import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import time

BASE_DIR = r"C:\dev\ba"
GUI_DIR = os.path.join(BASE_DIR, "gui")
LOG_PATH = os.path.join(BASE_DIR, "agent.log")
WATCHDOG_LOG_PATH = os.path.join(BASE_DIR, "cloud_scripts", "watchdog.log")
PID_PATH = os.path.join(BASE_DIR, "cloud_scripts", "watchdog.pid")
RUN_BAT = os.path.join(BASE_DIR, "cloud_scripts", "run.bat")
PROCESS_NAME = "electron.exe"
CHECK_INTERVAL = 30
STALE_SECONDS = 3 * 60
RESTART_COOLDOWN = 60
NOFRAME_WINDOW = 5 * 60
NOFRAME_LIMIT = 3
BROWSER_CLOSED_LIMIT = 3


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("laplace_watchdog")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [watchdog] %(levelname)s: %(message)s")
    file_handler = RotatingFileHandler(
        WATCHDOG_LOG_PATH,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def is_pid_running(pid: int) -> bool:
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}"],
            text=True,
            errors="ignore",
        )
        return str(pid) in output
    except Exception:
        return False


def acquire_lock(logger: logging.Logger) -> bool:
    if os.path.exists(PID_PATH):
        try:
            with open(PID_PATH, "r", encoding="utf-8") as f:
                pid = int(f.read().strip() or 0)
            if pid and is_pid_running(pid):
                logger.warning("watchdog already running (pid=%s) - exiting", pid)
                return False
        except Exception:
            pass
    try:
        with open(PID_PATH, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception as exc:
        logger.warning("failed to write pid file: %s", exc)
    return True


def release_lock(logger: logging.Logger) -> None:
    try:
        if os.path.exists(PID_PATH):
            os.remove(PID_PATH)
            logger.info("watchdog pid file removed")
    except Exception as exc:
        logger.warning("failed to remove pid file: %s", exc)


def is_process_running() -> bool:
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {PROCESS_NAME}"],
            text=True,
            errors="ignore",
        )
        return PROCESS_NAME.lower() in output.lower()
    except Exception:
        return False


def log_stale() -> bool:
    try:
        mtime = os.path.getmtime(LOG_PATH)
        return (time.time() - mtime) > STALE_SECONDS
    except Exception:
        return False


def find_agent_pids() -> list[int]:
    try:
        output = subprocess.check_output(
            [
                "wmic",
                "process",
                "where",
                "CommandLine like '%agent_api.py%'",
                "get",
                "ProcessId,CommandLine",
            ],
            text=True,
            errors="ignore",
        )
        pids = []
        for line in output.splitlines():
            line = line.strip()
            if not line or "ProcessId" in line:
                continue
            parts = line.split()
            try:
                pids.append(int(parts[-1]))
            except Exception:
                continue
        return pids
    except Exception:
        return []


def stop_agent():
    for pid in find_agent_pids():
        subprocess.call(
            ["taskkill", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

def stop_camoufox():
    # Kill browser processes too; agent-only restart is insufficient when the browser is zombied.
    for img in ("camoufox.exe", "firefox.exe"):
        subprocess.call(
            ["taskkill", "/F", "/T", "/IM", img],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def stop_gui():
    subprocess.call(
        ["taskkill", "/F", "/IM", PROCESS_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_gui():
    if os.path.exists(RUN_BAT):
        subprocess.Popen(["cmd", "/c", RUN_BAT], cwd=BASE_DIR)
    else:
        subprocess.Popen(["cmd", "/c", "npm run dev"], cwd=GUI_DIR)


def read_new_log_lines(state: dict) -> list[str]:
    try:
        if not os.path.exists(LOG_PATH):
            return []
        size = os.path.getsize(LOG_PATH)
        if size < state["pos"]:
            state["pos"] = 0
        with open(LOG_PATH, "r", errors="ignore") as f:
            f.seek(state["pos"])
            data = f.read()
            state["pos"] = f.tell()
        return data.splitlines()
    except Exception:
        return []


def main():
    logger = setup_logger()
    if not acquire_lock(logger):
        return
    logger.info("watchdog started")
    last_restart = 0.0
    last_no_frame_reset = time.time()
    no_frame_hits = 0
    browser_closed_hits = 0
    try:
        log_state = {"pos": os.path.getsize(LOG_PATH)}
    except Exception:
        log_state = {"pos": 0}
    last_state = {"running": None, "stale": None}
    try:
        while True:
            try:
                running = is_process_running()
                stale = log_stale()
                now = time.time()
                if running != last_state["running"] or stale != last_state["stale"]:
                    logger.info("status running=%s stale=%s", running, stale)
                    last_state["running"] = running
                    last_state["stale"] = stale
                if now - last_no_frame_reset > NOFRAME_WINDOW:
                    no_frame_hits = 0
                    browser_closed_hits = 0
                    last_no_frame_reset = now

                for line in read_new_log_lines(log_state):
                    if "no frames" in line or "iframe 不健全" in line:
                        no_frame_hits += 1
                    if "Browser closed" in line or "Target page, context or browser has been closed" in line:
                        browser_closed_hits += 1

                hard_restart = (
                    no_frame_hits >= NOFRAME_LIMIT or browser_closed_hits >= BROWSER_CLOSED_LIMIT
                )

                if (not running) or stale:
                    if now - last_restart >= RESTART_COOLDOWN:
                        if not running:
                            logger.info("gui down - restarting gui")
                            stop_camoufox()
                            stop_agent()
                            start_gui()
                        elif stale:
                            if find_agent_pids():
                                logger.info("log stale - restarting agent")
                                stop_camoufox()
                                stop_agent()
                            else:
                                logger.info("log stale + no agent - restarting gui")
                                stop_camoufox()
                                stop_gui()
                                time.sleep(3)
                                start_gui()
                        last_restart = now
                elif hard_restart and now - last_restart >= RESTART_COOLDOWN:
                    if find_agent_pids():
                        logger.info("recovery loop/browser closed - restarting agent")
                        stop_camoufox()
                        stop_agent()
                    else:
                        logger.info("recovery loop + no agent - restarting gui")
                        stop_camoufox()
                        stop_gui()
                        time.sleep(3)
                        start_gui()
                    no_frame_hits = 0
                    browser_closed_hits = 0
                    last_no_frame_reset = now
                    last_restart = now
                time.sleep(CHECK_INTERVAL)
            except Exception as exc:
                logger.exception("watchdog loop error: %s", exc)
                time.sleep(CHECK_INTERVAL)
    finally:
        release_lock(logger)


if __name__ == "__main__":
    main()
