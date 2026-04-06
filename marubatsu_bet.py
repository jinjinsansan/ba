"""〇❌ロジック × 自動BETセッション

⚠️  SERVER-ONLY — DO NOT SHIP TO CLIENT ⚠️
このモジュールは local-fallback 用 MaruBatsuBetSession で、
VPS に到達できない開発用途のみ使用します。marubatsu_strategy (SEQ 含む)
に依存するため client distribution には含めません (.dist_excludes 参照)。

Japanese Speed Baccarat A テーブルに入場し、
〇❌ロジック (SEQ, OS, slashed, next_unit_idx) に従って
Player側にBETする。

設計:
  - 常にPlayer=〇にBET (Banker=✕はBETしない、結果のみ記録)
  - 7ハンド=1セット、セット確定でSEQ昇降
  - +50 chip到達で利確リセット
  - 損切りchip到達で損切りリセット
  - Tieは〇❌に影響なし (BETは返還)
  - シュー交換時: 途中ターンは破棄 (BET済み分は損益確定済み)
"""
import time
import json
import logging
from pathlib import Path

from marubatsu_strategy import MaruBatsuTracker, SEQ, SetData
from notify import TelegramNotifier

logger = logging.getLogger("baccarat.marubatsu_bet")

PROFIT_STOP = 50  # default, overridable per session
DEFAULT_LOSS_CUT = 200


