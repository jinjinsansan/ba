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
                if not running:
                    print("[watchdog] gui down — restarting gui")
                    stop_agent()
                    start_gui()
                elif stale:
                    if find_agent_pids():
                        print("[watchdog] log stale — restarting agent")
                        stop_agent()
                    else:
                        print("[watchdog] log stale + no agent — restarting gui")
                        stop_gui()
                        time.sleep(3)
                        start_gui()
                last_restart = now
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
