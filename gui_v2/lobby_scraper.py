"""ロビー Playwright スクレイパ (任意) — 別プロセスで動かして lobby_state.json に書き出す

使い方:
  1. 初回: pip install playwright && playwright install chromium
  2. lobby_scraper_config.json を作成 (下記サンプル参照)
  3. python lobby_scraper.py で起動
     - 初回: 実ブラウザが立ち上がる → user が手動でログイン → Evolution ロビー表示
     - 2 回目以降: 永続プロファイルで自動ログイン済

※ このスクリプトはカジノサイトの DOM 構造に依存するため、
  各 user 自身で selector を調整する必要があります。
  雛形として Evolution 標準ロビーを想定しています。

設定ファイル (lobby_scraper_config.json):
{
  "casino_url": "https://YOUR-CASINO.com/play",
  "lobby_url_hint": "evolution",
  "scrape_interval_sec": 60,
  "user_data_dir": "./.browser_profile",
  "headless": false
}
"""
from __future__ import annotations
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SELF_DIR = Path(__file__).parent
CONFIG_PATH = SELF_DIR / "lobby_scraper_config.json"
OUTPUT_PATH = SELF_DIR / "lobby_state.json"

DEFAULT_CONFIG = {
    "casino_url": "about:blank",
    "lobby_url_hint": "evolution",
    "scrape_interval_sec": 60,
    "user_data_dir": str(SELF_DIR / ".browser_profile"),
    "headless": False,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        cfg = DEFAULT_CONFIG.copy()
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[init] サンプル設定を書き出しました: {CONFIG_PATH}")
        print(f"[init] casino_url を編集して再実行してください")
    # 欠けキーを default で補完
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


async def scrape_once(page, cfg) -> list[dict]:
    """
    Evolution ロビーから全テーブルの big road preview を読む。
    実装は casino ごとに異なるため、以下の selector は参考。
    user が自分のカジノに合わせて調整すること。
    """
    tables = []

    # Evolution ロビー上の全テーブルタイルを選択 (typical selector)
    # 以下の selector は Evolution 標準のものに近いが、canvas の中身も多いので調整必要
    candidates = await page.query_selector_all("[data-role='table-tile'], .table-tile, .game-tile")

    for el in candidates:
        try:
            name_el = await el.query_selector(".table-name, [data-role='table-name'], .game-name")
            tname = (await name_el.inner_text()).strip() if name_el else ""
            if not tname:
                continue

            # 大路 preview はテーブルタイルに埋め込まれている
            # DOM の ○● 要素列から P/B/T を読む (典型的には class="road-cell road-cell-player" など)
            road_cells = await el.query_selector_all(".road-cell, .big-road-cell, [data-road-cell]")
            seq_chars = []
            for c in road_cells:
                cls = (await c.get_attribute("class")) or ""
                cls_l = cls.lower()
                if "player" in cls_l or "blue" in cls_l:
                    seq_chars.append("P")
                elif "banker" in cls_l or "red" in cls_l:
                    seq_chars.append("B")
                elif "tie" in cls_l or "green" in cls_l:
                    seq_chars.append("T")
            tables.append({
                "table": tname,
                "seq": "".join(seq_chars),
            })
        except Exception as e:
            print(f"[warn] {e}", flush=True)
            continue
    return tables


async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright がインストールされていません", flush=True)
        print("  pip install playwright", flush=True)
        print("  playwright install chromium", flush=True)
        sys.exit(1)

    cfg = load_config()

    if cfg["casino_url"] == "about:blank":
        print(f"lobby_scraper_config.json の casino_url を編集してください", flush=True)
        sys.exit(1)

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=cfg["user_data_dir"],
            headless=cfg["headless"],
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print(f"[launch] {cfg['casino_url']}", flush=True)
        await page.goto(cfg["casino_url"], timeout=60000)
        print(f"[launch] 初回ログインが必要な場合、ブラウザで手動ログインしてください", flush=True)
        print(f"[launch] ログイン完了後、Evolution ロビーを開いた状態で放置してください", flush=True)
        print(f"[launch] {cfg['scrape_interval_sec']} 秒ごとにスクレイプします", flush=True)

        while True:
            try:
                # Evolution iframe を探す
                for f in page.frames:
                    if cfg["lobby_url_hint"] in (f.url or "").lower():
                        tables = await scrape_once(f, cfg)
                        if tables:
                            output = {
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "tables": tables,
                            }
                            OUTPUT_PATH.write_text(
                                json.dumps(output, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
                            print(f"[scrape] {datetime.now().strftime('%H:%M:%S')} {len(tables)} tables → lobby_state.json", flush=True)
                        break
                else:
                    print(f"[wait] Evolution iframe 未検出 (login / lobby 移動を待機)", flush=True)
            except Exception as e:
                print(f"[err] {e}", flush=True)
            await asyncio.sleep(cfg["scrape_interval_sec"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[stop] 終了", flush=True)
