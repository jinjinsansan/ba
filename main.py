"""バカラモニター + 自動BETシステム — メインエントリポイント

Stake.com経由でEvolutionライブバカラのテーブルを24時間監視し、
全ラウンドの結果（Player/Banker/Tie）をSQLiteに記録する。
1シューごとにTelegramに統計・出目・バンカー連続数を通知する。

BETモード (--bet / --dry-bet) では戦略に基づいて自動BETを実行。

Usage:
    python main.py                  # 通常起動 (監視のみ)
    python main.py --stats          # 統計表示のみ
    python main.py --dry            # Telegram通知なし
    python main.py --table "Speed Baccarat A"  # テーブル指定
    python main.py --bet            # 自動BETモード
    python main.py --dry-bet        # デモBETモード (実BETなし)
"""
import os
import sys
import time
import random
import signal
import logging
import argparse
import threading

import config
from db import (
    init_db, insert_shoe, get_stats, get_streak, get_recent_results,
    insert_bet, update_bet_result, start_session, end_session, get_bet_stats,
)
from scraper import BaccaratScraper
from notify import TelegramNotifier
from shoe import ShoeTracker
from strategy import BetStrategy
from humanize import Humanizer
from executor import BetExecutor

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


def run_monitor(table: str = "", dry: bool = False, bet_mode: bool = False, dry_bet: bool = False):
    """メイン監視ループ (BETモード対応)"""
    init_db()

    # Telegram
    notifier = TelegramNotifier(
        "" if dry else config.TELEGRAM_BOT_TOKEN,
        "" if dry else config.TELEGRAM_CHAT_ID,
    )

    scraper = BaccaratScraper()
    if table:
        scraper.table_name = table

    # BET関連の初期化
    is_betting = bet_mode or dry_bet
    strategy = None
    humanizer = None
    executor = None
    session_id = None
    session_start_time = time.time()
    bet_session_stats = {"total_bets": 0, "wins": 0, "losses": 0, "total_profit": 0.0}
    daily_profit = 0.0

    if is_betting:
        strategy = BetStrategy(config.STRATEGY_CONFIG)
        humanizer = Humanizer(config.HUMANIZE_CONFIG)

        executor_config = dict(config.EXECUTOR_CONFIG)
        if dry_bet:
            executor_config["demo_mode"] = True

        logger.info(f"BETモード: {'DEMO' if dry_bet or executor_config.get('demo_mode') else 'LIVE'}")
        logger.info(f"戦略: {config.BET_STRATEGY}, 最低規則性: {config.STRATEGY_CONFIG.get('min_regularity_score', 60)}")

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

    # BET executor はスクレイパー起動後に初期化 (pageが必要)
    if is_betting:
        executor_config = dict(config.EXECUTOR_CONFIG)
        if dry_bet:
            executor_config["demo_mode"] = True
        executor = BetExecutor(scraper.page, humanizer, executor_config)
        session_id = start_session(0.0)

    # WebSocket傍受を設定
    scraper.setup_ws_intercept()

    # EvolutionロビーWSからテーブル設定が来るのを待つ
    logger.info("EvolutionテーブルID解決を待機中...")
    for _ in range(30):
        if scraper._target_table_ids:
            break
        time.sleep(1)
    else:
        logger.warning("テーブルID解決タイムアウト — 続行します")

    table_count = len(scraper._target_table_ids)
    mode_str = " [BET: DEMO]" if dry_bet else " [BET: LIVE]" if bet_mode else ""
    notifier.notify_startup(
        f"{scraper.table_name} ({table_count}テーブル){mode_str}" if table_count > 1
        else (scraper.table_name or "(テーブル未確定)") + mode_str
    )
    logger.info(f"監視開始: {table_count}テーブル{mode_str}")

    # マルチテーブル シュー追跡: table_id → ShoeTracker
    shoes: dict[str, ShoeTracker] = {}
    for tid in scraper._target_table_ids:
        tname = scraper._target_table_names.get(tid, tid)
        shoes[tid] = ShoeTracker(table_name=tname)
        shoes[tid].shoe_number = 1
        logger.info(f"シュー #1 開始: {tname}")

    last_report = time.time()
    last_result_time = time.time()
    no_result_warning = False
    retry_count = 0

    while running:
        try:
            # 0. 新シュー信号をテーブルごとにチェック
            shoe_signals = scraper.get_new_shoe_signals()
            for tid, sig in shoe_signals.items():
                if sig and tid in shoes:
                    _handle_shoe_complete(shoes[tid], notifier)
                    shoes[tid].reset()
                    shoes[tid].table_name = scraper._target_table_names.get(tid, tid)
                    if is_betting and executor and executor.current_table_id == tid:
                        executor.increment_shoe()

            # 1. WebSocket結果をチェック
            ws_results = scraper.get_ws_results()
            if ws_results:
                new = scraper.process_results(ws_results)
                if new > 0:
                    last_result_time = time.time()
                    no_result_warning = False

                    # テーブルごとにシューへ結果追加
                    for r in ws_results:
                        result = r.get("result")
                        tid = r.get("table_id", "")
                        if result in ("player", "banker", "tie") and tid in shoes:
                            shoes[tid].add_result(result)

            # 1.5. WSキープアライブ
            ws_silent = scraper.seconds_since_last_ws_message()
            if ws_silent > config.WS_SILENCE_THRESHOLD:
                logger.warning(f"WSメッセージ{int(ws_silent)}秒沈黙 — ロビーリロード")
                if scraper.reload_lobby():
                    for _ in range(15):
                        if scraper._target_table_ids:
                            break
                        time.sleep(1)
                    for tid in scraper._target_table_ids:
                        if tid not in shoes:
                            tname = scraper._target_table_names.get(tid, tid)
                            shoes[tid] = ShoeTracker(table_name=tname)
                            shoes[tid].shoe_number = 1

            # === BET判断フェーズ ===
            if is_betting and strategy and executor and not executor.in_table:
                # 日次損失上限チェック
                if daily_profit <= -config.DAILY_LOSS_LIMIT:
                    if running:
                        logger.warning(f"日次損失上限到達: ${daily_profit:.2f}")
                        notifier.notify_daily_limit("loss", daily_profit)
                        running = False
                        break

                # 日次利益目標チェック
                if daily_profit >= config.DAILY_PROFIT_TARGET:
                    if running:
                        logger.info(f"日次利益目標達成: ${daily_profit:.2f}")
                        notifier.notify_daily_limit("profit", daily_profit)
                        running = False
                        break

                # 休憩判断
                session_minutes = (time.time() - session_start_time) / 60
                if humanizer and humanizer.should_take_break(session_minutes):
                    break_time = humanizer.get_break_duration()
                    logger.info(f"休憩: {break_time / 60:.1f}分")
                    time.sleep(break_time)
                    session_start_time = time.time()
                    strategy.reset_losses()

                # テーブル巡回: BET条件一致テーブルを探す
                for tid, shoe in shoes.items():
                    if shoe.hand_count < 10:
                        continue

                    bet_info = strategy.evaluate(shoe)
                    if not bet_info:
                        continue

                    tname = scraper._target_table_names.get(tid, tid)
                    logger.info(f"BET対象テーブル発見: {tname} - {bet_info['reason']}")

                    # テーブル入場 (sync wrapper for async)
                    import asyncio
                    loop = asyncio.new_event_loop()
                    try:
                        entered = loop.run_until_complete(executor.enter_table(tid, tname))
                    finally:
                        loop.close()

                    if not entered:
                        continue

                    # 1ターン見送り
                    time.sleep(random.uniform(config.HUMANIZE_CONFIG["bet_interval_min"],
                                              config.HUMANIZE_CONFIG["bet_interval_max"]))
                    logger.info("1ターン見送り完了")

                    # BETスキップ判断
                    if humanizer and humanizer.should_skip_bet():
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(executor.exit_table())
                        finally:
                            loop.close()
                        continue

                    # BET額決定
                    bet_amount = config.BET_MIN
                    if humanizer:
                        bet_amount = humanizer.randomize_bet_amount(bet_amount)
                    bet_amount = max(config.BET_MIN, min(config.BET_MAX, bet_amount))

                    # BET実行
                    loop = asyncio.new_event_loop()
                    try:
                        bet_placed = loop.run_until_complete(
                            executor.place_bet(bet_info["side"], bet_amount)
                        )
                    finally:
                        loop.close()

                    if bet_placed:
                        logger.info(f"BET実行: {bet_info['side']} ${bet_amount:.2f}")

                        # DB記録
                        bet_id = insert_bet(
                            table_name=tname,
                            table_id=tid,
                            shoe_number=shoe.shoe_number,
                            hand_number=shoe.hand_count,
                            bet_side=bet_info["side"],
                            bet_amount=bet_amount,
                            strategy_name=bet_info.get("strategy_name", ""),
                            strategy_reason=bet_info.get("reason", ""),
                            regularity_score=bet_info.get("regularity_score", 0),
                        )

                        # Telegram通知
                        if config.NOTIFY_EVERY_BET:
                            notifier.notify_bet_placed({
                                "side": bet_info["side"],
                                "amount": bet_amount,
                                "table_name": tname,
                                "reason": bet_info.get("reason", ""),
                                "regularity_score": bet_info.get("regularity_score", 0),
                            })

                        bet_session_stats["total_bets"] += 1

                        # デモモードでは仮想結果を判定
                        if dry_bet or executor.demo_mode:
                            # 次のWS結果を待って判定 (同期的にはできないのでスキップ)
                            logger.info("[DEMO] BET記録完了 — 結果は次のWS更新で判定")
                        else:
                            # 結果待ち
                            loop = asyncio.new_event_loop()
                            try:
                                result = loop.run_until_complete(executor.wait_for_result(60))
                            finally:
                                loop.close()

                            if result and bet_id:
                                if result == "tie":
                                    outcome = "tie_push"
                                    profit = 0.0
                                elif result == bet_info["side"]:
                                    outcome = "win"
                                    profit = bet_amount * (0.95 if bet_info["side"] == "banker" else 1.0)
                                else:
                                    outcome = "lose"
                                    profit = -bet_amount

                                update_bet_result(bet_id, outcome, profit)
                                daily_profit += profit
                                bet_session_stats["total_profit"] += profit

                                if outcome == "win":
                                    bet_session_stats["wins"] += 1
                                    strategy.record_result(True)
                                elif outcome == "lose":
                                    bet_session_stats["losses"] += 1
                                    strategy.record_result(False)

                                logger.info(f"BET結果: {outcome} 収支: ${profit:+.2f} 累計: ${daily_profit:+.2f}")

                                if config.NOTIFY_EVERY_BET:
                                    notifier.notify_bet_result({
                                        "result": outcome,
                                        "profit": profit,
                                        "table_name": tname,
                                        "cumulative_profit": daily_profit,
                                    })

                    # テーブル退出
                    if executor.should_leave_table(executor.shoes_at_table):
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(executor.exit_table())
                        finally:
                            loop.close()
                    break  # 1テーブルずつ

            # 3. シュー完了チェック（タイムアウトベース — 全テーブル）
            time_since_last = time.time() - last_result_time
            if time_since_last > 480:
                for tid, shoe in shoes.items():
                    if shoe.hand_count >= 40:
                        logger.info(f"8分間結果なし + {shoe.hand_count}ハンド → シュー完了: {shoe.table_name}")
                        _handle_shoe_complete(shoe, notifier)
                        shoe.reset()
                        shoe.table_name = scraper._target_table_names.get(tid, tid)

            # シューのハンド数上限チェック
            for tid, shoe in shoes.items():
                if shoe.is_shoe_complete():
                    _handle_shoe_complete(shoe, notifier)
                    shoe.reset()
                    shoe.table_name = scraper._target_table_names.get(tid, tid)

            # 4. 長時間結果なしの警告
            elapsed = time.time() - last_result_time
            if elapsed > 300 and not no_result_warning:
                logger.warning("5分間結果なし — テーブルが休止中またはセッション切れの可能性")
                scraper.take_screenshot("no_results")
                no_result_warning = True

            # 5. セッション生存チェック
            if elapsed > 600:
                if not scraper.is_alive():
                    logger.error("セッション切れ — 再接続中...")

                    for tid, shoe in shoes.items():
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

                    if is_betting:
                        executor_config = dict(config.EXECUTOR_CONFIG)
                        if dry_bet:
                            executor_config["demo_mode"] = True
                        executor = BetExecutor(scraper.page, humanizer, executor_config)

                    shoes.clear()
                    for tid in scraper._target_table_ids:
                        tname = scraper._target_table_names.get(tid, tid)
                        shoes[tid] = ShoeTracker(table_name=tname)
                        shoes[tid].shoe_number = 1
                    last_result_time = time.time()
                    no_result_warning = False
                    logger.info(f"再接続成功 (retry {retry_count}/{config.MAX_RETRIES})")

            # 6. 定期レポート
            if time.time() - last_report >= config.REPORT_INTERVAL:
                stats = get_stats(hours=24)
                streak = get_streak()
                notifier.notify_report(f"全テーブル ({table_count})", stats, streak)
                last_report = time.time()

            time.sleep(config.POLL_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"メインループエラー: {e}", exc_info=True)
            time.sleep(10)

    # 停止 — 残りのシューデータを保存
    logger.info("監視停止中...")
    for tid, shoe in shoes.items():
        if shoe.hand_count > 0:
            _handle_shoe_complete(shoe, notifier)

    # BETセッション終了
    if is_betting and session_id:
        wins = bet_session_stats["wins"]
        losses = bet_session_stats["losses"]
        win_rate = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0
        end_session(
            session_id,
            total_bets=bet_session_stats["total_bets"],
            wins=wins,
            losses=losses,
            total_profit=bet_session_stats["total_profit"],
        )
        if config.NOTIFY_SESSION_SUMMARY:
            notifier.notify_session_summary({
                "total_bets": bet_session_stats["total_bets"],
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_profit": bet_session_stats["total_profit"],
                "strategy": config.BET_STRATEGY,
                "starting_balance": 0,
                "ending_balance": bet_session_stats["total_profit"],
            })
        logger.info(
            f"BETセッション終了: {bet_session_stats['total_bets']}BET "
            f"W:{wins} L:{losses} 収支:${bet_session_stats['total_profit']:+.2f}"
        )

    stats = get_stats(hours=24)
    notifier.notify_shutdown(f"合計{stats['total']}ラウンド記録")
    scraper.stop()
    logger.info("完了")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="バカラモニター + 自動BETシステム")
    parser.add_argument("--stats", action="store_true", help="統計表示のみ")
    parser.add_argument("--dry", action="store_true", help="Telegram通知なし")
    parser.add_argument("--table", default="", help="テーブル名指定")
    parser.add_argument("--bet", action="store_true", help="自動BETモード (実BET)")
    parser.add_argument("--dry-bet", action="store_true", help="デモBETモード (BETなし)")
    parser.add_argument("--backtest", action="store_true", help="バックテスト実行")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.backtest:
        from backtest import main as backtest_main
        backtest_main()
    else:
        run_monitor(
            table=args.table,
            dry=args.dry,
            bet_mode=args.bet,
            dry_bet=args.dry_bet,
        )
