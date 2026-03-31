"""BET判断エンジン — プレイヤー3段目狙い + 1-2-3打法

ロジック:
  1. 規則性70%以上 + 横流れパターン (テレコ/ニコニコ/ニコイチ) のテーブルを選定
  2. バンカー列が切れてプレイヤーが2連続 → 3段目にプレイヤーBET
  3. 的中 → プレイヤー継続BET (ドラゴン追い)
  4. ハズレ → 待機、次のプレイヤー2連続を待つ
  5. プレイヤー限定 (バンカー側には賭けない)

資金管理 (1-2-3打法):
  - BET額: 基準額 × [1, 2, 3] の順で進行
  - 1回目と2回目の結果が違う → 即リセット (3回目に進まない)
  - 1回目と2回目の結果が同じ → 3回目に進む
  - 3回目の後は結果に関わらずリセット
"""
import logging
from shoe import ShoeTracker

logger = logging.getLogger("baccarat.strategy")

YOKONAGARE_PATTERNS = {"テレコ", "ニコニコ・ニコイチ"}


class BetStrategy:
    """プレイヤー3段目狙い + 1-2-3打法"""

    def __init__(self, config: dict):
        self.min_regularity = config.get("min_regularity_score", 30)
        self.base_bet = config.get("base_bet", 1.0)

        # 1-2-3打法の状態
        self._bet_level = 0       # 0=1回目, 1=2回目, 2=3回目
        self._bet_results = []    # 直近の勝敗記録 (True=勝, False=負)
        self._riding_streak = False  # 的中後のドラゴン追い中

    @property
    def current_bet_amount(self) -> float:
        """現在のBET額 (1-2-3打法)"""
        multipliers = [1, 2, 3]
        return self.base_bet * multipliers[self._bet_level]

    def evaluate(self, shoe: ShoeTracker) -> dict | None:
        """BETすべきならBET情報を返す。BET不要ならNone。

        条件:
          - プレイヤーが2連続以上 → BET
          - ドラゴン追い中は即BET
        """
        if shoe.hand_count < 3:
            return None

        # 大路の列 (streak) を取得
        streaks = shoe._compute_streaks()

        # ドラゴン追い中: 直前がプレイヤー勝利 → 継続BET
        if self._riding_streak and len(streaks) >= 1:
            last = streaks[-1]
            if last["type"] == "player" and last["len"] >= 3:
                return {
                    "side": "player",
                    "amount": self.current_bet_amount,
                    "reason": f"ドラゴン追い: P{last['len']}連続→継続",
                    "strategy_name": "player_3dan",
                }
            else:
                self._riding_streak = False

        # エントリー条件: 直近がP2連続以上 (=最後のstreakがplayer×2+)
        if len(streaks) >= 2:
            last = streaks[-1]
            prev = streaks[-2]
            if last["type"] == "player" and last["len"] >= 2:
                # 直前がバンカー列から切り替わった場合のみ (P3段目狙い)
                return {
                    "side": "player",
                    "amount": self.current_bet_amount,
                    "reason": f"P{last['len']}連続 (1-2-3: {self._bet_level + 1}回目 ${self.current_bet_amount:.0f})",
                    "strategy_name": "player_3dan",
                }
            else:
                logger.debug(f"  直近streak: {last['type']}x{last['len']} — P2連続なし")

        return None

    def record_result(self, won: bool):
        """BET結果を記録して1-2-3打法の状態を更新"""
        self._bet_results.append(won)

        if won:
            # 的中 → ドラゴン追い開始
            self._riding_streak = True
        else:
            # ハズレ → ドラゴン追い終了、待機
            self._riding_streak = False

        # 1-2-3打法の進行管理
        if self._bet_level == 0:
            # 1回目完了 → 2回目へ
            self._bet_level = 1
        elif self._bet_level == 1:
            # 2回目完了 → 結果が1回目と同じなら3回目へ、違えばリセット
            if len(self._bet_results) >= 2:
                if self._bet_results[-1] == self._bet_results[-2]:
                    # 同じ結果 (勝-勝 or 負-負) → 3回目へ
                    self._bet_level = 2
                else:
                    # 違う結果 (勝-負 or 負-勝) → リセット
                    self._reset_123()
        elif self._bet_level == 2:
            # 3回目完了 → 必ずリセット
            self._reset_123()

    def _reset_123(self):
        """1-2-3打法をリセット"""
        self._bet_level = 0
        self._bet_results.clear()
        logger.info("1-2-3打法リセット → 1回目に戻る")

    def reset_losses(self):
        """セッションリセット"""
        self._reset_123()
        self._riding_streak = False

    def get_status(self) -> dict:
        """現在の戦略状態を返す"""
        return {
            "bet_level": self._bet_level + 1,
            "bet_amount": self.current_bet_amount,
            "riding_streak": self._riding_streak,
            "recent_results": ["W" if r else "L" for r in self._bet_results[-5:]],
        }
