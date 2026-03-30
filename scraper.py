"""Stake.com Evolution バカラ スクレイパー (ロビーWS方式)

EvolutionロビーのWebSocketから全バカラテーブルの結果をリアルタイム監視。
テーブル個別ページに入る必要なし — ロビーに留まるだけで全テーブルのデータが取得可能。

データソース:
  - lobby.configs: テーブルID→テーブル名マッピング
  - lobby.histories: 初期履歴（全テーブル分）
  - lobby.historyUpdated: リアルタイム結果更新

Camoufoxを使用してCloudflare Turnstileを回避する。
"""
import json
import os
import re
import time
import logging
import threading
from datetime import datetime, timezone, timedelta

from camoufox.sync_api import Camoufox
from playwright.sync_api import Page, WebSocket

import config
from db import insert_round
from telegram_auth import ask_email_code

logger = logging.getLogger("baccarat.scraper")

JST = timezone(timedelta(hours=9))

# Evolution Big Road の色マッピング
# B = Blue = Player, R = Red = Banker
EVO_COLOR_MAP = {"B": "player", "R": "banker"}


class BaccaratScraper:
    """Stake.com EvolutionロビーWSを経由してバカラ結果を監視"""

    def __init__(self):
        self._camoufox_ctx = None
        self.browser = None
        self.page: Page | None = None
        self.table_name = config.TARGET_TABLE or ""
        self.round_count = 0
        self.last_round_id = ""
        self._ws_results: list[dict] = []
        self._lock = threading.Lock()

        # Evolution テーブル管理
        self._evo_table_configs: dict[str, dict] = {}  # table_id → config
        self._evo_table_histories: dict[str, list] = {}  # table_id → last known history
        self._evo_ws_connected = False
        self._last_ws_message_time: float = 0.0
        self._consecutive_reload_fails: int = 0

        # マルチテーブル監視
        self._target_table_ids: set[str] = set()  # 監視対象テーブルID群
        self._target_table_names: dict[str, str] = {}  # table_id → table_name
        self._shoe_epochs: dict[str, int] = {}  # table_id → shoe epoch
        self._new_shoe_signals: dict[str, bool] = {}  # table_id → signal

        # 後方互換用
        self._target_table_id: str = ""

    @staticmethod
    def _resolve_executable_path() -> str | None:
        """Windows Store版Python対応: realpathでCamoufox実行パスを解決"""
        try:
            from camoufox.pkgman import get_path, LAUNCH_FILE, OS_NAME
            path = get_path(LAUNCH_FILE[OS_NAME])
            real = os.path.realpath(path)
            if real != path and os.path.isfile(real):
                logger.info(f"Camoufox実行パス解決: {real}")
                return real
        except Exception:
            pass
        return None

    def start(self):
        """ブラウザ起動 → ログイン → WS傍受設定 → ロビーに移動"""
        logger.info("Camoufox起動中...")
        exe_path = self._resolve_executable_path()
        launch_opts = {"headless": config.HEADLESS}
        if exe_path:
            launch_opts["executable_path"] = exe_path
        self._camoufox_ctx = Camoufox(**launch_opts)
        self.browser = self._camoufox_ctx.__enter__()
        self.page = self.browser.new_page()

        # Cookie復元
        self._restore_cookies()

        # ログイン
        self._login()

        # ★ ロビーナビゲーション前にWSリスナーを登録
        # ロビーページロード時にEvolution WSが接続されるため、先に登録する必要がある
        self._register_ws_listener()

        # バカラロビーに移動（テーブルに入らない）
        self._navigate_to_lobby()

    def _restore_cookies(self):
        """保存済みCookieを復元"""
        cookie_file = config.AUTH_STATE_DIR / "stake_cookies.json"
        if not cookie_file.exists():
            logger.info("保存済みCookieなし")
            return
        try:
            with open(cookie_file) as f:
                cookies = json.load(f)
            self.page.context.add_cookies(cookies)
            logger.info(f"Cookie復元: {len(cookies)}件")
        except Exception as e:
            logger.warning(f"Cookie復元失敗: {e}")

    def _login(self):
        """Stake.comにログイン"""
        logger.info("Stakeにアクセス中...")
        self.page.goto(config.STAKE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "after_goto.png"))
        logger.info(f"ページタイトル: {self.page.title()}")

        if self._is_logged_in():
            logger.info("すでにログイン済み")
            return

        # ログインフォームを開く
        logger.info("ログインフォームを開く...")
        try:
            login_link = self.page.locator(
                'a:has-text("Login"), '
                'button:has-text("Login"), '
                'a:has-text("Sign in"), '
                'button:has-text("Sign in"), '
                'a:has-text("Sign In"), '
                'button:has-text("Sign In")'
            )
            if login_link.count() > 0:
                login_link.first.click()
                time.sleep(3)
        except Exception as e:
            logger.warning(f"ログインリンク検索: {e}")

        # メールアドレス入力
        logger.info("認証情報を入力中...")
        email_input = self.page.locator(
            'input[name="email"], input[type="email"], '
            'input[placeholder*="mail" i], input[placeholder*="Email"]'
        )
        if email_input.count() > 0:
            email_input.first.fill(config.STAKE_USERNAME)
        else:
            inputs = self.page.locator('input[type="text"], input:not([type])')
            if inputs.count() > 0:
                inputs.first.fill(config.STAKE_USERNAME)
        time.sleep(0.5)

        # パスワード入力
        pw_input = self.page.locator('input[type="password"]')
        if pw_input.count() > 0:
            pw_input.first.fill(config.STAKE_PASSWORD)
        time.sleep(0.5)

        # ログインボタン送信
        submit = self.page.locator(
            'button[type="submit"], '
            'button:has-text("Sign in"), '
            'button:has-text("Log in"), '
            'button:has-text("Login")'
        )
        if submit.count() > 0:
            submit.first.click()
        time.sleep(5)

        # Email Code（2FA）
        if not self._is_logged_in():
            self._handle_email_code()

        if self._is_logged_in():
            logger.info("ログイン成功")
            self._save_cookies()
        else:
            logger.warning("ログイン状態が不明（続行を試みます）")

    def _handle_email_code(self):
        """Email Code（2FA）画面を検出し、Telegram経由でコードを取得して入力"""
        logger.info("Email Code画面を確認中...")
        code_input = self.page.locator(
            'input[placeholder*="Code" i], '
            'input[name*="code" i], '
            'input[placeholder*="code" i]'
        )
        if code_input.count() == 0:
            try:
                body_text = self.page.locator("body").inner_text()[:500]
                if "email code" in body_text.lower() or "verification" in body_text.lower():
                    code_input = self.page.locator('input[type="text"]:visible')
                else:
                    return
            except Exception:
                return

        if code_input.count() == 0:
            return

        logger.info("📱 Telegram Bot経由でメール認証コードを待機中...")
        email_code = ask_email_code(timeout=300)
        if not email_code:
            logger.error("認証コードが取得できませんでした")
            return

        code_input.first.fill(email_code)
        time.sleep(0.5)

        submit = self.page.locator(
            'button:has-text("Sign in"), '
            'button:has-text("Sign In"), '
            'button[type="submit"]'
        )
        if submit.count() > 0:
            submit.first.click()
        time.sleep(8)

    def _save_cookies(self):
        """現在のCookieを保存"""
        try:
            cookie_file = config.AUTH_STATE_DIR / "stake_cookies.json"
            cookies = self.page.context.cookies()
            with open(cookie_file, "w") as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Cookie保存: {len(cookies)}件 → {cookie_file}")
        except Exception as e:
            logger.warning(f"Cookie保存エラー: {e}")

    def _is_logged_in(self) -> bool:
        """ログイン状態を確認"""
        try:
            indicators = self.page.locator(
                '[data-test="balance"], '
                'button:has-text("Wallet"), '
                '[class*="balance"], '
                '[class*="user-menu"]'
            )
            return indicators.count() > 0
        except Exception:
            return False

    def _navigate_to_lobby(self):
        """バカラロビーに移動（テーブルに入らない）"""
        logger.info("バカラロビーに移動中...")
        self.page.goto(
            config.BACCARAT_LOBBY_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )
        time.sleep(8)

        # Cookieバナーがあれば閉じる
        try:
            accept_btn = self.page.locator('button:has-text("Accept")')
            if accept_btn.count() > 0 and accept_btn.first.is_visible():
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "baccarat_lobby.png"))
        logger.info(f"バカラロビー到着 — タイトル: {self.page.title()}")

    def _register_ws_listener(self):
        """WebSocketリスナーを登録（ナビゲーション前に呼ぶこと）"""
        logger.info("WebSocket傍受を設定中...")

        def on_ws(ws: WebSocket):
            url = ws.url
            logger.info(f"WebSocket接続検出: {url[:120]}")

            # EvolutionロビーWSのみ対象
            if "evo-games.com" in url or "evolution" in url.lower():
                logger.info(f"✅ EvolutionロビーWS検出: {url[:120]}")
                self._evo_ws_connected = True

                def on_message(data):
                    payload = data.get("payload", data) if isinstance(data, dict) else data
                    self._handle_evo_lobby_message(str(payload))

                def on_sent(data):
                    payload = data.get("payload", data) if isinstance(data, dict) else data
                    text = str(payload)[:200]
                    logger.debug(f"WS送信: {text}")

                def on_close():
                    logger.warning("❌ EvolutionロビーWS切断")
                    self._evo_ws_connected = False

                ws.on("framereceived", on_message)
                ws.on("framesent", on_sent)
                ws.on("close", on_close)

        self.page.on("websocket", on_ws)
        logger.info("WebSocket傍受設定完了")

    def setup_ws_intercept(self):
        """EvolutionロビーWSの接続を待機する（後方互換性のため残す）

        start()内で _register_ws_listener() → _navigate_to_lobby() の順で
        呼ばれるため、ここでは接続待機のみ行う。
        """
        # ロビーWSが接続されるまで待つ（最大30秒）
        for _ in range(30):
            if self._evo_ws_connected:
                logger.info("EvolutionロビーWS接続確認 ✅")
                break
            time.sleep(1)
        else:
            logger.warning("EvolutionロビーWSが検出されませんでした — ページをリロードして再試行")
            self.page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(10)
            # リロード後にもう一度待機
            for _ in range(30):
                if self._evo_ws_connected:
                    logger.info("EvolutionロビーWS接続確認（リロード後）✅")
                    break
                time.sleep(1)
            else:
                logger.error("EvolutionロビーWSが接続できませんでした")

    def _handle_evo_lobby_message(self, payload: str):
        """EvolutionロビーWSメッセージを処理"""
        self._last_ws_message_time = time.time()
        try:
            if not isinstance(payload, str) or len(payload) < 10:
                return

            data = json.loads(payload)
            msg_type = data.get("type", "")
            args = data.get("args", {})

            if msg_type == "lobby.configs":
                self._process_configs(args)
            elif msg_type == "lobby.histories":
                self._process_histories(args)
            elif msg_type == "lobby.historyUpdated":
                self._process_history_updated(args)
            elif msg_type == "lobby.configsUpdated":
                self._process_configs_updated(args)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"EvolutionロビーWS解析エラー: {e}")

    def _process_configs(self, args: dict):
        """lobby.configs → テーブルID→設定マッピングを構築"""
        configs = args.get("configs", {})
        baccarat_tables = []

        for table_id, cfg in configs.items():
            gt = cfg.get("gt", "")
            # バカラ系テーブルのみ記録
            if gt in ("baccarat",):
                self._evo_table_configs[table_id] = cfg
                title = cfg.get("title", table_id)
                baccarat_tables.append(f"{title} ({table_id})")

        logger.info(f"Evolutionバカラテーブル: {len(baccarat_tables)}件検出")
        for t in baccarat_tables[:20]:
            logger.debug(f"  {t}")

        # ターゲットテーブルIDを決定
        self._resolve_target_table()

    def _process_configs_updated(self, args: dict):
        """lobby.configsUpdated → テーブル設定の差分更新"""
        configs = args.get("configs", {})
        for table_id, cfg in configs.items():
            gt = cfg.get("gt", "")
            if gt in ("baccarat",):
                self._evo_table_configs[table_id] = cfg

    def _resolve_target_table(self):
        """ターゲットテーブルを解決 — Japanese系は全テーブルをマッチ"""
        target_name = self.table_name.lower().strip()
        self._target_table_ids.clear()
        self._target_table_names.clear()

        for tid, cfg in self._evo_table_configs.items():
            title = cfg.get("title", "")
            title_lower = title.lower()

            # Japanese系テーブルを全てマッチ
            if target_name and all(w in title_lower for w in target_name.split()):
                self._target_table_ids.add(tid)
                self._target_table_names[tid] = title
                if tid not in self._shoe_epochs:
                    self._shoe_epochs[tid] = int(time.time())
                    self._new_shoe_signals[tid] = False

        # 後方互換: 最初のテーブルを代表として設定
        if self._target_table_ids:
            first_id = next(iter(self._target_table_ids))
            self._target_table_id = first_id
            logger.info(
                f"ターゲットテーブル {len(self._target_table_ids)}件マッチ: "
                + ", ".join(
                    f"{self._target_table_names[t]} ({t})"
                    for t in sorted(self._target_table_ids)
                )
            )
        else:
            logger.warning(f"ターゲットテーブル '{self.table_name}' が見つかりません")
            for tid, cfg in list(self._evo_table_configs.items())[:10]:
                logger.info(f"  利用可能: {cfg.get('title', tid)} ({tid})")

    def _process_histories(self, args: dict):
        """lobby.histories → 全ターゲットテーブルの差分チェック"""
        histories = args.get("histories", {})

        for table_id, hist_data in histories.items():
            new_results = hist_data.get("results", [])

            if table_id in self._target_table_ids:
                old_results = self._evo_table_histories.get(table_id, [])
                tname = self._target_table_names.get(table_id, table_id)

                if old_results and new_results and len(new_results) < len(old_results) - 5:
                    self._shoe_epochs[table_id] = int(time.time())
                    self._new_shoe_signals[table_id] = True
                    logger.info(f"シューリセット検出 (histories): {tname} {len(old_results)}→{len(new_results)}")

                added = self._diff_results(old_results, new_results)
                if added:
                    for entry in added:
                        result_info = self._parse_evo_bead_entry(entry, table_id)
                        if result_info:
                            with self._lock:
                                self._ws_results.append(result_info)

            self._evo_table_histories[table_id] = new_results

        for tid in self._target_table_ids:
            hist = self._evo_table_histories.get(tid, [])
            tname = self._target_table_names.get(tid, tid)
            logger.info(f"履歴ロード: {tname} ({tid}) — {len(hist)}件")

    def _process_history_updated(self, args: dict):
        """lobby.historyUpdated → 全ターゲットテーブルのリアルタイム更新"""
        for table_id, update_data in args.items():
            if table_id not in self._target_table_ids:
                continue

            new_results = update_data.get("results", [])
            if not new_results:
                continue

            old_results = self._evo_table_histories.get(table_id, [])
            tname = self._target_table_names.get(table_id, table_id)

            if old_results and len(new_results) < len(old_results) - 5:
                self._shoe_epochs[table_id] = int(time.time())
                self._new_shoe_signals[table_id] = True
                logger.info(f"シューリセット検出 (historyUpdated): {tname} {len(old_results)}→{len(new_results)}")

            added = self._diff_results(old_results, new_results)
            self._evo_table_histories[table_id] = new_results

            if added:
                for entry in added:
                    result_info = self._parse_evo_bead_entry(entry, table_id)
                    if result_info:
                        with self._lock:
                            self._ws_results.append(result_info)

    def _diff_results(self, old: list, new: list) -> list:
        """前回と今回の履歴を比較して新しいエントリを返す"""
        if not old:
            return []

        if not new:
            return []

        old_len = len(old)
        new_len = len(new)
        added = []

        # シューリセット: 履歴が大幅縮小 → 新しい結果を全て返す
        if new_len < old_len - 5:
            added.extend(new)
        # 新しいエントリが追加された場合
        elif new_len > old_len:
            added.extend(new[old_len:])

        # 既存エントリのTie更新をチェック（直近数エントリのみ）
        overlap_end = min(old_len, new_len)
        if overlap_end > 0:
            check_start = max(0, overlap_end - 3)
            for i in range(check_start, overlap_end):
                old_entry = old[i]
                new_entry = new[i]
                if isinstance(old_entry, dict) and isinstance(new_entry, dict):
                    old_ties = old_entry.get("ties", 0)
                    new_ties = new_entry.get("ties", 0)
                    if new_ties > old_ties:
                        tie_entry = dict(new_entry)
                        tie_entry["_is_tie_update"] = True
                        tie_entry["_tie_count"] = new_ties - old_ties
                        added.append(tie_entry)

        return added

    def _parse_evo_bead_entry(self, entry: dict | str, table_id: str) -> dict | None:
        """Evolution Big Road/BeadのエントリからResult情報を抽出"""
        # BacBo形式（文字列リスト）
        if isinstance(entry, str):
            mapping = {"player": "player", "banker": "banker", "tie": "tie"}
            result = mapping.get(entry.lower())
            if result:
                return {
                    "round_id": f"evo_{table_id}_{int(time.time()*1000)}",
                    "result": result,
                    "player_score": None,
                    "banker_score": None,
                    "player_pair": False,
                    "banker_pair": False,
                }
            return None

        if not isinstance(entry, dict):
            return None

        pos = entry.get("pos", [0, 0])

        shoe_epoch = self._shoe_epochs.get(table_id, int(time.time()))
        tname = self._target_table_names.get(table_id, table_id)

        # Tie更新の場合 — 結果を "tie" として返す
        if entry.get("_is_tie_update"):
            ties = entry.get("ties", 1)
            round_id = f"evo_{table_id}_s{shoe_epoch}_c{pos[0]}r{pos[1]}_t{ties}"
            return {
                "round_id": round_id,
                "result": "tie",
                "table_id": table_id,
                "table_name": tname,
                "player_score": None,
                "banker_score": None,
                "player_pair": False,
                "banker_pair": False,
            }

        # Big Road形式: {"pos":[col,row], "s":score, "c":"B"/"R", ...}
        color = entry.get("c", "")
        result = EVO_COLOR_MAP.get(color)

        if not result:
            return None

        score = entry.get("s")
        pp = bool(entry.get("pp"))
        bp = bool(entry.get("bp"))
        nat = bool(entry.get("nat"))

        round_id = f"evo_{table_id}_s{shoe_epoch}_c{pos[0]}r{pos[1]}"

        result_info = {
            "round_id": round_id,
            "result": result,
            "table_id": table_id,
            "table_name": tname,
            "player_score": score if result == "player" else None,
            "banker_score": score if result == "banker" else None,
            "player_pair": pp,
            "banker_pair": bp,
            "natural": nat,
            "ties": entry.get("ties", 0),
        }

        return result_info

    def _format_entry_short(self, entry) -> str:
        """結果エントリを短い表示形式に変換"""
        if isinstance(entry, str):
            mapping = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}
            return mapping.get(entry.lower(), "?")

        if isinstance(entry, dict):
            color = entry.get("c", "")
            score = entry.get("s", "?")
            ties = entry.get("ties", 0)
            emoji = {"B": "🔵P", "R": "🔴B"}.get(color, "?")
            tie_str = f"+🟢T×{ties}" if ties else ""
            return f"{emoji}({score}){tie_str}"

        return "?"

    def get_ws_results(self) -> list[dict]:
        """WebSocket経由で受信した未処理の結果を取得"""
        with self._lock:
            results = list(self._ws_results)
            self._ws_results.clear()
        return results

    def get_new_shoe_signals(self) -> dict[str, bool]:
        """新シュー信号があるテーブルをチェックして消費する"""
        signals = {}
        for tid, sig in self._new_shoe_signals.items():
            if sig:
                signals[tid] = True
                self._new_shoe_signals[tid] = False
        return signals

    def has_new_shoe_signal(self) -> bool:
        """後方互換: いずれかのテーブルで新シュー信号があるか"""
        return any(self._new_shoe_signals.values())

    def process_results(self, results: list[dict]) -> int:
        """結果をDBに保存。新規挿入数を返す"""
        new_count = 0
        for r in results:
            round_id = r.get("round_id", "")
            if not round_id or round_id == self.last_round_id:
                continue

            tname = r.get("table_name", self.table_name)
            inserted = insert_round(
                table_name=tname,
                round_id=round_id,
                result=r["result"],
                player_pair=r.get("player_pair", False),
                banker_pair=r.get("banker_pair", False),
                player_score=r.get("player_score"),
                banker_score=r.get("banker_score"),
            )
            if inserted:
                new_count += 1
                self.last_round_id = round_id
                self.round_count += 1
                emoji = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}.get(r["result"], "?")
                logger.info(
                    f"Round #{self.round_count}: {emoji} "
                    f"[{tname}] id={round_id}"
                )

        return new_count

    def poll_dom_results(self) -> list[dict]:
        """DOM経由の結果取得（ロビーWS方式では不要だが互換性のため残す）"""
        return []

    def take_screenshot(self, name: str = "current"):
        """デバッグ用スクリーンショット"""
        try:
            path = config.SCREENSHOTS_DIR / f"{name}.png"
            self.page.screenshot(path=str(path))
            logger.debug(f"スクリーンショット: {path}")
        except Exception as e:
            logger.error(f"スクリーンショットエラー: {e}")

    def seconds_since_last_ws_message(self) -> float:
        """最後にWSメッセージを受信してからの経過秒数"""
        if self._last_ws_message_time == 0:
            return 999
        return time.time() - self._last_ws_message_time

    def reload_lobby(self):
        """ロビーページをリロードしてWS再接続する

        リロード後は必ず _last_ws_message_time をリセットし、
        連続リロードループを防止する。
        3回連続失敗時はフルナビゲーションで復帰を試みる。
        """
        # 連続失敗3回以上 → フルナビゲーション
        if self._consecutive_reload_fails >= 3:
            return self._full_navigate_lobby()

        try:
            self._evo_ws_connected = False
            self.page.reload(wait_until="commit", timeout=15000)
            time.sleep(3)

            for _ in range(15):
                if self._evo_ws_connected:
                    self._consecutive_reload_fails = 0
                    logger.info("ロビーリロード後 WS再接続成功 ✅")
                    return True
                time.sleep(1)

            self._consecutive_reload_fails += 1
            logger.warning(f"ロビーリロード後もWS未接続 (連続失敗: {self._consecutive_reload_fails})")
        except Exception as e:
            self._consecutive_reload_fails += 1
            logger.warning(f"ロビーリロードエラー: {e} (連続失敗: {self._consecutive_reload_fails})")
            time.sleep(3)

        # 成功・失敗に関わらずタイムスタンプをリセット（連続リロード防止）
        self._last_ws_message_time = time.time()
        return self._evo_ws_connected

    def _full_navigate_lobby(self):
        """フルナビゲーションでロビーに再移動（リロード連続失敗時の復帰策）"""
        logger.info("フルナビゲーションでロビー復帰を試行...")
        try:
            self._evo_ws_connected = False
            self.page.goto(
                config.BACCARAT_LOBBY_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            time.sleep(8)

            for _ in range(20):
                if self._evo_ws_connected:
                    self._consecutive_reload_fails = 0
                    logger.info("フルナビゲーション後 WS再接続成功 ✅")
                    # テーブルID再解決を待つ
                    for _ in range(15):
                        if self._target_table_ids:
                            break
                        time.sleep(1)
                    self._last_ws_message_time = time.time()
                    return True
                time.sleep(1)

            self._consecutive_reload_fails += 1
            logger.error(f"フルナビゲーション後もWS未接続 (連続失敗: {self._consecutive_reload_fails})")
        except Exception as e:
            self._consecutive_reload_fails += 1
            logger.error(f"フルナビゲーションエラー: {e}")

        self._last_ws_message_time = time.time()
        return False

    def is_alive(self) -> bool:
        """ブラウザセッションが生きているか"""
        try:
            self.page.evaluate("1 + 1")
            return self._evo_ws_connected
        except Exception:
            return False

    def stop(self):
        """ブラウザを閉じる"""
        try:
            if self._camoufox_ctx:
                self._camoufox_ctx.__exit__(None, None, None)
                self._camoufox_ctx = None
        except Exception as e:
            logger.error(f"停止エラー: {e}")
        logger.info("スクレイパー停止")
