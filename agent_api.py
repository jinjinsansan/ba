"""LAPLACE -- Python Agent (BET mode)

Uses proven BaccaratScraper + BetExecutor + MaruBatsuBetSession.
Electron GUI communicates via stdin/stdout JSON IPC.

Flow:
  1. GUI sends start → agent launches Camoufox
  2. Scraper: login → lobby → WS intercept → find table
  3. Executor: enter table
  4. BetSession: run_round loop (BET → result → logic)
  5. All status/events sent to GUI via stdout
"""
import json
import sys
import os
import threading
import time
import logging
import io

# ---- Force stdio to UTF-8 (MUST run before any send_log/send_msg) -------
# PyInstaller-bundled Python on a Japanese Windows install defaults to
# cp932 for sys.stdout / sys.stderr, which chokes on characters like
# the em dash U+2014 used throughout our log messages and crashes the
# whole BET session with UnicodeEncodeError. The parent Electron process
# always decodes the child pipes as UTF-8, so forcing UTF-8 on both ends
# is the right fix.
for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except Exception:
            pass

# ---- Eager imports (MUST happen on the main thread) --------------------
# Importing numpy from a worker thread while another thread is blocked on
# sys.stdin.readline() deadlocks inside numpy._core.overrides on Python
# 3.12 Windows. camoufox.async_api transitively imports numpy, so the
# scraper import used to hang the whole BET session.
#
# Pull every heavy / native dependency in up front from the main thread
# so the worker thread only needs to reference already-loaded modules.
# Order matters: numpy first, then playwright/camoufox, then our own
# modules that depend on them.
try:
    import numpy  # noqa: F401 -- pre-warm numpy on main thread
except Exception:
    pass
try:
    import playwright.sync_api  # noqa: F401
except Exception:
    pass
try:
    import camoufox.sync_api  # noqa: F401
except Exception:
    pass

# ---- Bundled camoufox browser bootstrap --------------------------------
# When the Engine is packaged via PyInstaller, the build script can include
# a pre-fetched camoufox browser tree at <exe_dir>/camoufox_cache/.
# On first launch we copy it into the platform cache dir that
# camoufox.pkgman.INSTALL_DIR points to, so users never have to run
# `camoufox fetch` or download 530 MB themselves.
def _bootstrap_camoufox_cache():
    try:
        from camoufox.pkgman import INSTALL_DIR
        if INSTALL_DIR.exists() and (INSTALL_DIR / "version.json").exists():
            return  # already installed, nothing to do
        exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
        bundled = os.path.join(exe_dir, "camoufox_cache")
        if not os.path.isdir(bundled):
            return  # no bundled cache
        import shutil
        INSTALL_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundled, str(INSTALL_DIR), dirs_exist_ok=True)
    except Exception:
        pass

_bootstrap_camoufox_cache()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env early so LAPLACE_USE_REMOTE etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log"),
            encoding="utf-8",
        )
    ],
)
logger = logging.getLogger("valhalla.agent")

# Global reference to current active BET session (for live config updates)
_active_session = None
# Pending config updates received before session was created
_pending_config_update = {}
# BET mode: mutable box for cross-thread access (stdin_reader ↔ bet loop)
_bet_mode_box = ["1drop"]       # ユーザー選択モード: "normal" | "1drop" | "mix"
_effective_mode_box = ["1drop"] # 実行時モード（mixの場合 normal→1drop に自動切替）

MAX_ROUNDS = 9999


# ======== IPC ========

def send_msg(msg: dict):
    line = json.dumps(msg, ensure_ascii=False) + "\n"
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Belt-and-braces: if the stdout text wrapper somehow still has a
        # non-UTF-8 encoding (e.g. cp932 on a Japanese Windows PyInstaller
        # build that ignored our reconfigure), push raw UTF-8 bytes onto
        # the underlying binary buffer instead. The Electron parent always
        # decodes the child pipe as UTF-8, so this works.
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            try:
                buf.write(line.encode("utf-8", errors="replace"))
                buf.flush()
            except Exception:
                pass
        else:
            # Last resort: ASCII-safe JSON (escapes everything non-ASCII)
            try:
                ascii_line = json.dumps(msg, ensure_ascii=True) + "\n"
                sys.stdout.write(ascii_line)
                sys.stdout.flush()
            except Exception:
                pass
    except Exception:
        pass

def send_log(text: str):
    send_msg({"type": "log", "message": text})

def send_action(text: str):
    """Send browser action status for GUI display"""
    send_msg({"type": "action", "message": text})

def send_result(result: str, won: bool | None, bet_amount: float, balance: float,
                turn: int, turns_display: str, cumulative_profit: int, cumulative_money: float,
                round_profit_dollars: float = 0.0):
    send_msg({
        "type": "round_result",
        "result": result,
        "won": won,
        "bet_amount": bet_amount,
        "balance": balance,
        "turn": turn,
        "turns_display": turns_display,
        "cumulative_profit": cumulative_profit,
        "cumulative_money": cumulative_money,
        "round_profit": round_profit_dollars,
    })

def send_set_complete(set_data, chip_base: float):
    send_msg({
        "type": "set_complete",
        "set_index": set_data.set_index,
        "results": set_data.results,
        "wins": set_data.wins,
        "losses": set_data.losses,
        "set_profit": set_data.set_profit,
        "cumulative_profit": set_data.cumulative_profit,
        "money_set": set_data.set_profit * chip_base,
        "money_cum": set_data.cumulative_profit * chip_base,
        "overshoot": set_data.overshoot,
    })

def send_status(session, balance: float = 0):
    s = session.get_summary()
    turns = session.tracker.current_turns
    turns_display = "".join("O" if t == "O" else "X" for t in turns)
    overshoot = session.tracker.prev_overshoot
    send_msg({
        "type": "status",
        "cumulative_profit": s["cumulative_profit"],
        "cumulative_money": s["cumulative_money"],
        "wins": s["total_wins"],
        "losses": s["total_losses"],
        "ties": s["total_ties"],
        "set_count": s["sets"],
        "current_turn": s["current_turn"],
        "current_unit": s["current_unit"],
        "current_unit_idx": s["current_unit_idx"],
        "total_bets": s["total_bets"],
        "overshoot": overshoot,
        "running": True,
        "balance": balance,
        "turns_display": turns_display,
        "session_count": s["session_count"],
    })

def send_shoe_history(sets: list, chip_base: float):
    """Send all completed sets for shoe display"""
    data = []
    for s in sets:
        data.append({
            "set_index": s.set_index,
            "results": s.results,
            "wins": s.wins,
            "losses": s.losses,
            "set_profit": s.set_profit,
            "cumulative_profit": s.cumulative_profit,
            "overshoot": s.overshoot,
            "slashed": s.slashed,
        })
    send_msg({"type": "shoe_history", "sets": data, "chip_base": chip_base})


# ======== BET Runner ========

def run_bet_session(config: dict, stop_event: threading.Event, skip_event: threading.Event = None):
    """Main BET loop entry — runs in a thread. Wraps the real body so that
    any unhandled exception is surfaced to the GUI instead of silently
    killing the daemon thread."""
    import traceback as _tb
    try:
        return _run_bet_session_inner(config, stop_event, skip_event)
    except Exception as _err:
        tb = _tb.format_exc()
        try:
            send_log(f"FATAL: BET session crashed: {_err}")
            for _line in tb.splitlines():
                if _line.strip():
                    send_log(_line)
        except Exception:
            pass
        try:
            logger.error("BET session crashed", exc_info=True)
        except Exception:
            pass
        try:
            send_msg({"type": "error", "message": f"BET session crashed: {_err}"})
            send_msg({"type": "stopped", "code": -1})
        except Exception:
            pass


