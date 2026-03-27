"""バカラモニター — メインエントリポイント

Stake.com経由でEvolutionライブバカラのテーブルを24時間監視し、
全ラウンドの結果（Player/Banker/Tie）をSQLiteに記録する。
1シューごとにTelegramに統計・出目・バンカー連続数を通知する。

Usage:
    python main.py                  # 通常起動
    python main.py --stats          # 統計表示のみ
    python main.py --dry            # Telegram通知なし
    python main.py --table "Speed Baccarat A"  # テーブル指定
"""
import os
import sys
import time
import signal
import logging
import argparse
import threading

import config
from db import init_db, insert_shoe, get_stats, get_streak, get_recent_results
from scraper import BaccaratScraper
from notify import TelegramNotifier
from shoe import ShoeTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "baccarat.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("baccarat")


def show_stats():
    """統計を表示して終了"""
    init_db()
    stats = get_stats(hours=24)
    if stats["total"] == 0:
        print("データがありません。")
        return

    streak = get_streak()
    recent = get_recent_results(limit=20)

    print("━━━ バカラモニター 24時間統計 ━━━")
    print(f"\n📊 合計 {stats['total']} ラウンド")
    print(f"  🔵 Player: {stats['player']:>4} ({stats['player_pct']}%)")
    print(f"  🔴 Banker: {stats['banker']:>4} ({stats['banker_pct']}%)")
    print(f"  🟢 Tie:    {stats['tie']:>4} ({stats['tie_pct']}%)")
    print(f"  ペア: Player={stats['player_pair']} Banker={stats['banker_pair']}")
    print(f"\n現在の連続: {streak['current']} × {streak['count']}")

    print("\n直近20ラウンド:")
    symbols = {"player": "🔵", "banker": "🔴", "tie": "🟢"}
    row = ""
    for r in reversed(recent):
        row += symbols.get(r["result"], "?")
    print(f"  {row}")


def _handle_shoe_complete(shoe: ShoeTracker, notifier: TelegramNotifier):
    """シュー完了時の処理: DB保存 + Telegram通知"""
    if shoe.hand_count == 0:
        return

    summary = shoe.get_summary()

    # DB保存
    insert_shoe(summary)

    # Telegram通知
    notifier.notify_shoe_complete(summary)

    logger.info(
        f"シュー #{summary['shoe_number']} 完了: "
        f"{summary['hand_count']}ハンド "
        f"P={summary['player_count']} B={summary['banker_count']} T={summary['tie_count']} "
        f"出目={summary['result_sequence'][:30]}... "
        f"B最大連続={summary['max_banker_streak']}"
    )


