"""Valhalla II -- Python Agent (BET mode)

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

TARGET_TABLE_NAME = "Japanese Speed Baccarat A"
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
                turn: int, turns_display: str, cumulative_profit: int, cumulative_money: float):
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
        })
    send_msg({"type": "shoe_history", "sets": data, "chip_base": chip_base})


# ======== Table finder ========

def find_target_table_id(scraper) -> str | None:
    for tid, name in scraper._target_table_names.items():
        if name.strip().lower() == TARGET_TABLE_NAME.lower():
            return tid
    for tid, name in scraper._target_table_names.items():
        if "japanese speed baccarat a" in name.lower():
            return tid
    return None


# ======== BET Runner ========

def run_bet_session(config: dict, stop_event: threading.Event):
    """Main BET loop — runs in a thread."""
    import config as cfg
    cfg.HEADLESS = False
    cfg.PROFILE_NAME = "bet"

    from scraper import BaccaratScraper
    from executor import BetExecutor
    from game_ws import GameWSMonitor
    from humanize import Humanizer
    from notify import TelegramNotifier
    from marubatsu_bet import MaruBatsuBetSession, PROFIT_STOP
    from marubatsu_strategy import SEQ

    chip_base = config.get("chip_base", 1.0)
    loss_cut = config.get("loss_cut", 200)
    dry_run = config.get("dry_run", False)

    mode = "DRY RUN" if dry_run else "LIVE"
    send_action(f"Starting {mode} mode...")

    if dry_run:
        notifier = TelegramNotifier("", "")
    else:
        notifier = TelegramNotifier(
            os.getenv("TELEGRAM_BOT_TOKEN", ""),
            os.getenv("TELEGRAM_CHAT_ID", ""),
        )

    # === Browser launch ===
    send_action("Launching browser...")
    scraper = BaccaratScraper()
    scraper.table_name = "Japanese Baccarat"

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

    # === Find table ===
    send_action("Finding target table...")
    for _ in range(30):
        if scraper._target_table_ids:
            break
        time.sleep(1)

    target_tid = find_target_table_id(scraper)
    if not target_tid:
        send_log(f"Table '{TARGET_TABLE_NAME}' not found")
        send_action("Table not found")
        scraper.stop()
        return

    target_name = scraper._target_table_names.get(target_tid, TARGET_TABLE_NAME)
    send_action(f"Table found: {target_name}")

    # === Setup executor ===
    humanizer = Humanizer(cfg.HUMANIZE_CONFIG)
    executor_config = {"demo_mode": dry_run}
    executor = BetExecutor(scraper.page, scraper.game_ws, executor_config, humanizer=humanizer)

    session = MaruBatsuBetSession(
        executor=executor,
        notifier=notifier,
        chip_base=chip_base,
        loss_cut=loss_cut,
        dry_run=dry_run,
    )

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

    while not stop_event.is_set() and round_count < MAX_ROUNDS:
        # Shoe change check
        shoe_signals = scraper.get_new_shoe_signals()
        if target_tid in shoe_signals and shoe_signals[target_tid]:
            send_action("Shoe change detected")
            send_log("Shoe change — partial turns discarded")
            session.handle_shoe_change()

        # BET phase
        unit_idx = session.tracker.current_unit_idx
        unit = SEQ[unit_idx]
        bet_amount = unit * chip_base
        turn_num = len(session.tracker.current_turns) + 1
        send_action(f"Waiting for BET phase... (Turn {turn_num}/7, ${bet_amount:.0f})")

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
                    send_action("3 entry failures — restarting browser...")
                    try:
                        scraper.stop()
                    except Exception:
                        pass
                    time.sleep(3)
                    scraper = BaccaratScraper()
                    scraper.table_name = "Japanese Baccarat"
                    scraper.start()
                    scraper.setup_ws_intercept()
                    for _ in range(30):
                        if scraper._target_table_ids:
                            break
                        time.sleep(1)
                    executor = BetExecutor(scraper.page, scraper.game_ws, executor_config, humanizer=humanizer)
                    session.executor = executor
                    target_tid = find_target_table_id(scraper) or target_tid
                    entry_fail_count = 0
                    if not executor.enter_table(target_tid, target_name):
                        send_action("Failed after browser restart — stopping")
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

            if res == "tie":
                send_action(f"Tie — BET returned. Balance: ${bal:.2f}")
            elif won:
                send_action(f"WIN! Player ${ba:.0f}. Balance: ${bal:.2f}")
            else:
                send_action(f"LOSE. Banker won. Balance: ${bal:.2f}")

            send_result(res, won, ba, bal, len(turns), turns_disp, cp, cm)

        # Set complete
        if result.get("completed_set"):
            s = result["completed_set"]
            send_set_complete(s, chip_base)
            send_shoe_history(session.tracker.sets, chip_base)
            send_action(f"Set #{s.set_index} done: {s.wins}W/{s.losses}L, P&L: {s.set_profit:+d}")

        # Profit/loss reset
        if result.get("should_reset"):
            cp = session.tracker.cumulative_profit
            reason = "Profit target" if cp >= PROFIT_STOP else "Loss cut"
            send_action(f"{reason} reached ({cp:+d} chips) — resetting...")
            session.reset_session("利確" if cp >= PROFIT_STOP else "損切り")
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


# ======== Main ========

def main():
    stop_event = threading.Event()
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
                        bet_thread = threading.Thread(
                            target=run_bet_session, args=(config, stop_event), daemon=True
                        )
                        bet_thread.start()
                        send_log("BET session starting...")

                elif msg_type == "stop":
                    stop_event.set()
                    send_log("Stop requested.")

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

    send_log("Valhalla II Engine ready.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        stop_event.set()


if __name__ == "__main__":
    main()
