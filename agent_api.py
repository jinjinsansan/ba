"""Valhalla II -- Python Agent

Uses the proven BaccaratScraper (scraper.py) directly.
Electron GUI communicates via stdin/stdout JSON IPC.

Flow:
  1. Electron sends {"type":"start", "config":{...}}
  2. This agent launches BaccaratScraper (Camoufox browser)
  3. Scraper handles login, lobby navigation, WS intercept
  4. Results are polled and fed to MaruBatsu logic
  5. Status/results sent to Electron via stdout
"""
import json
import sys
import os
import threading
import time
import logging
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Logging to file only (stdout is for IPC)
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

from marubatsu_strategy import MaruBatsuTracker, SEQ, SetData

PROFIT_STOP = 50
TARGET_TABLE_NAME = "Japanese Speed Baccarat A"


# ======== IPC ========

def send_msg(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

def send_log(text: str):
    send_msg({"type": "log", "message": text})

def send_browser_status(state: str):
    send_msg({"type": "browser_status", "state": state})


# ======== Logic Engine ========

class LogicEngine:
    def __init__(self):
        self.tracker = MaruBatsuTracker(chip_base=1.0)
        self.config = {}
        self.running = False
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0
        self.session_count = 0

    def start(self, config: dict):
        self.config = config
        self.tracker.chip_base = config.get("chip_base", 1.0)
        self.running = True
        send_log(f"Logic engine started. Chip: ${self.tracker.chip_base}, Loss cut: -{config.get('loss_cut', 200)}")

    def stop(self):
        self.running = False

    def on_result(self, result: str):
        if not self.running:
            return
        if result == "tie":
            self.total_ties += 1
            return

        won = (result == "player")
        turn_before = len(self.tracker.current_turns)
        completed_set = self.tracker.add_result(result)

        if won:
            self.total_wins += 1
        else:
            self.total_losses += 1

        send_msg({
            "type": "turn_result",
            "turn_index": turn_before,
            "won": won,
            "result": result,
        })

        if completed_set:
            money_set = completed_set.set_profit * self.tracker.chip_base
            money_cum = completed_set.cumulative_profit * self.tracker.chip_base
            send_msg({
                "type": "set_complete",
                "set_index": completed_set.set_index,
                "wins": completed_set.wins,
                "losses": completed_set.losses,
                "profit": completed_set.set_profit,
                "cumulative_profit": completed_set.cumulative_profit,
                "money_set": money_set,
                "money_cum": money_cum,
            })

        cp = self.tracker.cumulative_profit
        loss_cut = self.config.get("loss_cut", 200)
        if cp >= PROFIT_STOP or cp <= -loss_cut:
            reason = "profit_stop" if cp >= PROFIT_STOP else "loss_cut"
            send_msg({"type": "session_reset", "reason": reason, "profit": cp})
            self.session_count += 1
            self.tracker.sets.clear()
            self.tracker.current_turns.clear()

    def send_status(self):
        send_msg({
            "type": "status",
            "cumulative_profit": self.tracker.cumulative_profit,
            "cumulative_money": self.tracker.cumulative_profit * self.tracker.chip_base,
            "wins": self.total_wins,
            "losses": self.total_losses,
            "ties": self.total_ties,
            "set_count": len(self.tracker.sets),
            "current_turn": len(self.tracker.current_turns),
            "current_unit": SEQ[self.tracker.current_unit_idx],
            "running": self.running,
        })


# ======== Scraper Runner ========

def find_target_table_id(scraper) -> str | None:
    for tid, name in scraper._target_table_names.items():
        if name.strip().lower() == TARGET_TABLE_NAME.lower():
            return tid
    for tid, name in scraper._target_table_names.items():
        if "japanese" in name.lower() and "baccarat a" in name.lower():
            return tid
    return None


def run_scraper(engine: LogicEngine, stop_event: threading.Event):
    """Run BaccaratScraper in a thread. This is the proven, working approach."""
    # Import here to avoid circular imports and ensure config is loaded
    import config as cfg
    cfg.HEADLESS = False
    from scraper import BaccaratScraper

    scraper = BaccaratScraper()
    scraper.table_name = "Japanese Baccarat"

    send_log("Launching browser (Camoufox)...")
    send_browser_status("launching")

    try:
        scraper.start()
    except Exception as e:
        send_log(f"Browser launch failed: {e}")
        logger.error(f"Browser launch failed: {e}", exc_info=True)
        return

    send_log("Browser launched + logged in.")
    send_browser_status("logged_in")

    send_log("Waiting for Evolution WS...")
    scraper.setup_ws_intercept()

    if scraper._evo_ws_connected:
        send_log("Evolution WebSocket connected!")
        send_browser_status("ws_connected")
    else:
        send_log("Warning: Evolution WS not detected. Continuing anyway...")

    # Resolve target table
    send_log("Resolving target table...")
    for _ in range(30):
        if scraper._target_table_ids:
            break
        time.sleep(1)

    target_tid = find_target_table_id(scraper)
    if target_tid:
        name = scraper._target_table_names.get(target_tid, TARGET_TABLE_NAME)
        send_log(f"Monitoring: {name} ({target_tid})")
        send_browser_status("ws_connected")
    else:
        available = list(scraper._target_table_names.values())
        send_log(f"Table '{TARGET_TABLE_NAME}' not found. Available: {available}")

    # Main loop: poll for results (same as run_marubatsu.py)
    while not stop_event.is_set():
        try:
            ws_results = scraper.get_ws_results()
            if ws_results:
                scraper.process_results(ws_results)

                for r in ws_results:
                    result = r.get("result")
                    tid = r.get("table_id", "")

                    if target_tid and tid != target_tid:
                        continue
                    if result not in ("player", "banker", "tie"):
                        continue

                    mark = {"player": "Player", "banker": "Banker", "tie": "Tie"}.get(result, result)
                    tname = scraper._target_table_names.get(tid, tid)
                    send_log(f"Result: {mark} ({tname})")
                    engine.on_result(result)

            # Periodic lobby reload to get fresh results
            # Evolution WS stops sending historyUpdated after a while,
            # but reload_lobby() triggers fresh histories diff
            ws_silent = scraper.seconds_since_last_ws_message()
            if ws_silent > 90:
                logger.info(f"Periodic reload ({int(ws_silent)}s since last WS)")
                scraper.reload_lobby()
                for _ in range(15):
                    if scraper._target_table_ids:
                        break
                    time.sleep(1)
                new_tid = find_target_table_id(scraper)
                if new_tid:
                    target_tid = new_tid

            time.sleep(3)

        except Exception as e:
            logger.error(f"Loop error: {e}", exc_info=True)
            send_log(f"Error: {e}")
            time.sleep(10)

    # Shutdown
    send_log("Stopping browser...")
    try:
        scraper.stop()
    except Exception:
        pass
    send_log("Browser stopped.")


# ======== Main ========

def main():
    engine = LogicEngine()
    stop_event = threading.Event()
    scraper_thread = None

    def stdin_reader():
        nonlocal scraper_thread
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                msg_type = msg.get("type", "")

                if msg_type == "start":
                    engine.start(msg.get("config", {}))
                    if scraper_thread is None or not scraper_thread.is_alive():
                        stop_event.clear()
                        scraper_thread = threading.Thread(
                            target=run_scraper, args=(engine, stop_event), daemon=True
                        )
                        scraper_thread.start()

                elif msg_type == "stop":
                    engine.stop()
                    stop_event.set()

                elif msg_type == "get_status":
                    engine.send_status()

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON: {line}")
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                send_msg({"type": "error", "message": str(e)})

    reader_thread = threading.Thread(target=stdin_reader, daemon=True)
    reader_thread.start()

    send_log("Valhalla II Logic Engine ready.")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, EOFError):
        stop_event.set()
        engine.stop()


if __name__ == "__main__":
    main()
