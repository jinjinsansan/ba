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
        self.min_regularity = config.get("min_regularity_score", 70)
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
          - 規則性70%以上
          - 横流れパターン (テレコ/ニコニコ/ニコイチ)
          - バンカー列終了後、プレイヤーが2連続 → 3段目にBET
          - ドラゴン追い中は即BET
        """
        if shoe.hand_count < 10:
            return None

        analysis = shoe.analyze()

        # 規則性チェック
        if analysis["regularity_score"] < self.min_regularity:
            return None

        # 横流れパターンチェック
        dominant = analysis.get("dominant_pattern", "")
        patterns = analysis.get("pattern_breakdown", {})
        is_yokonagare = (
            dominant in YOKONAGARE_PATTERNS
            or any(p in YOKONAGARE_PATTERNS for p, pct in patterns.items() if pct >= 30)
        )
        if not is_yokonagare:
            return None

        # 大路の列 (streak) を取得
        streaks = shoe._compute_streaks()
        if len(streaks) < 3:
            return None

        # ドラゴン追い中: 直前がプレイヤー勝利 → 継続BET
        if self._riding_streak:
            last = streaks[-1]
            if last["type"] == "player" and last["len"] >= 3:
                return {
                    "side": "player",
                    "amount": self.current_bet_amount,
                    "reason": f"ドラゴン追い: P{last['len']}連続→継続",
                    "strategy_name": "player_3dan",
                    "regularity_score": analysis["regularity_score"],
                }
            else:
                # プレイヤー列が切れた → ドラゴン追い終了
                self._riding_streak = False

        # エントリー条件: バンカー列終了 → プレイヤー2連続 → 3段目BET
        if self._check_player_3dan_entry(streaks):
            return {
                "side": "player",
                "amount": self.current_bet_amount,
                "reason": f"P3段目狙い: B切→P2連→3段目 (1-2-3: {self._bet_level + 1}回目 ${self.current_bet_amount:.0f})",
                "strategy_name": "player_3dan",
                "regularity_score": analysis["regularity_score"],
            }

        return None

    def _check_player_3dan_entry(self, streaks: list[dict]) -> bool:
        """バンカー列終了後、プレイヤーが2連続している状態か判定"""
        if len(streaks) < 2:
            return False

        last = streaks[-1]
        prev = streaks[-2]

        # 直前がバンカー列で、現在がプレイヤー2連続
        if prev["type"] == "banker" and last["type"] == "player" and last["len"] == 2:
            return True

        return False

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
