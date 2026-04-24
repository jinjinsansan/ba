"""Camoufox 手動ログインヘルパー

scraper.py がロビー遷移後にログアウト扱いになる場合、以下を実行:
  1. このスクリプトで Camoufox をブラウザ起動 (persistent profile)
  2. user が手動で Stake.com にログイン → Evolution バカラロビー に移動
  3. ロビーでテーブル一覧が見える状態になるまで待機 (10-30 秒)
  4. ブラウザをそのまま閉じる (×ボタン)
  5. プロファイルが完全な状態で保存される → 以降 scraper.py が自動ログイン成功

使い方:
  cd E:\\dev\\Cusor\\ba\\gui_v2
  python manual_login.py

起動:
  - run.bat で Flask GUI 起動
  - GUI から 🔌 Live Scraper 起動
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

# ba/ を import path に追加
BA_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BA_DIR))


def main():
    try:
        import camoufox
        from camoufox.sync_api import Camoufox
    except ImportError:
        print("ERROR: camoufox がインストールされていません", flush=True)
        sys.exit(1)

    import config as cfg
    profile_dir = cfg.AUTH_STATE_DIR / "camoufox_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"=" * 60, flush=True)
    print(f"Camoufox 手動ログインヘルパー", flush=True)
    print(f"=" * 60, flush=True)
    print(f"Profile dir: {profile_dir}", flush=True)
    print(f"", flush=True)
    print(f"手順:", flush=True)
    print(f"  1. Camoufox が起動します (Firefox 系のブラウザ)", flush=True)
    print(f"  2. Stake.com にログインしてください", flush=True)
    print(f"  3. バカラロビー ({cfg.BACCARAT_LOBBY_URL}) に移動", flush=True)
    print(f"  4. テーブル一覧が見える状態で 30 秒以上待機", flush=True)
    print(f"  5. ブラウザを閉じてください (×ボタン)", flush=True)
    print(f"", flush=True)
    print(f"起動します...", flush=True)

    launch_opts = {
        "headless": False,
        "locale": "ja-JP",
        "user_data_dir": str(profile_dir),
        "viewport": {"width": 1400, "height": 900},
    }

    with Camoufox(**launch_opts) as browser:
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
        except Exception:
            page = browser.new_page()

        print(f"[launch] → {cfg.STAKE_URL}", flush=True)
        try:
            page.goto(cfg.STAKE_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[warn] goto 失敗: {e}", flush=True)

        print(f"[waiting] ブラウザで手動操作してください。閉じるまで待機します...", flush=True)

        # ブラウザが閉じられるまで待機
        closed = False
        while not closed:
            try:
                # page が閉じられた or context 切断を検知
                page.evaluate("1+1")
                time.sleep(2)
            except Exception:
                closed = True
                break

    print(f"", flush=True)
    print(f"[saved] プロファイルが保存されました: {profile_dir}", flush=True)
    print(f"[next] これで GUI の 🔌 Live Scraper 起動が成功するはずです", flush=True)


if __name__ == "__main__":
    main()
