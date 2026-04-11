import os
import subprocess
import time

BASE_DIR = r"C:\dev\ba"
GUI_DIR = os.path.join(BASE_DIR, "gui")
LOG_PATH = os.path.join(BASE_DIR, "agent.log")
RUN_BAT = os.path.join(BASE_DIR, "cloud_scripts", "run.bat")
PROCESS_NAME = "electron.exe"
CHECK_INTERVAL = 30
STALE_SECONDS = 10 * 60
RESTART_COOLDOWN = 60


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


def main():
    last_restart = 0.0
    while True:
        running = is_process_running()
        stale = log_stale()
        if (not running) or stale:
            now = time.time()
            if now - last_restart >= RESTART_COOLDOWN:
                reason = "process down" if not running else "log stale"
                print(f"[watchdog] restart ({reason})")
                stop_gui()
                time.sleep(3)
                start_gui()
                last_restart = now
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
