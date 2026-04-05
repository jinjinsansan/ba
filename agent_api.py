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

MAX_ROUNDS = 9999


# ======== IPC ========

def send_msg(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

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
    global _active_session, _pending_config_update
    """Main BET loop — runs in a thread."""
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

    # Setup 3-tier notifier system
    public_notifier = PublicNotifier()  # reads PUBLIC_BOT_TOKEN / PUBLIC_CHANNEL_ID from env
    admin_notifier = AdminNotifier()  # reads ADMIN_BOT_TOKEN / ADMIN_CHAT_ID from env
    if dry_run:
        user_notifier = UserNotifier("", "")
    else:
        user_notifier = UserNotifier()  # reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from env
    composite = CompositeNotifier(public_notifier, admin_notifier, user_notifier)
    # Legacy alias: existing code uses `notifier` with .send(), .notify_*() — use UserNotifier
    notifier = user_notifier

    def pick_table():
        """Verification modeなら固定テーブル、それ以外は通常選定"""
        if verification_mode:
            return selector.find_best_table(fixed_name=fixed_table_name)
        return selector.find_best_table()

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
            best = selector.find_best_table(fixed_name=fixed_table_name)
        else:
            send_action("Selecting best table...")
            best = selector.find_best_table()
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

    # === Enter table ===
    send_action(f"Entering table: {target_name}...")
    if not executor.enter_table(target_tid, target_name):
        send_log("Table entry failed")
        send_action("Table entry failed")
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

    while not stop_event.is_set() and round_count < MAX_ROUNDS:
        # Shoe change check
        shoe_signals = scraper.get_new_shoe_signals()
        if target_tid in shoe_signals and shoe_signals[target_tid]:
            send_action("Shoe change detected")
            send_log("Shoe change — partial turns discarded")
            session.handle_shoe_change()

        # Session break (anti-bot)
        if len(session.tracker.current_turns) == 0:
            minutes_elapsed = (time.time() - session_start) / 60
            if humanizer.should_take_break(minutes_elapsed):
                break_sec = humanizer.get_break_duration()
                send_action(f"Taking a break ({break_sec/60:.1f} min)...")
                send_log(f"Anti-bot break: {break_sec/60:.1f} min")
                executor.exit_table()
                if stop_event.wait(break_sec):
                    break
                session_start = time.time()
                # 休憩後は再選定
                send_action("Break finished — re-selecting table...")
                target_tid = None
                while not stop_event.is_set() and target_tid is None:
                    best = pick_table()
                    if best:
                        target_tid = best.table_id
                        target_name = best.title
                        send_action(f"Picked: {target_name}")
                    else:
                        if stop_event.wait(15):
                            break
                if stop_event.is_set():
                    break
                with scraper._lock:
                    scraper._target_table_ids.add(target_tid)
                    scraper._target_table_names[target_tid] = target_name
                if not executor.enter_table(target_tid, target_name):
                    send_action("Re-entry after break failed")
                    continue

        # User-requested skip takes precedence (only between sets)
        user_skip = False
        if skip_event is not None and skip_event.is_set() and len(session.tracker.current_turns) == 0:
            user_skip = True
            skip_event.clear()

        # Condition check (only when not in the middle of a set)
        if len(session.tracker.current_turns) == 0:
            exit_reason = "User requested skip" if user_skip else selector.should_exit_table(target_tid)
            if exit_reason:
                send_action(f"Table conditions broke: {exit_reason} — exiting...")
                send_log(f"Leaving {target_name}: {exit_reason}")
                executor.exit_table()
                time.sleep(3)

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

                send_action(f"Entering {target_name}...")
                if not executor.enter_table(target_tid, target_name):
                    send_action("Entry failed — retrying...")
                    time.sleep(5)
                    continue

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
                continue
            else:
                entry_fail_count += 1
                if entry_fail_count >= 3:
                    send_action("3 entry failures — re-selecting table...")
                    best = pick_table()
                    if best:
                        target_tid = best.table_id
                        target_name = best.title
                        with scraper._lock:
                            scraper._target_table_ids.add(target_tid)
                            scraper._target_table_names[target_tid] = target_name
                        entry_fail_count = 0
                    else:
                        send_action("No alternative table — stopping")
                        break
                else:
                    time.sleep(10)
                    continue

        round_count += 1

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

        # Periodic status
        bal = executor.get_balance() if not dry_run else 0
        send_status(session, bal)

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