class MaruBatsuBetSession:
    """テーブル内で〇❌ロジックに従いBETを実行するセッション"""

    def __init__(
        self,
        executor,
        notifier: TelegramNotifier,
        chip_base: float = 1.0,
        loss_cut: int = DEFAULT_LOSS_CUT,
        dry_run: bool = False,
        profit_stop: int = PROFIT_STOP,
        resume: bool = True,
    ):
        self.executor = executor
        self.notifier = notifier
        self.chip_base = chip_base
        self.loss_cut = loss_cut
        self.profit_stop = profit_stop
        self.dry_run = dry_run
        self.resume = resume

        self.tracker = MaruBatsuTracker(chip_base=chip_base)
        self.session_count = 0

        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0

        # Separate state files for dry run vs live
        if dry_run:
            self.state_path = Path(__file__).parent / "state_marubatsu_bet_dry.json"
        else:
            self.state_path = Path(__file__).parent / "state_marubatsu_bet.json"

        # Resume behavior controlled by user choice (Continue/Reset dialog)
        if self.resume:
            self._load_state()
        else:
            try:
                if self.state_path.exists():
                    self.state_path.unlink()
                    logger.info(f"状態リセット: {self.state_path.name} を削除")
            except Exception as e:
                logger.warning(f"状態ファイル削除失敗: {e}")

    # === 状態保存/復元 ===

    def _save_state(self):
        state = {
            "sets": [
                {
                    "set_index": s.set_index,
                    "results": s.results,
                    "wins": s.wins,
                    "losses": s.losses,
                    "overshoot": s.overshoot,
                    "slashed": s.slashed,
                    "used_unit_idx": s.used_unit_idx,
                    "next_unit_idx": s.next_unit_idx,
                    "set_profit": s.set_profit,
                    "cumulative_profit": s.cumulative_profit,
                }
                for s in self.tracker.sets
            ],
            "current_turns": self.tracker.current_turns,
            "total_o": self.tracker.total_o,
            "total_x": self.tracker.total_x,
            "session_count": self.session_count,
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_ties": self.total_ties,
        }
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            for sd in state.get("sets", []):
                self.tracker.sets.append(SetData(**sd))
            self.tracker.current_turns = state.get("current_turns", [])
            self.tracker.total_o = state.get("total_o", 0)
            self.tracker.total_x = state.get("total_x", 0)
            self.session_count = state.get("session_count", 0)
            self.total_bets = state.get("total_bets", 0)
            self.total_wins = state.get("total_wins", 0)
            self.total_losses = state.get("total_losses", 0)
            self.total_ties = state.get("total_ties", 0)
            logger.info(
                f"状態復元: {len(self.tracker.sets)}セット, "
                f"ターン{len(self.tracker.current_turns)}/7, "
                f"累計{self.tracker.cumulative_profit:+d}chip"
            )
        except Exception as e:
            logger.warning(f"状態復元失敗: {e}")

    # === BET額計算 ===

    def get_bet_amount(self) -> float:
        """現在のSEQ[idx] × chip_base で実際のBET額($)を算出"""
        unit = SEQ[self.tracker.current_unit_idx]
        return unit * self.chip_base

    # === セッション制御 ===

    def effective_profit(self) -> int:
        """セット完了損益 + 進行中セットの暫定損益 (chip単位)"""
        from marubatsu_strategy import SEQ
        cp = self.tracker.cumulative_profit
        # Add provisional profit from in-progress set
        turns = self.tracker.current_turns
        if turns:
            wins = turns.count("O")
            losses = turns.count("X")
            unit = SEQ[self.tracker.current_unit_idx]
            cp += (wins - losses) * unit
        return cp

    def should_reset(self) -> bool:
        """利確 or 損切り条件をチェック (進行中セット含む)"""
        cp = self.effective_profit()
        if cp >= self.profit_stop:
            return True
        if cp <= -self.loss_cut:
            return True
        return False

    def reset_session(self, reason: str):
        """セッションリセット (利確/損切り)"""
        cp = self.effective_profit()
        self.session_count += 1
        money = cp * self.chip_base
        balance = self.executor.get_balance() if not self.dry_run else 0

        emoji = "🎉" if reason == "利確" else "🛑"
        msg = (
            f"{emoji} {reason}! Session #{self.session_count}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"損益: {cp:+d} chip (${money:+.2f})\n"
            f"セット数: {len(self.tracker.sets)}\n"
            f"成績: {self.total_wins}勝 {self.total_losses}敗 {self.total_ties}Tie\n"
            f"残高: ${balance:.2f}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"リセットして再開します..."
        )
        logger.info(msg)
        self.notifier.send(msg)

        self.tracker.sets.clear()
        self.tracker.current_turns.clear()
        self._save_state()

    # === メインBETループ ===

    def run_round(self, running_flag) -> dict:
        """1ラウンド分のBET→結果取得→〇❌記録を実行。

        Returns: {
            "action": "bet" | "observe" | "exit",
            "result": "player" | "banker" | "tie" | None,
            "won": bool | None,
            "bet_amount": float,
            "completed_set": SetData | None,
            "should_reset": bool,
        }
        """
        if not running_flag():
            return {"action": "exit"}

        if not self.executor.check_and_dismiss_error():
            logger.warning("エラーダイアログ検出 → セッション中断")
            return {"action": "exit"}

        # BETフェーズ待ち
        is_first = (self.total_bets == 0 and len(self.tracker.current_turns) == 0)
        if not self.executor.wait_for_betting_phase(timeout=180 if is_first else 120, skip_round=is_first):
            if not self.executor.check_and_dismiss_error():
                return {"action": "exit"}
            logger.warning("BETフェーズ待ちタイムアウト")
            return {"action": "exit"}

        # 残高チェック
        bet_amount = self.get_bet_amount()
        if not self.dry_run:
            balance = self.executor.get_balance()
            if balance < bet_amount:
                logger.error(f"残高不足: ${balance:.2f} < ${bet_amount:.2f}")
                self.notifier.send(
                    f"⚠️ 残高不足!\n"
                    f"必要: ${bet_amount:.2f} (SEQ[{self.tracker.current_unit_idx}]={SEQ[self.tracker.current_unit_idx]})\n"
                    f"残高: ${balance:.2f}"
                )
                return {"action": "exit"}

        # BET実行 (常にPlayer)
        side = "player"
        unit_idx = self.tracker.current_unit_idx
        unit = SEQ[unit_idx]
        turn_num = len(self.tracker.current_turns) + 1

        logger.info(
            f"BET: ${bet_amount:.0f} {side.upper()} "
            f"(SEQ[{unit_idx}]={unit}, Set#{self.tracker.current_set_index} Turn{turn_num}/7)"
        )

        if not self.executor.place_bet(side, bet_amount):
            logger.error("BET失敗")
            return {"action": "exit"}

        # 部分BETが発生した可能性 → 実際にテーブルに置かれた額で上書き
        actual_total = self.executor._get_total_bet()
        if actual_total > 0 and abs(actual_total - bet_amount) > 0.5:
            logger.warning(f"部分BET検出: 計画${bet_amount:.0f} → 実際${actual_total:.2f}")
            bet_amount = actual_total

        self.total_bets += 1

        # 結果待ち
        result_info = self.executor.wait_for_result(timeout=90, bet_amount=bet_amount)
        if not result_info or not result_info.get("result"):
            logger.error("結果取得失敗")
            return {"action": "exit"}

        result = result_info["result"]
        balance = result_info.get("balance", 0)

        # Tie処理
        if result == "tie":
            self.total_ties += 1
            logger.info(f"Tie — BET返還、〇❌に影響なし (残高${balance:.2f})")
            self._save_state()
            return {
                "action": "bet",
                "result": "tie",
                "won": None,
                "bet_amount": bet_amount,
                "completed_set": None,
                "should_reset": False,
            }

        # 〇❌に記録
        won = (result == "player")
        if won:
            self.total_wins += 1
        else:
            self.total_losses += 1

        completed_set = self.tracker.add_result(result)

        mark = "〇" if won else "✕"
        logger.info(
            f"結果: {result.upper()} → {mark} "
            f"(残高${balance:.2f})"
        )

        # ターン通知
        turns_display = "".join("〇" if t == "O" else "✕" for t in self.tracker.current_turns)
        if not completed_set:
            remaining = 7 - len(self.tracker.current_turns)
            turns_display += "_" * remaining

        self.notifier.send(
            f"{'〇 的中!' if won else '✕ ハズレ'} Turn {turn_num}/7\n"
            f"結果: {result.upper()} (BET: Player ${bet_amount:.0f})\n"
            f"{turns_display}\n"
            f"残高: ${balance:.2f}"
        )

        # セット確定
        if completed_set:
            self._notify_set_complete(completed_set, balance)

        need_reset = self.should_reset()
        self._save_state()

        return {
            "action": "bet",
            "result": result,
            "won": won,
            "bet_amount": bet_amount,
            "completed_set": completed_set,
            "should_reset": need_reset,
        }

    def _notify_set_complete(self, new_set: SetData, balance: float):
        """セット確定時のTelegram通知"""
        marks = new_set.results.replace("O", "〇").replace("X", "✕")
        diff = new_set.wins - new_set.losses
        outcome = "勝ち越し 📈" if diff > 0 else "負け越し 📉"
        money_set = new_set.set_profit * self.chip_base
        money_cum = new_set.cumulative_profit * self.chip_base

        msg = (
            f"📋 Set #{new_set.set_index} 確定\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{marks}\n"
            f"{outcome} ({new_set.wins}勝 {new_set.losses}敗)\n"
            f"\n"
            f"セット損益: {new_set.set_profit:+d} chip (${money_set:+.2f})\n"
            f"累計損益: {new_set.cumulative_profit:+d} chip (${money_cum:+.2f})\n"
            f"OS: {new_set.overshoot}\n"
            f"\n"
            f"次BET: SEQ[{new_set.next_unit_idx}] = {SEQ[new_set.next_unit_idx]} chip "
            f"(${SEQ[new_set.next_unit_idx] * self.chip_base:.2f})\n"
            f"残高: ${balance:.2f}\n"
            f"━━━━━━━━━━━━━━━"
        )
        self.notifier.send(msg)
        logger.info(
            f"Set #{new_set.set_index} 確定: {new_set.results} "
            f"{new_set.wins}/{new_set.losses} "
            f"P/L:{new_set.cumulative_profit:+d}"
        )

    def handle_shoe_change(self):
        """シュー交換時の処理 — 途中ターンを破棄"""
        if self.tracker.current_turns:
            partial = "".join("〇" if t == "O" else "✕" for t in self.tracker.current_turns)
            logger.info(f"シュー交換 — 途中ターン破棄: {partial}")
            self.notifier.send(
                f"⚠️ シュー交換\n"
                f"途中ターン破棄: {partial} ({len(self.tracker.current_turns)}/7)\n"
                f"累計損益: {self.tracker.cumulative_profit:+d} chip"
            )
            self.tracker.current_turns.clear()
            self._save_state()

    def get_summary(self) -> dict:
        """セッションサマリー"""
        return {
            "session_count": self.session_count,
            "sets": len(self.tracker.sets),
            "current_turn": len(self.tracker.current_turns),
            "cumulative_profit": self.tracker.cumulative_profit,
            "cumulative_money": self.tracker.cumulative_profit * self.chip_base,
            "total_bets": self.total_bets,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "total_ties": self.total_ties,
            "current_unit": SEQ[self.tracker.current_unit_idx],
            "current_unit_idx": self.tracker.current_unit_idx,
        }
