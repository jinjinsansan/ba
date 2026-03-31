"""hakudasama用 — Japanese Speed Baccarat 9テーブル監視 + Telegram通知

Usage:
    cd E:\\dev\\Cusor\\ba\\monitor
    python run.py
"""
import os
import sys

# 親ディレクトリのモジュールを使用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# このディレクトリの .env を優先読み込み
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# config.ini もこのディレクトリのものを使用
import configparser
_monitor_dir = os.path.dirname(os.path.abspath(__file__))
_ini = configparser.ConfigParser()
_ini.read(os.path.join(_monitor_dir, "config.ini"), encoding="utf-8")

import io
import time
import signal
import logging

# ログ設定
_console = logging.StreamHandler(
    stream=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
)
_console.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))

_log_path = os.path.join(_monitor_dir, "monitor.log")
_file = logging.FileHandler(_log_path, encoding="utf-8")
_file.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])

# scraper詳細ログはファイルのみ
logging.getLogger("baccarat.scraper").handlers = [_file]
logging.getLogger("baccarat.scraper").propagate = False
logging.getLogger("baccarat.game_ws").handlers = [_file]
logging.getLogger("baccarat.game_ws").propagate = False

logger = logging.getLogger("baccarat.monitor")

from db import init_db, insert_shoe, get_stats, get_streak
from scraper import BaccaratScraper
from notify import TelegramNotifier
from shoe import ShoeTracker


def _handle_shoe_complete(shoe: ShoeTracker, notifier: TelegramNotifier):
    if shoe.hand_count == 0:
        return
    summary = shoe.get_summary()
    insert_shoe(summary)
    notifier.notify_shoe_complete(summary)
    logger.info(
        f"シュー完了: {summary['table_name']} {summary['hand_count']}手 "
        f"P={summary['player_count']} B={summary['banker_count']} T={summary['tie_count']}"
    )


def main():
    init_db()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    notifier = TelegramNotifier(bot_token, chat_id)

    scraper = BaccaratScraper()
    scraper.table_name = "Japanese Baccarat"  # Japanese 9テーブルのみ

    running = True
    def shutdown(signum, frame):
        nonlocal running
        logger.info("停止シグナル受信...")
        running = False
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        scraper.start()
    except Exception as e:
        logger.error(f"起動失敗: {e}")
        scraper.stop()
        return

    scraper.setup_ws_intercept()

    logger.info("EvolutionテーブルID解決を待機中...")
    for _ in range(30):
        if scraper._target_table_ids:
            break
        time.sleep(1)

    table_count = len(scraper._target_table_ids)
    logger.info(f"監視開始: {table_count}テーブル (Japanese Speed Baccarat)")
    notifier.notify_startup(f"Japanese Speed Baccarat ({table_count}テーブル)")

    shoes: dict[str, ShoeTracker] = {}
    for tid in scraper._target_table_ids:
        tname = scraper._target_table_names.get(tid, tid)
        shoes[tid] = ShoeTracker(table_name=tname)
        shoes[tid].shoe_number = 1
        hist = scraper._evo_table_histories.get(tid, [])
        for entry in hist:
            if isinstance(entry, dict):
                color = entry.get("c", "")
                r = {"B": "banker", "R": "player"}.get(color)
                if r:
                    shoes[tid].add_result(r)
                if entry.get("ties", 0) > 0:
                    shoes[tid].add_result("tie")

    last_result_time = time.time()

    while running:
        try:
            # 新シュー信号
            shoe_signals = scraper.get_new_shoe_signals()
            for tid, sig in shoe_signals.items():
                if sig and tid in shoes:
                    _handle_shoe_complete(shoes[tid], notifier)
                    shoes[tid].reset()
                    shoes[tid].table_name = scraper._target_table_names.get(tid, tid)

            # WS結果
            ws_results = scraper.get_ws_results()
            if ws_results:
                new = scraper.process_results(ws_results)
                if new > 0:
                    last_result_time = time.time()
                    for r in ws_results:
                        result = r.get("result")
                        tid = r.get("table_id", "")
                        if result in ("player", "banker", "tie") and tid in shoes:
                            shoes[tid].add_result(result)

            # シュー完了チェック (8分間結果なし)
            if time.time() - last_result_time > 480:
                for tid, shoe in shoes.items():
                    if shoe.hand_count >= 40:
                        _handle_shoe_complete(shoe, notifier)
                        shoe.reset()
                        shoe.table_name = scraper._target_table_names.get(tid, tid)
                last_result_time = time.time()

            time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"エラー: {e}", exc_info=True)
            time.sleep(10)

    logger.info("監視停止中...")
    saved = 0
    for tid, shoe in shoes.items():
        if shoe.hand_count > 0:
            summary = shoe.get_summary()
            insert_shoe(summary)
            saved += 1
    if saved:
        logger.info(f"シューデータ保存: {saved}件")

    notifier.notify_shutdown()
    scraper.stop()
    logger.info("完了")


if __name__ == "__main__":
    main()
