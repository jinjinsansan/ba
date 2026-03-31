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

import io

# コンソール (PowerShell) — UTF-8強制
_console = logging.StreamHandler(
    stream=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
)
_console.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))

# ファイル — 全ログ
_file = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "baccarat.log"),
    encoding="utf-8",
)
_file.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])

# scraper内部の詳細ログ (Round #N, 履歴ロード等) はファイルのみ
logging.getLogger("baccarat.scraper").handlers = [_file]
logging.getLogger("baccarat.scraper").propagate = False
logging.getLogger("baccarat.game_ws").handlers = [_file]
logging.getLogger("baccarat.game_ws").propagate = False

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


def _run_table_session(
    executor, strategy, shoe, tid, tname,
    notifier, config_mod, stats, dry_bet, running_flag,
):
    """テーブル内で1-2-3打法を実行。

    フロー:
      1. BETフェーズ待機 (WS)
      2. BET実行
      3. 結果待ち (WS)
      4. 勝敗判定 → 1-2-3打法更新
      5. 条件が続けば次ラウンドへ、なければ終了
    """
    MAX_ROUNDS = 10

    for round_num in range(1, MAX_ROUNDS + 1):
        if not running_flag():
            break

        # BET額 (1-2-3打法)
        bet_amount = strategy.current_bet_amount
        bet_amount = max(config_mod.BET_MIN, min(config_mod.BET_MAX, bet_amount))
        side = "player"
        level = strategy.get_status()["bet_level"]

        # BETフェーズを待つ
        if not executor.wait_for_betting_phase(timeout=60):
            logger.warning("BETフェーズに入れません — テーブル退出")
            break

        # BET実行
        if not executor.place_bet(side, bet_amount):
            logger.warning("BET失敗 — テーブル退出")
            break

        # DB記録
        bet_id = insert_bet(
            table_name=tname, table_id=tid,
            shoe_number=shoe.shoe_number, hand_number=shoe.hand_count,
            bet_side=side, bet_amount=bet_amount,
            strategy_name="player_3dan",
            strategy_reason=f"1-2-3打法 {level}回目",
            regularity_score=0,
        )
        stats["total_bets"] += 1

        if dry_bet or executor.demo_mode:
            logger.info("[DEMO] BET記録完了")
            break

        # 結果待ち
        result_info = executor.wait_for_result(timeout=90)
        if not result_info or not result_info.get("result"):
            logger.warning("結果取得失敗 — テーブル退出")
            break

        result = result_info["result"]
        balance = result_info.get("balance", 0)
        shoe.add_result(result)

        # 勝敗判定
        if result == "tie":
            outcome = "tie"
            profit = 0.0
        elif result == side:
            outcome = "win"
            profit = bet_amount
        else:
            outcome = "lose"
            profit = -bet_amount

        if bet_id:
            update_bet_result(bet_id, outcome, profit)
        stats["total_profit"] += profit
        if outcome == "win":
            stats["wins"] += 1
        elif outcome == "lose":
            stats["losses"] += 1

        # ログ (友人BOTスタイル)
        outcome_jp = {"win": "勝利!", "lose": "負け", "tie": "TIE (引き分け)"}[outcome]
        logger.info(f"結果: {outcome_jp} 収支: ${profit:+.0f} 残高: ${balance:.2f}")

        if config_mod.NOTIFY_EVERY_BET:
            notifier.notify_bet_result({
                "result": outcome, "profit": profit,
                "table_name": tname, "cumulative_profit": stats["total_profit"],
            })

        # 1-2-3打法更新
        if outcome == "tie":
            logger.info("TIE → 同額で再BET")
            continue
        elif outcome == "win":
            strategy.record_result(True)
        else:
            strategy.record_result(False)

        # 1-2-3打法が継続中なら同じテーブルで次のBET
        status = strategy.get_status()
        if status["bet_level"] > 1:
            # まだ2回目 or 3回目が残っている → 同テーブルで続行
            next_amount = strategy.current_bet_amount
            logger.info(f"次: ${next_amount:.0f} BET (1-2-3: {status['bet_level']}回目)")
            continue
        else:
            # 1-2-3打法リセット済み or 1回目に戻った → テーブル退出
            logger.info("1-2-3打法完了 → テーブル退出")
            break

    logger.info(
        f"テーブルセッション終了: {stats['total_bets']}BET "
        f"累計${stats['total_profit']:+.2f}"
    )


def _handle_shoe_complete(shoe: ShoeTracker, notifier: TelegramNotifier):
    """シュー完了時の処理: DB保存 + Telegram通知"""
    if shoe.hand_count == 0:
        return

    summary = shoe.get_summary()

    # DB保存
    insert_shoe(summary)

    # Telegram通知
    notifier.notify_shoe_complete(summary)

    logging.getLogger("baccarat.scraper").info(
        f"シュー #{summary['shoe_number']} 完了: {summary['table_name']} "
        f"{summary['hand_count']}手 P={summary['player_count']} B={summary['banker_count']} T={summary['tie_count']}"
    )