def run_monitor(table: str = "", dry: bool = False):
    """メイン監視ループ"""
    init_db()

    # Telegram
    notifier = TelegramNotifier(
        "" if dry else config.TELEGRAM_BOT_TOKEN,
        "" if dry else config.TELEGRAM_CHAT_ID,
    )

    scraper = BaccaratScraper()
    if table:
        scraper.table_name = table

    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("停止シグナル受信...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 起動
    try:
        scraper.start()
    except Exception as e:
        logger.error(f"起動失敗: {e}")
        scraper.take_screenshot("startup_error")
        scraper.stop()
        return

    # WebSocket傍受を設定
    scraper.setup_ws_intercept()

    # EvolutionロビーWSからテーブル設定が来るのを待つ
    logger.info("EvolutionテーブルID解決を待機中...")
    for _ in range(30):
        if scraper._target_table_id:
            break
        time.sleep(1)
    else:
        logger.warning("テーブルID解決タイムアウト — 続行します")

    notifier.notify_startup(scraper.table_name or "(テーブル未確定)")
    logger.info(f"監視開始: {scraper.table_name} (ID: {scraper._target_table_id})")

    # シュー追跡
    shoe = ShoeTracker(table_name=scraper.table_name)
    shoe.shoe_number = 1
    logger.info("シュー #1 開始")

    last_report = time.time()
    last_result_time = time.time()
    no_result_warning = False
    retry_count = 0

    while running:
        try:
            # 0. 新シュー信号をチェック
            if scraper.has_new_shoe_signal():
                _handle_shoe_complete(shoe, notifier)
                shoe.reset()
                shoe.table_name = scraper.table_name

            # 1. WebSocket結果をチェック
            ws_results = scraper.get_ws_results()
            if ws_results:
                new = scraper.process_results(ws_results)
                if new > 0:
                    last_result_time = time.time()
                    no_result_warning = False

                    # シューに結果を追加
                    for r in ws_results:
                        result = r.get("result")
                        if result in ("player", "banker", "tie"):
                            shoe.add_result(result)

            # 2. DOM結果をチェック（WSが取れない場合のフォールバック）
            if time.time() - last_result_time > 120:  # 2分間WSから結果なし
                try:
                    dom_results = scraper.poll_dom_results()
                    if dom_results:
                        new = scraper.process_results(dom_results)
                        if new > 0:
                            last_result_time = time.time()
                            logger.info("DOM経由で結果取得")

                            for r in dom_results:
                                result = r.get("result")
                                if result in ("player", "banker", "tie"):
                                    shoe.add_result(result)
                except Exception as e:
                    logger.debug(f"DOMポーリングエラー: {e}")

            # 3. シュー完了チェック（タイムアウトベース）
            #    3分以上結果がなく、かつシューに10ハンド以上あればシュー終了と判定
            time_since_last = time.time() - last_result_time
            if time_since_last > 180 and shoe.hand_count >= 10:
                logger.info(f"3分間結果なし + {shoe.hand_count}ハンド → シュー完了と判定")
                _handle_shoe_complete(shoe, notifier)
                shoe.reset()
                shoe.table_name = scraper.table_name

            # シューのハンド数上限チェック
            if shoe.is_shoe_complete():
                _handle_shoe_complete(shoe, notifier)
                shoe.reset()
                shoe.table_name = scraper.table_name

            # 4. 長時間結果なしの警告
            elapsed = time.time() - last_result_time
            if elapsed > 300 and not no_result_warning:  # 5分
                logger.warning("5分間結果なし — テーブルが休止中またはセッション切れの可能性")
                scraper.take_screenshot("no_results")
                no_result_warning = True

            # 5. セッション生存チェック
            if elapsed > 600:  # 10分
                if not scraper.is_alive():
                    logger.error("セッション切れ — 再接続中...")

                    # 現在のシューがあれば保存
                    if shoe.hand_count > 0:
                        _handle_shoe_complete(shoe, notifier)
                        shoe.reset()

                    retry_count += 1
                    if retry_count > config.MAX_RETRIES:
                        logger.error("最大リトライ回数超過 — 停止")
                        notifier.notify_shutdown("最大リトライ超過")
                        break

                    scraper.stop()
                    time.sleep(config.RETRY_DELAY)
                    scraper = BaccaratScraper()
                    if table:
                        scraper.table_name = table
                    scraper.start()
                    scraper.setup_ws_intercept()
                    shoe.table_name = scraper.table_name
                    last_result_time = time.time()
                    no_result_warning = False
                    logger.info(f"再接続成功 (retry {retry_count}/{config.MAX_RETRIES})")

            # 6. 定期レポート
            if time.time() - last_report >= config.REPORT_INTERVAL:
                stats = get_stats(table_name=scraper.table_name, hours=24)
                streak = get_streak(table_name=scraper.table_name)
                notifier.notify_report(scraper.table_name, stats, streak)
                last_report = time.time()

                logger.info(
                    f"レポート: {stats['total']}R "
                    f"P={stats['player']}({stats['player_pct']}%) "
                    f"B={stats['banker']}({stats['banker_pct']}%) "
                    f"T={stats['tie']}({stats['tie_pct']}%)"
                )

            # ポーリング間隔
            time.sleep(config.POLL_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"メインループエラー: {e}", exc_info=True)
            time.sleep(10)

    # 停止 — 残りのシューデータを保存
    logger.info("監視停止中...")
    if shoe.hand_count > 0:
        _handle_shoe_complete(shoe, notifier)

    stats = get_stats(table_name=scraper.table_name, hours=24)
    notifier.notify_shutdown(f"合計{stats['total']}ラウンド記録")
    scraper.stop()
    logger.info("完了")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="バカラモニター")
    parser.add_argument("--stats", action="store_true", help="統計表示のみ")
    parser.add_argument("--dry", action="store_true", help="Telegram通知なし")
    parser.add_argument("--table", default="", help="テーブル名指定")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_monitor(table=args.table, dry=args.dry)
