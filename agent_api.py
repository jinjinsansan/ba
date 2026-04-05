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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    from marubatsu_strategy import SEQ
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
    global _active_session, _pending_config_update
    """Main BET loop — runs in a thread."""
    import config as cfg
    cfg.HEADLESS = False
    cfg.PROFILE_NAME = "bet"

    from scraper import BaccaratScraper
    from executor import BetExecutor
    from game_ws import GameWSMonitor
    from humanize import Humanizer
    from notify import TelegramNotifier, PublicNotifier, AdminNotifier, UserNotifier, CompositeNotifier
    from marubatsu_bet import MaruBatsuBetSession
    from marubatsu_strategy import SEQ
    from table_selector import TableSelector

    chip_base = config.get("chip_base", 1.0)
    profit_target_dollars = config.get("profit_target", 50)
    loss_cut_dollars = config.get("loss_cut", 200)
    dry_run = config.get("dry_run", False)
    resume = config.get("resume", False)
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

    selector = TableSelector(scraper)
    humanizer = Humanizer(cfg.HUMANIZE_CONFIG)
    executor_config = {"demo_mode": dry_run}
    executor = BetExecutor(scraper.page, scraper.game_ws, executor_config, humanizer=humanizer)

    session = MaruBatsuBetSession(
        executor=executor,
        notifier=notifier,
        chip_base=chip_base,
        loss_cut=loss_cut_chips,
        profit_stop=profit_stop_chips,
        dry_run=dry_run,
        resume=resume,
    )
    _active_session = session

    # Apply any pending config updates received before session creation
    if _pending_config_update:
        pending = _pending_config_update
        _pending_config_update = {}
        if "profit_target" in pending:
            new_pt = float(pending["profit_target"])
            session.profit_stop = max(1, int(round(new_pt / max(chip_base, 0.01))))
            send_log(f"Applied pending profit target: ${new_pt:.0f} ({session.profit_stop} chips)")
        if "loss_cut" in pending:
            new_lc = float(pending["loss_cut"])
            session.loss_cut = max(1, int(round(new_lc / max(chip_base, 0.01))))
            send_log(f"Applied pending loss cut: ${new_lc:.0f} ({session.loss_cut} chips)")

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

        # BET phase
        unit_idx = session.tracker.current_unit_idx
        unit = SEQ[unit_idx]
        bet_amount = unit * chip_base
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
                        chip_base = s.chip_base
                        if "profit_target" in cfg:
                            new_pt = float(cfg["profit_target"])
                            s.profit_stop = max(1, int(round(new_pt / max(chip_base, 0.01))))
                            send_log(f"Profit target updated: ${new_pt:.0f} ({s.profit_stop} chips)")
                        if "loss_cut" in cfg:
                            new_lc = float(cfg["loss_cut"])
                            s.loss_cut = max(1, int(round(new_lc / max(chip_base, 0.01))))
                            send_log(f"Loss cut updated: ${new_lc:.0f} ({s.loss_cut} chips)")
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