def run_monitor(table: str = "", dry: bool = False, bet_mode: bool = False, dry_bet: bool = False):
    """メイン監視ループ (BETモード対応)"""
    init_db()

    # Telegram (BETモードでは通知無効)
    if is_betting or dry:
        notifier = TelegramNotifier("", "")
    else:
        notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    scraper = BaccaratScraper()
    scraper.table_name = table if table else "all"

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
        elif bet_mode:
            executor_config["demo_mode"] = False

        logger.info(f"BETモード: {'DEMO' if executor_config.get('demo_mode') else 'LIVE'}")
        logger.info(f"戦略: {config.BET_STRATEGY}, P2連続以上でBET")

    running = True
    _shutdown_count = 0

    def shutdown(signum, frame):
        nonlocal running, _shutdown_count
        _shutdown_count += 1
        import traceback
        logger.info(f"停止シグナル受信 (signum={signum}, count={_shutdown_count})")
        logger.info(f"  呼び出し元: {''.join(traceback.format_stack(frame, limit=3))}")
        running = False
        if _shutdown_count >= 2:
            logger.info("強制終了します")
            import os
            os._exit(1)

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
        elif bet_mode:
            executor_config["demo_mode"] = False
        executor = BetExecutor(scraper.page, scraper.game_ws, executor_config)
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
        f"全バカラ ({table_count}テーブル){mode_str}"
    )
    logger.info(f"監視開始: {table_count}テーブル{mode_str}")

    # マルチテーブル シュー追跡: table_id → ShoeTracker
    shoes: dict[str, ShoeTracker] = {}
    for tid in scraper._target_table_ids:
        tname = scraper._target_table_names.get(tid, tid)
        shoes[tid] = ShoeTracker(table_name=tname)
        shoes[tid].shoe_number = 1
        # 履歴データをshoeに投入
        hist = scraper._evo_table_histories.get(tid, [])
        for entry in hist:
            if isinstance(entry, dict):
                color = entry.get("c", "")
                r = {"B": "banker", "R": "player"}.get(color)
                if r:
                    shoes[tid].add_result(r)
                if entry.get("ties", 0) > 0:
                    shoes[tid].add_result("tie")
            elif isinstance(entry, str):
                r = {"player": "player", "banker": "banker", "tie": "tie"}.get(entry.lower())
                if r:
                    shoes[tid].add_result(r)
        logging.getLogger("baccarat.scraper").info(f"シュー #1 開始: {tname} (履歴{shoes[tid].hand_count}手)")

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
                    added_to_shoes = 0
                    missed = 0
                    for r in ws_results:
                        result = r.get("result")
                        tid = r.get("table_id", "")
                        if result in ("player", "banker", "tie"):
                            if tid in shoes:
                                shoes[tid].add_result(result)
                                added_to_shoes += 1
                            else:
                                missed += 1
                    if added_to_shoes > 0 or missed > 0:
                        logging.getLogger("baccarat.scraper").info(f"結果→シュー追加: {added_to_shoes}件, 未登録{missed}件")

            # 1.5. WSキープアライブ (BET中はリロードしない)
            ws_silent = scraper.seconds_since_last_ws_message()
            if ws_silent > config.WS_SILENCE_THRESHOLD and not (executor and executor.in_table):
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

                # テーブル巡回: BET条件一致テーブルを探す
                found_target = False
                candidates = []
                for tid, shoe in shoes.items():
                    if shoe.hand_count < 3:
                        continue
                    tname = scraper._target_table_names.get(tid, tid)
                    bet_info = strategy.evaluate(shoe)
                    if bet_info:
                        candidates.append((tid, shoe, tname, bet_info))

                if candidates:
                    # 複数一致 → 最もhand_countが多い(=データ多い)テーブルを優先
                    candidates.sort(key=lambda x: x[1].hand_count, reverse=True)
                    tid, shoe, tname, bet_info = candidates[0]
                    found_target = True
                    logger.info(
                        f">>> BET: {tname} ({shoe.hand_count}手) "
                        f"{bet_info['reason']} 出目={shoe.result_sequence[-8:]}"
                    )
                    if len(candidates) > 1:
                        others = ", ".join(c[2].replace("Japanese ","J.")[:20] for c in candidates[1:3])
                        logger.info(f"    他の候補: {others}")

                    entered = executor.enter_table(tid, tname)
                    if not entered:
                        continue

                    # テーブル内で1-2-3打法実行
                    _run_table_session(
                        executor, strategy, shoe, tid, tname,
                        notifier, config,
                        bet_session_stats, dry_bet,
                        lambda: running,
                    )
                    daily_profit = bet_session_stats["total_profit"]

                    executor.exit_table()
                    strategy.reset_losses()  # 1-2-3打法リセット (テーブル間持ち越し防止)
                    logger.info("監視を再開します")
                    last_result_time = time.time()
                    continue  # メインループ先頭に戻る

                if not found_target:
                    total_tables = len(shoes)
                    with_data = sum(1 for s in shoes.values() if s.hand_count >= 3)
                    logger.debug(f"BET条件一致なし ({with_data}/{total_tables}テーブル評価済み)")

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
                    scraper.table_name = table if table else "all"
                    scraper.start()
                    scraper.setup_ws_intercept()

                    if is_betting:
                        executor_config = dict(config.EXECUTOR_CONFIG)
                        if dry_bet:
                            executor_config["demo_mode"] = True
                        elif bet_mode:
                            executor_config["demo_mode"] = False
                        executor = BetExecutor(scraper.page, scraper.game_ws, executor_config)

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

    # 停止 — 残りのシューデータを保存 (ログ抑制)
    logger.info("監視停止中...")
    saved = 0
    for tid, shoe in shoes.items():
        if shoe.hand_count > 0:
            summary = shoe.get_summary()
            insert_shoe(summary)
            saved += 1
    if saved:
        logger.info(f"シューデータ保存: {saved}件")

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