def _run_bet_session_inner(config: dict, stop_event: threading.Event, skip_event: threading.Event = None):
    global _active_session, _pending_config_update, _bet_mode_box, _effective_mode_box
    """Main BET loop — runs in a thread."""
    # BETモード初期化
    _bet_mode_box[0] = config.get("bet_mode", "1drop")
    _effective_mode_box[0] = "normal" if _bet_mode_box[0] == "mix" else _bet_mode_box[0]
    send_log(f"BET mode: {_bet_mode_box[0]} (effective: {_effective_mode_box[0]})")
    import config as cfg
    # Headless is determined by env (VPS sets LAPLACE_HEADLESS=1) or config.ini; default False
    if os.getenv("LAPLACE_HEADLESS", "").strip() in ("1", "true", "True", "yes"):
        cfg.HEADLESS = True
    cfg.PROFILE_NAME = os.getenv("LAPLACE_PROFILE_NAME", "bet")

    # These modules were pre-imported on the main thread at agent_api load
    # time (see top of file) so Python's import machinery does NOT deadlock
    # when the worker thread touches numpy-backed code.
    from scraper import BaccaratScraper
    from executor import BetExecutor
    from game_ws import GameWSMonitor
    from humanizer import Humanizer
    from notify import TelegramNotifier, PublicNotifier, AdminNotifier, UserNotifier, CompositeNotifier
    # NOTE: marubatsu_bet / marubatsu_strategy / table_selector are lazily imported ONLY
    # in local-fallback mode. In production (LAPLACE_USE_REMOTE=1) these modules must
    # NEVER be imported on the client so that the core logic / scoring formulas cannot
    # be extracted from a shipped binary.

    # Remote LAPLACE API mode (VPS-hosted logic engine)
    use_remote = os.getenv("LAPLACE_USE_REMOTE", "0").strip() in ("1", "true", "True", "yes")
    RemoteLaplaceSession = None
    RemoteTableSelector = None
    if use_remote:
        try:
            from laplace_client import RemoteLaplaceSession, RemoteTableSelector, LaplaceApiError  # noqa: F401
            send_log(f"LAPLACE Remote mode: API={os.getenv('LAPLACE_API_URL', 'http://127.0.0.1:8000')} user={os.getenv('LAPLACE_USER', 'dev-machine')}")
        except Exception as e:
            send_log(f"Remote mode requested but client import failed ({e}) — falling back to local MaruBatsuBetSession")
            use_remote = False

    chip_base = config.get("chip_base", 1.0)
    profit_target_dollars = config.get("profit_target", 50)
    loss_cut_dollars = config.get("loss_cut", 200)
    dry_run = config.get("dry_run", False)
    resume = config.get("resume", False)
    table_filter = config.get("table_filter", {})
    logger.info(f"Table filter: {table_filter}")
    send_log(f"Table filter: {table_filter}")

    # Allow overriding dry_run via environment (safe for CI / first-run testing)
    if os.getenv("LAPLACE_FORCE_DRYRUN", "").strip() in ("1", "true", "True", "yes"):
        if not dry_run:
            send_log("LAPLACE_FORCE_DRYRUN=1 detected — forcing dry_run=True")
        dry_run = True
    # Verification mode: fixed table, public channel notifications
    verification_mode = (
        config.get("verification_mode", False)
        or os.getenv("LAPLACE_MODE", "").lower() == "verification"
    )
    fixed_table_name = os.getenv("LAPLACE_FIXED_TABLE", "Japanese Speed Baccarat A")
    user_label = os.getenv("LAPLACE_USER", "anon")

    # Convert dollar amounts to chip units
    profit_stop_chips = max(1, int(round(profit_target_dollars / max(chip_base, 0.01))))
    loss_cut_chips = max(1, int(round(loss_cut_dollars / max(chip_base, 0.01))))

    send_log(f"Start mode: {'RESUME' if resume else 'RESET'} (dry_run={dry_run})")

    mode = "DRY RUN" if dry_run else "LIVE"
    send_action(f"Starting {mode} mode...")

    # Setup notifier system
    # Public channel is for independent monitoring only, NOT for GUI BET activity
    admin_notifier = AdminNotifier()  # reads ADMIN_BOT_TOKEN / ADMIN_CHAT_ID from env
    if dry_run:
        user_notifier = UserNotifier("", "")
    else:
        user_notifier = UserNotifier()  # reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from env
    composite = CompositeNotifier(public=None, admin=admin_notifier, user=user_notifier)
    # Legacy alias: existing code uses `notifier` with .send(), .notify_*() — use UserNotifier
    notifier = user_notifier

    def pick_table():
        """Verification modeなら固定テーブル、それ以外は通常選定"""
        if verification_mode:
            return selector.find_best_table(fixed_name=fixed_table_name, selector_config=table_filter)
        return selector.find_best_table(selector_config=table_filter)

    def find_1_drop_table() -> tuple[str, str] | None:
        """全テーブルをスキャンしてPlayerが出ている（1落ち）テーブルを探す。

        1落ち = 最新の非タイ結果がPlayer（R）であること。
        lobby WS の _evo_table_raw_histories をポーリングするだけで
        Playwright APIは呼ばないため、WSリスナースレッドをブロックしない。
        90秒ごとにEvo iframeに触れてSESSION EXPIREDを防ぐ。
        直前に使ったテーブル（target_tid）は候補から除外してランダム選択。
        見つかったら (table_id, table_name) を返す。STOPされた場合はNone。
        """
        import random as _random
        _MIN_HISTORY = 5  # シューリセット直後の信頼性低いテーブルを除外

        def _has_1drop(raw: list) -> bool:
            """最新の非タイ結果がPlayer（R）かつ履歴が十分あるか"""
            non_tie = [e for e in raw if e.get("c") in ("B", "R")]
            return len(non_tie) >= _MIN_HISTORY and non_tie[-1].get("c") == "R"

        send_action("Scanning all tables for Player 1-drop...")
        send_log("[observe] Scanning lobby WS — looking for latest Player result on any table")
        last_heartbeat = time.time()

        while not stop_event.is_set():
            # ── ハートビート（90秒ごと）Evolution iframeタッチでSESSION EXPIRED防止 ──
            if time.time() - last_heartbeat > 90:
                try:
                    inner = executor._get_evo_inner()
                    if inner:
                        inner.evaluate("() => document.documentElement.scrollTop", timeout=3000)
                except Exception:
                    pass
                if not scraper.get_all_table_configs():
                    send_log("[observe] Lobby WS lost — reconnecting...")
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                last_heartbeat = time.time()

            # ── 全テーブルをスキャンして1落ちリストを作成 ──
            configs = scraper.get_all_table_configs()
            candidates = []
            for tid, cfg in configs.items():
                raw = scraper.get_raw_history(tid)
                if _has_1drop(raw):
                    candidates.append((tid, cfg.get("title", tid)))

            if candidates:
                # 直前に使ったテーブルを除外（テーブルバリエーション確保）
                preferred = [(tid, tname) for tid, tname in candidates if tid != target_tid]
                chosen_list = preferred if preferred else candidates
                tid, tname = _random.choice(chosen_list)
                send_action(f"Player 1落ち検出: {tname} ({len(candidates)}件中) → 入場します")
                send_log(f"[observe] Player 1-drop found on {tname} ({tid}) — {len(candidates)} candidates")
                return tid, tname

            stop_event.wait(2)

        return None  # STOPされた

    def confirm_2nd_drop() -> str:
        """テーブル内で1ハンド観察し、2落ち目もPlayerかどうかを確認する。

        BETはしない。ロビーWSはテーブル入場後に切断されるため、
        ビーズロードDOM（executor.read_bead_road）から結果を読む。
        タイは無視して継続観察。
        Returns:
          "confirmed"   — Playerが出た（2落ち確認）→ BET開始
          "invalidated" — Bankerが出た → 退室してロビー監視に戻る
          "stopped"     — STOPイベント
        """
        send_action("In table — observing for 2nd Player (no BET)...")
        send_log("[2nd-drop] Observing bead road DOM to confirm Player streak")

        # 現在のビーズロード長を記録（最大3回リトライ）
        pre_bead = ""
        for _br in range(3):
            pre_bead = executor.read_bead_road()
            if pre_bead:
                break
            time.sleep(1)
        pre_len = len(pre_bead)
        if pre_len == 0:
            send_log("[2nd-drop] Bead road empty — skipping this table")
            return "invalidated"  # ビーズロード取得不可 → 別テーブルへ
        send_log(f"[2nd-drop] pre_bead len={pre_len} tail={pre_bead[-5:] if pre_bead else ''}")

        _observe_fail = 0  # ビーズロード更新失敗カウンタ
        while not stop_event.is_set():
            # 1ハンド見送り（BETせず結果を待つ）
            if not executor.wait_for_betting_phase(timeout=180, skip_round=True):
                return "stopped"

            # ビーズロードDOMから結果を確認（最大10秒、0.5秒ポーリング）
            deadline = time.time() + 10
            _got_update = False
            while time.time() < deadline and not stop_event.is_set():
                new_bead = executor.read_bead_road()
                if len(new_bead) > pre_len:
                    _observe_fail = 0  # リセット
                    new_chars = new_bead[pre_len:]
                    send_log(f"[2nd-drop] new chars: {new_chars!r}")
                    for ch in new_chars:
                        if ch == 'P':
                            send_action("2nd Player confirmed → BET Player next hand!")
                            send_log("[2nd-drop] Player streak confirmed — starting BET")
                            return "confirmed"
                        elif ch == 'B':
                            send_action("Banker appeared — streak broken → returning to lobby")
                            send_log("[2nd-drop] Banker appeared — exit table")
                            return "invalidated"
                        # T = タイ → pre_len更新して次のハンドを待つ
                    pre_len = len(new_bead)
                    _got_update = True
                    break  # タイのみ → outer whileループで再観察
                time.sleep(0.5)
            if not _got_update:
                _observe_fail += 1
                send_log(f"[2nd-drop] Bead road not updated ({_observe_fail}/3) — re-observing")
                if _observe_fail >= 3:
                    send_log("[2nd-drop] Bead road stuck — switching table")
                    return "invalidated"

        return "stopped"

    def observe_until_1_drop(tid: str, tname: str) -> bool:
        """後方互換ラッパー: find_1_drop_table() に委譲し、結果でtarget_tid/nameを更新"""
        result = find_1_drop_table()
        if result is None:
            return False
        nonlocal target_tid, target_name
        target_tid, target_name = result
        return True

    BACCARAT_LOBBY_URL = "https://stake.com/casino/games/evolution-baccarat-lobby"

    # === Sync Mode: 推奨テーブル（Phase 1: ハードコード、Phase 2でSupabase化）===
    SYNC_RECOMMENDED_TABLES = config.get("recommended_tables") or [
        "Japanese Speed Baccarat A",
        "Korean Speed Baccarat B",
    ]

    def find_sync_table() -> tuple[str, str] | None:
        """推奨テーブルから規則性の高いものを選択（入場前の静的判断）

        条件:
          1. 推奨リストにあるテーブル
          2. ハンド数 >= 35（シュー約50%経過）
          3. 規則性スコア >= 70
        優先順位: リストの順
        SESSION EXPIRED対策: 90秒ごとにiframeタッチ
        """
        from regularity_monitor import evaluate_table, raw_history_to_results, ENTRY_THRESHOLD, MIN_HANDS_FOR_ENTRY

        send_action("🔍 Syncモード: 推奨テーブルを監視中...")
        send_log(f"[Sync] 推奨テーブル: {', '.join(SYNC_RECOMMENDED_TABLES)}")
        send_log(f"[Sync] 入場条件: ハンド数≥{MIN_HANDS_FOR_ENTRY}, 規則性≥{ENTRY_THRESHOLD}")
        last_heartbeat = time.time()
        last_status = time.time()
        scan_count = 0

        while not stop_event.is_set():
            scan_count += 1
            # ハートビート（90秒ごと）
            if time.time() - last_heartbeat > 90:
                send_log("[Sync] 💓 ハートビート送信（SESSION EXPIRED対策）")
                try:
                    inner = executor._get_evo_inner()
                    if inner:
                        inner.evaluate("() => document.documentElement.scrollTop", timeout=3000)
                except Exception:
                    pass
                if not scraper.get_all_table_configs():
                    send_log("[Sync] ⚠️ ロビーWS切断 → 再接続中...")
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                last_heartbeat = time.time()

            configs = scraper.get_all_table_configs()
            name_to_tid = {cfg.get("title", ""): tid for tid, cfg in configs.items()}

            # 推奨テーブルを順に評価
            best = None
            table_reports = []
            for rec_name in SYNC_RECOMMENDED_TABLES:
                tid = name_to_tid.get(rec_name)
                if not tid:
                    table_reports.append(f"❌ {rec_name}: ロビーに存在しません")
                    continue
                raw = scraper.get_raw_history(tid)
                results = raw_history_to_results(raw)
                eval_result = evaluate_table(results)
                reg = eval_result['regularity']
                hands = eval_result['hands']

                if hands < MIN_HANDS_FOR_ENTRY:
                    table_reports.append(f"⏳ {rec_name}: {hands}ハンド（{MIN_HANDS_FOR_ENTRY}まで待機）")
                elif reg < ENTRY_THRESHOLD:
                    table_reports.append(f"⚠️ {rec_name}: {hands}ハンド reg={reg:.0f}（閾値{ENTRY_THRESHOLD}未満）")
                else:
                    table_reports.append(f"✅ {rec_name}: {hands}ハンド reg={reg:.0f} → 条件クリア!")
                    if best is None or reg > best[2]:
                        best = (tid, rec_name, reg)

            # 15秒ごとに候補状況をログ出力
            if time.time() - last_status > 15:
                for report in table_reports:
                    send_log(f"[Sync] {report}")
                last_status = time.time()

            if best:
                tid, tname, reg = best
                send_action(f"🎯 Sync: {tname} に入場します (reg={reg:.0f})")
                send_log(f"[Sync] ★ 入場決定: {tname} 規則性={reg:.0f}")
                return tid, tname

            # 待機メッセージ（30秒ごと）
            if scan_count % 10 == 1:
                send_action("⏱️ 全推奨テーブルが条件未達 — 待機中...")

            stop_event.wait(3)

        return None

    def check_sync_regularity(tid) -> dict:
        """動的監視: 現在のテーブルの規則性をチェック（BET中）

        ロビーWSではなくexecutor.read_bead_road()でDOMから読む
        （入場後はロビーWSが切断されるため）
        """
        from regularity_monitor import evaluate_table
        try:
            bead = executor.read_bead_road()
            if bead:
                return evaluate_table(list(bead))
        except Exception as e:
            send_log(f"[Sync-Monitor] ⚠️ ビーズロード読み取り失敗: {e}")
        return {'regularity': 0, 'hands': 0, 'can_enter': False, 'should_exit': False}

    def full_recovery() -> tuple[str, str] | None:
        """最終手段フルリカバリ: ページ完全リロード→ログイン確認→WS再接続→テーブル再選定

        iframe壊死・WS接続不能・entry連続失敗など、通常のリカバリで復旧できない場合の最終手段。
        正常に動いている既存ロジックには干渉しない。
        Returns: (table_id, table_name) or None (STOP時)
        """
        nonlocal target_tid, target_name
        send_action("Full recovery — reloading page...")
        send_log("[recovery] Starting full page recovery")

        # 1. テーブル状態をクリア
        try:
            executor.game_ws.reset()
            executor._reset_state()
        except Exception:
            pass

        # 2. ページを完全にリロード（lobby URLに直接遷移）
        try:
            send_log("[recovery] Navigating to lobby...")
            scraper.page.goto(BACCARAT_LOBBY_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
        except Exception as e:
            send_log(f"[recovery] page.goto failed: {e}")
            # それでも続行を試みる

        if stop_event.is_set():
            return None

        # 3. ログイン状態を確認、必要なら再ログイン
        try:
            if not scraper._is_logged_in():
                send_log("[recovery] Not logged in — attempting re-login...")
                send_action("Re-logging in to Stake...")
                scraper._login_from_lobby()
                time.sleep(3)
                send_log("[recovery] Re-login completed")
        except Exception as e:
            send_log(f"[recovery] Re-login failed: {e}")
            # それでもWS接続を試みる

        if stop_event.is_set():
            return None

        # 4. WS傍受を再設定
        try:
            send_log("[recovery] Reconnecting lobby WS...")
            scraper.setup_ws_intercept()
            send_log("[recovery] Lobby WS reconnected")
        except Exception as e:
            send_log(f"[recovery] WS reconnect failed: {e}")

        if stop_event.is_set():
            return None

        # 5. テーブル再選定
        send_action("Recovery — selecting table...")
        target_tid = None
        target_name = None
        for _rt in range(5):
            if stop_event.is_set():
                return None
            best = pick_table()
            if best:
                target_tid = best.table_id
                target_name = best.title
                with scraper._lock:
                    scraper._target_table_ids.add(target_tid)
                    scraper._target_table_names[target_tid] = target_name
                    scraper._new_shoe_signals[target_tid] = False
                    scraper._shoe_epochs[target_tid] = int(time.time())
                send_action(f"Recovery complete — picked {target_name}")
                send_log(f"[recovery] Table selected: {target_name}")
                return target_tid, target_name
            else:
                if not scraper.get_all_table_configs():
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                if stop_event.wait(10):
                    return None

        send_log("[recovery] Full recovery failed — no table available")
        return None

    # Startup broadcast (admin + user + public if verification)
    try:
        composite.on_startup(user_label, {
            "dry_run": dry_run,
            "chip_base": chip_base,
            "profit_target": profit_target_dollars,
            "loss_cut": loss_cut_dollars,
            "verification_mode": verification_mode,
        }, fixed_table_name if verification_mode else "auto-select")
    except Exception as e:
        logger.warning(f"Startup notification failed: {e}")

    # === Browser launch ===
    send_action("Launching browser...")
    scraper = BaccaratScraper()
    scraper.table_name = "all"

    try:
        scraper.start()
    except Exception as e:
        send_log(f"Browser launch failed: {e}")
        send_action("Browser launch failed")
        return

    send_action("Browser ready. Waiting for Evolution WS...")
    scraper.setup_ws_intercept()

    if scraper._evo_ws_connected:
        send_action("Evolution WS connected")
    else:
        send_action("Evolution WS timeout — continuing...")

    # === Table Selector ===
    send_action("Loading table data...")
    time.sleep(12)  # configs/histories/playersCount の初期ロード待機

    if use_remote:
        # All scoring / exclusion / threshold logic runs on the VPS.
        # This client never ships table_selector.py.
        from laplace_client import LaplaceClient as _LaplaceClient
        _api_url = os.getenv("LAPLACE_API_URL", "http://127.0.0.1:8000")
        _api_key = os.getenv("LAPLACE_API_KEY", "")
        _user_id = os.getenv("LAPLACE_USER", "dev-machine")
        _selector_client = _LaplaceClient(_api_url, _api_key)
        selector = RemoteTableSelector(scraper, _selector_client, _user_id)
    else:
        # Local fallback — requires table_selector.py on disk
        from table_selector import TableSelector
        selector = TableSelector(scraper)
    humanizer = Humanizer(cfg.HUMANIZE_CONFIG)
    executor_config = {"demo_mode": dry_run}
    executor = BetExecutor(scraper.page, scraper.game_ws, executor_config, humanizer=humanizer)

    def _make_local_session():
        # Lazy import — only when running in local fallback mode.
        # On shipped client binaries, marubatsu_bet / marubatsu_strategy are NOT included,
        # so this import will fail and force the user to use VPS remote mode.
        from marubatsu_bet import MaruBatsuBetSession
        return MaruBatsuBetSession(
            executor=executor,
            notifier=notifier,
            chip_base=chip_base,
            loss_cut=loss_cut_chips,
            profit_stop=profit_stop_chips,
            dry_run=dry_run,
            resume=resume,
        )

    if use_remote:
        try:
            session = RemoteLaplaceSession(
                executor=executor,
                notifier=notifier,
                chip_base=chip_base,
                loss_cut=loss_cut_chips,
                profit_stop=profit_stop_chips,
                dry_run=dry_run,
                resume=resume,
            )
            send_action(f"LAPLACE Remote session ready (sets={len(session.tracker.sets)}, cp={session.tracker.cumulative_profit:+d})")
        except Exception as e:
            send_log(f"Remote session creation failed ({e}) — falling back to local MaruBatsuBetSession")
            try:
                session = _make_local_session()
            except ImportError as imp_err:
                send_log(f"FATAL: local fallback unavailable on this build ({imp_err}). VPS API is required.")
                return
    else:
        try:
            session = _make_local_session()
        except ImportError as imp_err:
            send_log(f"FATAL: local mode requires marubatsu_bet/marubatsu_strategy ({imp_err}). Set LAPLACE_USE_REMOTE=1 to use the VPS API instead.")
            return
    _active_session = session

    # Apply any pending config updates received before session creation
    if _pending_config_update:
        pending = _pending_config_update
        _pending_config_update = {}
        new_pt_chips = None
        new_lc_chips = None
        if "profit_target" in pending:
            new_pt = float(pending["profit_target"])
            new_pt_chips = max(1, int(round(new_pt / max(chip_base, 0.01))))
            session.profit_stop = new_pt_chips
            send_log(f"Applied pending profit target: ${new_pt:.0f} ({new_pt_chips} chips)")
        if "loss_cut" in pending:
            new_lc = float(pending["loss_cut"])
            new_lc_chips = max(1, int(round(new_lc / max(chip_base, 0.01))))
            session.loss_cut = new_lc_chips
            send_log(f"Applied pending loss cut: ${new_lc:.0f} ({new_lc_chips} chips)")
        # Sync to remote if applicable
        if use_remote and hasattr(session, "update_config"):
            try:
                session.update_config(profit_stop=new_pt_chips, loss_cut=new_lc_chips)
            except Exception as e:
                send_log(f"Remote config sync failed: {e}")

    # === Select initial table ===
    target_tid = None
    target_name = None
    while not stop_event.is_set() and target_tid is None:
        if verification_mode:
            send_action(f"[VERIFICATION] Looking for fixed table: {fixed_table_name}")
            best = selector.find_best_table(fixed_name=fixed_table_name, selector_config=table_filter)
        else:
            send_action("Selecting best table...")
            best = selector.find_best_table(selector_config=table_filter)
        if best:
            target_tid = best.table_id
            target_name = best.title
            send_action(f"Picked: {target_name} ({best.players}p, {best.hands}h, P:{best.p_count}/B:{best.b_count})")
        else:
            send_action("No suitable table — waiting 15s...")
            if stop_event.wait(15):
                break

    if not target_tid:
        send_log("Stopped before selecting table")
        scraper.stop()
        return

    # scraper に監視対象として追加 (shoe signal等のため)
    with scraper._lock:
        scraper._target_table_ids.add(target_tid)
        scraper._target_table_names[target_tid] = target_name
        if target_tid not in scraper._shoe_epochs:
            scraper._shoe_epochs[target_tid] = int(time.time())
            scraper._new_shoe_signals[target_tid] = False

    # === 1落ち待機（ロビー観察）=== — 1-dropモードのみ
    if _effective_mode_box[0] == "1drop":
        if not observe_until_1_drop(target_tid, target_name):
            send_log("Stopped during lobby observation")
            scraper.stop()
            return

    # === Syncモード: 推奨テーブルから規則性が高いものを選定 ===
    if _effective_mode_box[0] == "sync":
        res_sync = find_sync_table()
        if not res_sync:
            send_log("Stopped during sync table selection")
            scraper.stop()
            return
        target_tid, target_name = res_sync
        with scraper._lock:
            scraper._target_table_ids.add(target_tid)
            scraper._target_table_names[target_tid] = target_name
            scraper._new_shoe_signals[target_tid] = False
            scraper._shoe_epochs[target_tid] = int(time.time())

    # === Enter table (診断ログ付き) ===
    send_action(f"Entering table: {target_name}...")

    # 診断: ブラウザ状態を出力
    try:
        page_url = scraper.page.url
        frame_urls = [f.url[:80] for f in scraper.page.frames]
        evo_frames = [u for u in frame_urls if "evo" in u.lower()]
        send_log(f"[DIAG] page={page_url[:80]}")
        send_log(f"[DIAG] frames={len(frame_urls)} evo={len(evo_frames)}")
        for eu in evo_frames:
            send_log(f"[DIAG] evo_frame: {eu}")
        if not evo_frames:
            send_log(f"[DIAG] ALL frames: {frame_urls}")
        # スクリーンショット
        try:
            import config as _cfg
            scraper.page.screenshot(path=str(_cfg.SCREENSHOTS_DIR / "before_entry.png"))
            send_log("[DIAG] screenshot saved: before_entry.png")
        except Exception as ss_err:
            send_log(f"[DIAG] screenshot failed: {ss_err}")
    except Exception as diag_err:
        send_log(f"[DIAG] diagnostic failed: {diag_err}")

    _entry_ok = False
    for _attempt in range(3):
        if executor.enter_table(target_tid, target_name):
            _entry_ok = True
            break
        # 失敗時の詳細診断
        try:
            evo_frames_now = [f.url[:80] for f in scraper.page.frames if "evo" in f.url.lower()]
            send_log(f"[DIAG] after fail: evo_frames={len(evo_frames_now)} page={scraper.page.url[:60]}")
        except Exception:
            pass
        send_log(f"Table entry failed (attempt {_attempt+1}/3) — retrying in 10s...")
        send_action(f"Entry failed — retrying ({_attempt+1}/3)...")
        if _attempt < 2:
            # リトライ前にロビーに戻る
            try:
                send_log("[DIAG] Navigating back to lobby before retry...")
                import config as _cfg
                scraper.page.goto(_cfg.BACCARAT_LOBBY_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
            except Exception as nav_err:
                send_log(f"[DIAG] lobby navigation failed: {nav_err}")
            time.sleep(5)
    if not _entry_ok:
        send_log("Table entry failed after 3 attempts — stopping")
        send_action("Table entry failed — stopping")
        scraper.stop()
        return

    balance = executor.get_balance() if not dry_run else 0
    send_action(f"In table. Balance: ${balance:.2f}")
    send_log(f"BET session started [{mode}] table={target_name} chip=${chip_base} balance=${balance:.2f}")
    send_shoe_history(session.tracker.sets, chip_base)

    # === Main BET loop ===
    round_count = 0
    entry_fail_count = 0
    session_start = time.time()

    _FREEZE_TIMEOUT = 90      # WS無活動90秒でフリーズ判定
    _SESSION_CHECK_INTERVAL = 300  # 5分おきにStakeログイン確認
    _last_session_check = time.time()
    _deferred_exit_reason = None   # BETウィンドウ保護: exit checkは前ラウンドで実行済み
    _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")  # 1-dropモード時のみ2落ち確認
    _awaiting_sync_confirm = (_effective_mode_box[0] == "sync")  # syncモード: 入場直後の再確認
    _bet_fail_count = 0            # BET完全失敗カウンタ（3連続で退室）
    _sync_monitor_counter = 0      # Syncモード: 動的規則性監視カウンタ

    while not stop_event.is_set() and round_count < MAX_ROUNDS:
        # ── フリーズ検出ウォッチドッグ ──
        ws_idle = scraper.game_ws.seconds_since_last_message() if hasattr(scraper, 'game_ws') and scraper.game_ws else 0
        if ws_idle > _FREEZE_TIMEOUT and target_tid:
            send_action(f"Browser freeze detected ({ws_idle:.0f}s no WS) — reloading...")
            send_log(f"[watchdog] WS silent {ws_idle:.0f}s — page reload")
            try:
                scraper.page.reload(timeout=15000)
                import time as _t; _t.sleep(5)
                executor.exit_table()
                _t.sleep(3)
                if executor.enter_table(target_tid, target_name):
                    send_action(f"Recovered — re-entered {target_name}")
                    _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                else:
                    # 通常リカバリ失敗 → フルリカバリ
                    send_log("[watchdog] Normal recovery failed — escalating to full recovery")
                    fr = full_recovery()
                    if not fr:
                        break
                    target_tid, target_name = fr
            except Exception as _e:
                send_log(f"[watchdog] reload error: {_e} — escalating to full recovery")
                fr = full_recovery()
                if not fr:
                    break
                target_tid, target_name = fr
            continue

        # ── Stakeセッション確認（5分おき）──
        if time.time() - _last_session_check > _SESSION_CHECK_INTERVAL:
            _last_session_check = time.time()
            try:
                if not scraper._is_logged_in():
                    send_action("Stake session expired — re-logging in...")
                    send_log("[session] Stake logout detected — attempting re-login")
                    try:
                        scraper._login()
                        send_log("[session] Re-login successful")
                    except Exception as _le:
                        send_log(f"[session] Re-login failed: {_le} — escalating to full recovery")
                        fr = full_recovery()
                        if not fr:
                            break
                        target_tid, target_name = fr
                        if executor.enter_table(target_tid, target_name):
                            _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                        continue
                    executor.exit_table()
                    time.sleep(3)
                    if executor.enter_table(target_tid, target_name):
                        send_action(f"Session restored — re-entered {target_name}")
                        _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                    else:
                        # 再入場失敗 → フルリカバリ
                        fr = full_recovery()
                        if not fr:
                            break
                        target_tid, target_name = fr
                        if executor.enter_table(target_tid, target_name):
                            _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                    continue
            except Exception as _se:
                send_log(f"[session] re-login error: {_se}")

        # Shoe change check — 同じテーブルに滞在中のみ有効
        # 1-Dropモードでテーブルを変えた直後はshoe signalを無視する
        if not _awaiting_2nd_drop:  # 2落ち確認中 = 入場直後 → スキップ
            shoe_signals = scraper.get_new_shoe_signals()
            if target_tid in shoe_signals and shoe_signals[target_tid]:
                send_action("Shoe change detected")
                send_log("Shoe change — partial turns discarded")
                session.handle_shoe_change()

        # Session break (anti-bot) — 無効化
        # 1-dropモードではロビー監視+テーブル出入りが実質休憩になる。
        # 休憩中にEvolutionセッションが切れるためSESSION EXPIRED の主要原因だった。
        # session_start のリセットのみ残す（セッション時間トラッキング用）
        if len(session.tracker.current_turns) == 0:
            minutes_elapsed = (time.time() - session_start) / 60
            if humanizer.should_take_break(minutes_elapsed):
                session_start = time.time()  # タイマーリセットのみ

        # User-requested skip takes precedence (only between sets)
        user_skip = False
        if skip_event is not None and skip_event.is_set() and len(session.tracker.current_turns) == 0:
            user_skip = True
            skip_event.clear()

        # Deferred exit check (non-blocking: uses result from previous iteration)
        # should_exit_table API call moved to END of loop to avoid blocking BET window
        if len(session.tracker.current_turns) == 0 and (_deferred_exit_reason or user_skip):
            exit_reason = "User requested skip" if user_skip else _deferred_exit_reason
            _deferred_exit_reason = None
            if exit_reason:
                send_action(f"Table conditions broke: {exit_reason} — exiting...")
                send_log(f"Leaving {target_name}: {exit_reason}")
                executor.exit_table()
                time.sleep(3)

                # ロビーWS再接続 (テーブル退出後にconfigsが空になる対策)
                if not scraper.get_all_table_configs():
                    send_log("Lobby WS lost — reconnecting...")
                    try:
                        scraper.setup_ws_intercept()
                    except Exception as _ws_err:
                        send_log(f"Lobby WS reconnect failed: {_ws_err}")

                # 再選定
                target_tid = None
                target_name = None
                while not stop_event.is_set() and target_tid is None:
                    send_action("Re-selecting table...")
                    best = pick_table()
                    if best:
                        target_tid = best.table_id
                        target_name = best.title
                        send_action(f"Picked: {target_name} ({best.players}p, {best.hands}h)")
                    else:
                        # configsが空のままならlobby WS再接続を試行
                        if not scraper.get_all_table_configs():
                            send_log("Still no configs — lobby WS reconnect retry...")
                            try:
                                scraper.setup_ws_intercept()
                            except Exception:
                                pass
                        send_action("No suitable table — waiting 15s...")
                        if stop_event.wait(15):
                            break

                if stop_event.is_set():
                    break

                with scraper._lock:
                    scraper._target_table_ids.add(target_tid)
                    scraper._target_table_names[target_tid] = target_name
                    if target_tid not in scraper._shoe_epochs:
                        scraper._shoe_epochs[target_tid] = int(time.time())
                        scraper._new_shoe_signals[target_tid] = False

                if _effective_mode_box[0] == "1drop":
                    if not observe_until_1_drop(target_tid, target_name):
                        break
                send_action(f"Entering {target_name}...")
                if not executor.enter_table(target_tid, target_name):
                    send_action("Entry failed — retrying...")
                    time.sleep(5)
                    continue
                _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")  # deferred exit後再入場 → 2落ち確認必須

        # ── 2落ち確認フェーズ（入場直後のみ、BETしないで1ハンド観察）──
        if _awaiting_2nd_drop:
            cdr = confirm_2nd_drop()
            if cdr == "stopped":
                break
            elif cdr == "invalidated":
                # Bankerが来た → 退室してロビー監視へ
                executor.exit_table()
                # 退室後にランダム待機（10〜25秒）— 人間らしくロビーを眺める時間
                import random as _rand2
                _lobby_wait2 = _rand2.uniform(10, 25)
                send_action(f"Browsing lobby... ({_lobby_wait2:.0f}s)")
                if stop_event.wait(_lobby_wait2):
                    break
                if stop_event.is_set():
                    break
                if not scraper.get_all_table_configs():
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                res_1drop = find_1_drop_table()
                if not res_1drop:
                    break
                target_tid, target_name = res_1drop
                with scraper._lock:
                    scraper._target_table_ids.add(target_tid)
                    scraper._target_table_names[target_tid] = target_name
                    if target_tid not in scraper._shoe_epochs:
                        scraper._shoe_epochs[target_tid] = int(time.time())
                        scraper._new_shoe_signals[target_tid] = False
                _reenter_ok = False
                for _r in range(3):
                    send_action(f"Entering {target_name} (attempt {_r+1}/3)...")
                    if executor.enter_table(target_tid, target_name):
                        _reenter_ok = True
                        break
                    time.sleep(5)
                if not _reenter_ok:
                    send_action("Entry failed — stopping")
                    break
                _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                continue
            else:  # "confirmed" — Playerが2落ち確認
                _awaiting_2nd_drop = False
                # 次のBETフェーズでrun_round()へ

        # ── Syncモード: 入場後の規則性再確認（DOM読み取り）──
        # ロビーWSとテーブル内DOMの不整合を検出、条件未達なら即退避
        if _awaiting_sync_confirm:
            from regularity_monitor import evaluate_table, ENTRY_THRESHOLD, MIN_HANDS_FOR_ENTRY
            send_action("🔍 Sync: 入場後の規則性を再確認中...")
            send_log("[Sync-Entry] ビーズロードから規則性を再計算")
            try:
                bead = executor.read_bead_road()
                if bead:
                    eval_r = evaluate_table(list(bead))
                    reg = eval_r['regularity']
                    hands = eval_r['hands']
                    send_log(f"[Sync-Entry] テーブル内: {hands}ハンド reg={reg:.0f}")
                    if hands < MIN_HANDS_FOR_ENTRY or reg < ENTRY_THRESHOLD:
                        send_action(f"⚠️ Sync: 条件未達 (hands={hands} reg={reg:.0f}) — 退避")
                        send_log(f"[Sync-Entry] ❌ 入場後確認失敗: {hands}ハンド reg={reg:.0f} < 閾値 → 退避")
                        executor.exit_table()
                        import random as _rand_se
                        _w = _rand_se.uniform(5, 10)
                        send_log(f"[Sync] 🚶 ロビーで{_w:.0f}秒待機...")
                        if stop_event.wait(_w):
                            break
                        # 次の候補テーブルを探す
                        if not scraper.get_all_table_configs():
                            try:
                                scraper.setup_ws_intercept()
                            except Exception:
                                pass
                        res_s = find_sync_table()
                        if not res_s:
                            break
                        target_tid, target_name = res_s
                        with scraper._lock:
                            scraper._target_table_ids.add(target_tid)
                            scraper._target_table_names[target_tid] = target_name
                            scraper._new_shoe_signals[target_tid] = False
                            scraper._shoe_epochs[target_tid] = int(time.time())
                        send_action(f"🚪 {target_name} に入場中...")
                        if not executor.enter_table(target_tid, target_name):
                            fr = full_recovery()
                            if not fr:
                                break
                            target_tid, target_name = fr
                            if not executor.enter_table(target_tid, target_name):
                                break
                        _awaiting_sync_confirm = True  # 新しいテーブルでも再確認
                        continue
                    else:
                        send_action(f"✅ Sync: 確認OK (hands={hands} reg={reg:.0f}) — BET開始")
                        send_log(f"[Sync-Entry] ✅ 入場後確認OK: {hands}ハンド reg={reg:.0f} → BET開始")
                        _awaiting_sync_confirm = False
                else:
                    send_log("[Sync-Entry] ⚠️ ビーズロード空 — 継続（初回BET後に動的監視で判定）")
                    _awaiting_sync_confirm = False
            except Exception as e:
                send_log(f"[Sync-Entry] ⚠️ エラー: {e}")
                _awaiting_sync_confirm = False

        # BET phase — amount comes from session (remote: from VPS state; local: from tracker)
        bet_amount = session.get_bet_amount()
        total_hands = session.total_wins + session.total_losses + session.total_ties + 1
        send_action(f"Hand #{total_hands} -- Betting ${bet_amount:.0f}")

        result = session.run_round(lambda: not stop_event.is_set())

        if result["action"] == "exit":
            send_action("Session interrupted — attempting re-entry...")
            executor.exit_table()
            time.sleep(5)

            if stop_event.is_set():
                break

            send_action(f"Re-entering {target_name}...")
            if executor.enter_table(target_tid, target_name):
                entry_fail_count = 0
                _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                continue
            else:
                entry_fail_count += 1
                if entry_fail_count >= 2:
                    # EV.5 / SESSION EXPIRED — Stake再ログインを試行
                    send_action("Entry failed repeatedly — attempting Stake re-login...")
                    send_log("[session] Re-login attempt after entry failures")
                    try:
                        scraper._login_from_lobby()
                        time.sleep(5)
                        scraper.setup_ws_intercept()
                    except Exception as _rl_err:
                        send_log(f"[session] Re-login failed: {_rl_err}")
                        # ロビーに戻ってconfigsを復旧
                        try:
                            scraper.setup_ws_intercept()
                        except Exception:
                            pass
                    # 再選定
                    send_action("Re-selecting table after re-login...")
                    target_tid = None
                    target_name = None
                    _reselect_tries = 0
                    while not stop_event.is_set() and target_tid is None and _reselect_tries < 5:
                        _reselect_tries += 1
                        best = pick_table()
                        if best:
                            target_tid = best.table_id
                            target_name = best.title
                            with scraper._lock:
                                scraper._target_table_ids.add(target_tid)
                                scraper._target_table_names[target_tid] = target_name
                        else:
                            if not scraper.get_all_table_configs():
                                try:
                                    scraper.setup_ws_intercept()
                                except Exception:
                                    pass
                            if stop_event.wait(15):
                                break
                    entry_fail_count = 0
                    if target_tid and not stop_event.is_set():
                        send_action(f"Entering {target_name}...")
                        if executor.enter_table(target_tid, target_name):
                            _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                            continue
                    if stop_event.is_set():
                        break
                    # 通常リカバリ全失敗 → フルリカバリ（最終手段）
                    send_log("[recovery] All normal recovery failed — escalating to full recovery")
                    fr = full_recovery()
                    if not fr:
                        break
                    target_tid, target_name = fr
                    if executor.enter_table(target_tid, target_name):
                        _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                        continue
                    send_action("Full recovery failed — stopping")
                    break
                else:
                    time.sleep(10)
                    continue

        round_count += 1

        # ── BET完全失敗チェック: bet_amount=0 なら失敗カウント ──
        if result.get("bet_amount", 0) == 0 and result.get("result"):
            _bet_fail_count += 1
            send_log(f"[bet-fail] BET failed ({_bet_fail_count}/3) on {target_name}")
            if _bet_fail_count >= 3:
                send_action(f"BET failed 3 times on {target_name} — switching table...")
                send_log(f"[bet-fail] 3 consecutive failures — exit table")
                executor.exit_table()
                import random as _rand3
                _lobby_wait3 = _rand3.uniform(10, 25)
                send_action(f"Browsing lobby... ({_lobby_wait3:.0f}s)")
                if stop_event.wait(_lobby_wait3):
                    break
                _bet_fail_count = 0
                if not scraper.get_all_table_configs():
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                if not observe_until_1_drop(target_tid, target_name):
                    break
                if not executor.enter_table(target_tid, target_name):
                    # 通常リカバリ失敗 → フルリカバリ
                    fr = full_recovery()
                    if not fr:
                        break
                    target_tid, target_name = fr
                    if not executor.enter_table(target_tid, target_name):
                        send_action("Full recovery failed — stopping")
                        break
                _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")
                continue
        else:
            _bet_fail_count = 0  # 成功したらリセット

        # Send round result to GUI
        if result.get("result"):
            res = result["result"]
            won = result.get("won")
            ba = result.get("bet_amount", 0)
            bal = executor.get_balance() if not dry_run else 0
            turns = session.tracker.current_turns
            turns_disp = "".join("O" if t == "O" else "X" for t in turns)
            cp = session.tracker.cumulative_profit
            cm = cp * chip_base

            # Per-round profit in dollars (for daily P&L aggregation)
            if res == "tie":
                round_profit = 0.0
            elif won:
                round_profit = ba  # Player win returns 1x bet
            else:
                round_profit = -ba

            if res == "tie":
                send_action(f"Tie — BET returned. Balance: ${bal:.2f}")
            elif won:
                send_action(f"WIN! +${ba:.0f}. Balance: ${bal:.2f}")
            else:
                send_action(f"LOSE. -${ba:.0f}. Balance: ${bal:.2f}")

            send_result(res, won, ba, bal, len(turns), turns_disp, cp, cm, round_profit)

        # Set complete
        if result.get("completed_set"):
            s = result["completed_set"]
            send_set_complete(s, chip_base)
            send_shoe_history(session.tracker.sets, chip_base)
            send_action(f"Set #{s.set_index} done: {s.wins}W/{s.losses}L, P&L: {s.set_profit:+d}")
            # Public channel broadcast (verification only)
            try:
                composite.on_set_complete({
                    "set_index": s.set_index,
                    "results": s.results,
                    "wins": s.wins,
                    "losses": s.losses,
                    "set_profit": s.set_profit,
                }, s.cumulative_profit * chip_base, verification_mode)
            except Exception as e:
                logger.warning(f"Public notify failed: {e}")

        # Profit/loss reset
        if result.get("should_reset"):
            cp = session.effective_profit()
            money = cp * chip_base
            is_win = cp >= session.profit_stop
            reason_en = "PROFIT TARGET" if is_win else "LOSS CUT"
            send_msg({
                "type": "session_reset",
                "is_profit": is_win,
                "amount": money,
                "reason": reason_en,
            })
            send_action(f"{reason_en} HIT! {'+$' if money >= 0 else '-$'}{abs(money):.0f} locked in -- new session starting")
            send_log(f"[{reason_en}] Session ended at {'+$' if money >= 0 else '-$'}{abs(money):.0f}")
            # Admin + Public broadcast
            try:
                hands_count = session.total_bets
                sess_num = session.session_count + 1
                if is_win:
                    composite.on_profit_target(user_label, sess_num, money, hands_count, money, verification_mode)
                else:
                    composite.on_loss_cut(user_label, sess_num, money, hands_count, money, verification_mode)
            except Exception as e:
                logger.warning(f"Reset notify failed: {e}")
            session.reset_session("利確" if is_win else "損切り")
            send_shoe_history(session.tracker.sets, chip_base)

        # ── Mix自動切替: セット確定後にOS>=20なら1-Dropモードへ ──
        if _bet_mode_box[0] == "mix" and _effective_mode_box[0] == "normal":
            os_val = getattr(session.tracker, 'prev_overshoot', 0)
            if os_val >= 20:
                _effective_mode_box[0] = "1drop"
                send_action(f"OS={os_val} ≥ 20 — switching to 1-Drop mode")
                send_log(f"[mix] Auto-switch to 1-drop (OS={os_val})")
                send_msg({"type": "mode_changed", "mode": "1drop"})

        # Periodic status
        bal = executor.get_balance() if not dry_run else 0
        send_status(session, bal)

        # ── Syncモード: 動的規則性監視（毎ハンドチェック）──
        # シュー切替は一瞬で起きるため即検出が必要
        # 規則性崩壊・ハンド数不足いずれも即退避
        if _effective_mode_box[0] == "sync" and target_tid:
            monitor = check_sync_regularity(target_tid)
            if monitor['should_exit']:
                send_action(f"⚠️ Sync: 規則性崩壊/シュー切替 (reg={monitor['regularity']:.0f} hands={monitor['hands']}) — 退避")
                send_log(f"[Sync-Monitor] ❌ 規則性={monitor['regularity']:.0f} ハンド={monitor['hands']} → 退避判定")
                executor.exit_table()
                import random as _rand_sync
                _wait = _rand_sync.uniform(5, 15)
                send_log(f"[Sync] 🚶 ロビーで{_wait:.0f}秒待機...")
                if stop_event.wait(_wait):
                    break
                if not scraper.get_all_table_configs():
                    try:
                        scraper.setup_ws_intercept()
                    except Exception:
                        pass
                send_action("🔍 次の推奨テーブルを探しています...")
                res_sync = find_sync_table()
                if not res_sync:
                    break
                target_tid, target_name = res_sync
                with scraper._lock:
                    scraper._target_table_ids.add(target_tid)
                    scraper._target_table_names[target_tid] = target_name
                    scraper._new_shoe_signals[target_tid] = False
                    scraper._shoe_epochs[target_tid] = int(time.time())
                send_action(f"🚪 {target_name} に入場中...")
                if not executor.enter_table(target_tid, target_name):
                    send_log("[Sync] ⚠️ 入場失敗 → フルリカバリ")
                    fr = full_recovery()
                    if not fr:
                        break
                    target_tid, target_name = fr
                    if not executor.enter_table(target_tid, target_name):
                        break
                _awaiting_sync_confirm = True  # 新テーブルで再確認
                continue
            else:
                send_log(f"[Sync-Monitor] ✅ 規則性={monitor['regularity']:.0f} ハンド={monitor['hands']} → 継続")

        # ── 1落ちロジック: Player負け（Banker勝ち）→ テーブル退出 → ロビー観察 ──
        # normalモードではBanker負けでも退室せず、そのままテーブルに留まる
        if result.get("result") == "banker" and _effective_mode_box[0] == "1drop":
            send_action("Player lost — returning to lobby for 1-drop re-observation...")
            send_log("[1-drop] Banker won → exit table → observe lobby")
            executor.exit_table()
            # 退室後にランダム待機（10〜25秒）— 人間らしくロビーを眺める時間
            import random as _rand
            _lobby_wait = _rand.uniform(10, 25)
            send_action(f"Browsing lobby... ({_lobby_wait:.0f}s)")
            if stop_event.wait(_lobby_wait):
                break
            if stop_event.is_set():
                break
            # ロビーWS確認
            if not scraper.get_all_table_configs():
                send_log("[1-drop] Lobby WS lost — reconnecting...")
                try:
                    scraper.setup_ws_intercept()
                except Exception:
                    pass
            # 1落ち待機
            if not observe_until_1_drop(target_tid, target_name):
                break  # STOPされた
            # 再入場（3回リトライ）→ 失敗ならテーブル再選定
            _deferred_exit_reason = None  # 前ラウンドの判定を持ち越さない
            _reenter_ok = False
            for _retry in range(3):
                send_action(f"Re-entering {target_name} (attempt {_retry+1}/3)...")
                if executor.enter_table(target_tid, target_name):
                    _reenter_ok = True
                    _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")  # Banker負け再入場 → 2落ち確認必須
                    # テーブル変更後のshoe signalをクリア（誤検出防止）
                    with scraper._lock:
                        scraper._new_shoe_signals[target_tid] = False
                        scraper._shoe_epochs[target_tid] = int(time.time())
                    break
                send_log(f"[1-drop] Entry retry {_retry+1}/3 failed")
                time.sleep(5)
            if not _reenter_ok:
                send_action("Re-entry failed — re-selecting table...")
                send_log("[1-drop] All entry retries failed — re-selecting")
                target_tid = None
                target_name = None
                while not stop_event.is_set() and target_tid is None:
                    best = pick_table()
                    if best:
                        target_tid = best.table_id
                        target_name = best.title
                        with scraper._lock:
                            scraper._target_table_ids.add(target_tid)
                            scraper._target_table_names[target_tid] = target_name
                            if target_tid not in scraper._shoe_epochs:
                                scraper._shoe_epochs[target_tid] = int(time.time())
                                scraper._new_shoe_signals[target_tid] = False
                        send_action(f"Picked: {target_name}")
                    else:
                        send_action("No suitable table — waiting 15s...")
                        if stop_event.wait(15):
                            break
                if stop_event.is_set() or not target_tid:
                    break
                if not observe_until_1_drop(target_tid, target_name):
                    break
                if not executor.enter_table(target_tid, target_name):
                    send_action("New table entry failed — stopping")
                    break
                _awaiting_2nd_drop = (_effective_mode_box[0] == "1drop")  # 新テーブル再入場 → 2落ち確認必須
            continue

        # Deferred exit check: runs during dealing phase (after result, before next BET window)
        # This avoids blocking the BET window with a VPS API call
        if len(session.tracker.current_turns) == 0 and target_tid:
            try:
                _deferred_exit_reason = selector.should_exit_table(target_tid, selector_config=table_filter)
            except Exception as _ec:
                logger.warning(f"Deferred exit check failed: {_ec}")
                _deferred_exit_reason = None

    # === Shutdown ===
    send_action("Stopping...")
    summary = session.get_summary()
    balance = executor.get_balance() if not dry_run else 0
    send_log(
        f"Session ended. Bets:{summary['total_bets']} "
        f"W:{summary['total_wins']} L:{summary['total_losses']} "
        f"P&L:{summary['cumulative_profit']:+d} chips"
    )
    send_action("Closing table...")
    executor.exit_table()
    send_action("Closing browser...")
    scraper.stop()
    send_action("Stopped.")
    try:
        composite.on_shutdown(user_label, "Normal stop")
    except Exception:
        pass
    _active_session = None


# ======== Main ========

def main():
    stop_event = threading.Event()
    skip_event = threading.Event()
    bet_thread = None

    def stdin_reader():
        nonlocal bet_thread
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                msg_type = msg.get("type", "")

                if msg_type == "start":
                    config = msg.get("config", {})
                    if bet_thread is None or not bet_thread.is_alive():
                        stop_event.clear()
                        skip_event.clear()
                        bet_thread = threading.Thread(
                            target=run_bet_session, args=(config, stop_event, skip_event), daemon=True
                        )
                        bet_thread.start()
                        send_log("BET session starting...")

                elif msg_type == "stop":
                    stop_event.set()
                    send_log("Stop requested.")

                elif msg_type == "skip_table":
                    skip_event.set()
                    send_log("Skip table requested by user.")

                elif msg_type == "update_config":
                    # Live update of profit_target / loss_cut
                    cfg = msg.get("config", {})
                    if _active_session is not None:
                        s = _active_session
                        chip_base_val = s.chip_base
                        new_pt_chips = None
                        new_lc_chips = None
                        if "profit_target" in cfg:
                            new_pt = float(cfg["profit_target"])
                            new_pt_chips = max(1, int(round(new_pt / max(chip_base_val, 0.01))))
                            s.profit_stop = new_pt_chips
                            send_log(f"Profit target updated: ${new_pt:.0f} ({new_pt_chips} chips)")
                        if "loss_cut" in cfg:
                            new_lc = float(cfg["loss_cut"])
                            new_lc_chips = max(1, int(round(new_lc / max(chip_base_val, 0.01))))
                            s.loss_cut = new_lc_chips
                            send_log(f"Loss cut updated: ${new_lc:.0f} ({new_lc_chips} chips)")
                        # Sync to remote session if applicable
                        if hasattr(s, "update_config") and hasattr(s, "client"):
                            try:
                                s.update_config(profit_stop=new_pt_chips, loss_cut=new_lc_chips)
                            except Exception as e:
                                send_log(f"Remote config sync failed: {e}")
                    else:
                        # Session not yet initialized, buffer for later
                        _pending_config_update.update(cfg)
                        send_log(f"Config buffered (session starting): {cfg}")

                elif msg_type == "change_mode":
                    new_mode = msg.get("mode", "1drop")
                    if new_mode in ("normal", "1drop", "mix", "sync"):
                        _bet_mode_box[0] = new_mode
                        _effective_mode_box[0] = "normal" if new_mode == "mix" else new_mode
                        send_log(f"BET mode changed to: {new_mode} (effective: {_effective_mode_box[0]})")
                        send_msg({"type": "mode_changed", "mode": new_mode})

                elif msg_type == "get_status":
                    # Status is sent periodically from bet loop
                    pass

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON: {line}")
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                send_msg({"type": "error", "message": str(e)})

    reader_thread = threading.Thread(target=stdin_reader, daemon=True)
    reader_thread.start()

    send_log("LAPLACE Engine ready.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        stop_event.set()


if __name__ == "__main__":
    main()
