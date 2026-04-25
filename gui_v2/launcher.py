"""LAPLACE COPILOT v2 — pywebview ネイティブウィンドウランチャー

仕組み:
  1. Flask backend を bg thread で起動 (port 5050)
  2. pywebview で Edge WebView2 ネイティブウィンドウを開く
  3. ウィンドウ閉じたら Flask サーバ + 子プロセス全停止

使い方:
  python launcher.py
  → タスクバーに新規ウィンドウが出現、URL バーなしで GUI 表示
  → 閉じたら全停止
"""
from __future__ import annotations
import os
import sys
import threading
import time
from pathlib import Path

# 文字化け対策
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
BA_DIR = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BA_DIR))

# Flask app を import (この時点で BACKEND が初期化される)
import app as _app_module

PORT = 5050
URL = f"http://127.0.0.1:{PORT}"


def _run_flask():
    """Flask を別スレッドで起動 (debug/reloader OFF)"""
    _app_module.app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False, threaded=False)


def main():
    print("=" * 60, flush=True)
    print("  LAPLACE COPILOT v2 — Native Window Launcher", flush=True)
    print("=" * 60, flush=True)

    # 1. Flask backend を bg thread で起動
    flask_thread = threading.Thread(target=_run_flask, daemon=True, name="FlaskBackend")
    flask_thread.start()
    print(f"[1/2] Flask backend 起動中 (port {PORT})...", flush=True)

    # サーバが応答するまで待機 (最大 15 秒)
    import urllib.request
    for i in range(30):
        try:
            with urllib.request.urlopen(URL, timeout=1) as r:
                if r.status == 200:
                    print(f"[1/2] Flask 起動完了 ({i*0.5:.1f}s)", flush=True)
                    break
        except Exception:
            time.sleep(0.5)
    else:
        print("[ERROR] Flask 起動失敗 (15s timeout)", flush=True)
        sys.exit(1)

    # 2. pywebview ネイティブウィンドウ
    print(f"[2/2] ネイティブウィンドウ起動中...", flush=True)
    try:
        import webview
    except ImportError:
        print("[ERROR] pywebview がインストールされていません", flush=True)
        print("  pip install pywebview", flush=True)
        sys.exit(1)

    window = webview.create_window(
        title="LAPLACE COPILOT v2",
        url=URL,
        width=1700,
        height=1050,
        min_size=(1200, 700),
        background_color="#05080f",
        zoomable=True,
        confirm_close=False,
    )
    # blocking — ウィンドウ閉じるまで戻ってこない
    webview.start(debug=False, http_server=False)

    print("[exit] ウィンドウ閉じられました — Flask 停止中...", flush=True)
    # daemon thread なのでメインプロセス終了で Flask も死ぬ
    sys.exit(0)


if __name__ == "__main__":
    main()
