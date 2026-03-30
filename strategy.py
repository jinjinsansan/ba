"""BET判断エンジン

シューの状態を評価し、BETすべきかどうかを判断する。
4つの戦略: 横流れ / テレコ / ニコニコ / ドラゴン
"""
import logging
from shoe import ShoeTracker

logger = logging.getLogger("baccarat.strategy")


class BetStrategy:
    """シューの状態を評価し、BETすべきかどうかを判断する"""

    def __init__(self, config: dict):
        self.min_regularity = config.get("min_regularity_score", 60)
        self.strategy_name = config.get("strategy", "yokonagare")
        self.max_consecutive_loss = config.get("max_consecutive_loss", 3)
        self.consecutive_losses = 0

    def evaluate(self, shoe: ShoeTracker) -> dict | None:
        """BETすべきならBET情報を返す。BET不要ならNone"""
        if shoe.hand_count < 10:
            return None

        if self.consecutive_losses >= self.max_consecutive_loss:
            logger.info(f"{self.consecutive_losses}連敗 — BET停止中")
            return None

        analysis = shoe.analyze()
        if analysis["regularity_score"] < self.min_regularity:
            return None

        strategies = {
            "yokonagare": self._yokonagare,
            "tereko": self._tereko,
            "nikoniko": self._nikoniko,
            "dragon": self._dragon,
            "regularity": self._regularity_based,
        }

        func = strategies.get(self.strategy_name)
        if not func:
            logger.warning(f"不明な戦略: {self.strategy_name}")
            return None

        result = func(shoe, analysis)
        if result:
            result["strategy_name"] = self.strategy_name
            result["regularity_score"] = analysis["regularity_score"]
        return result

    def record_result(self, won: bool):
        """BET結果を記録して連敗カウントを更新"""
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1

    def reset_losses(self):
        """連敗カウントをリセット"""
        self.consecutive_losses = 0

    def _yokonagare(self, shoe: ShoeTracker, analysis: dict) -> dict | None:
        """横流れ攻略: 2落後の1落を狙う

        条件:
          - 5列までに3落が1-2個、4落以上なし、2落連続あり
          - 20目までの3落以上:2落以下 = 3:7以上
        エントリー:
          - 基本: 2落後の1落を狙う (逆サイドにBET)
        """
        streaks = shoe._compute_streaks()
        if len(streaks) < 5:
            return None

        first5 = streaks[:5]
        drops3 = sum(1 for s in first5 if s["len"] == 3)
        drops4plus = sum(1 for s in first5 if s["len"] >= 4)
        if drops4plus > 0 or drops3 > 2:
            return None

        # 20目までの比率チェック
        first20 = streaks[:20] if len(streaks) >= 20 else streaks
        above3 = sum(1 for s in first20 if s["len"] >= 3)
        below3 = len(first20) - above3
        if len(first20) >= 10 and below3 > 0:
            ratio = above3 / len(first20)
            if ratio > 0.5:
                return None

        last_streak = streaks[-1]
        if last_streak["len"] == 2:
            bet_side = "banker" if last_streak["type"] == "player" else "player"
            return {"side": bet_side, "reason": "横流れ: 2落後の1落狙い"}

        return None

    def _tereko(self, shoe: ShoeTracker, analysis: dict) -> dict | None:
        """テレコ狙い: テレコ(1落)が50%以上で逆サイドBET"""
        patterns = analysis.get("pattern_breakdown", {})
        tereko_pct = patterns.get("テレコ", 0)
        if tereko_pct < 50:
            return None

        streaks = shoe._compute_streaks()
        if not streaks:
            return None

        last = streaks[-1]
        if last["len"] == 1:
            bet_side = "banker" if last["type"] == "player" else "player"
            return {"side": bet_side, "reason": f"テレコ: 前回{last['type']}→逆 ({tereko_pct}%)"}

        return None

    def _nikoniko(self, shoe: ShoeTracker, analysis: dict) -> dict | None:
        """ニコニコ狙い: ニコニコ(2落)が40%以上で逆サイドBET"""
        patterns = analysis.get("pattern_breakdown", {})
        niko_pct = patterns.get("ニコニコ・ニコイチ", 0)
        if niko_pct < 40:
            return None

        streaks = shoe._compute_streaks()
        if not streaks:
            return None

        last = streaks[-1]
        if last["len"] == 2:
            bet_side = "banker" if last["type"] == "player" else "player"
            return {"side": bet_side, "reason": f"ニコニコ: 2落後→逆 ({niko_pct}%)"}

        return None

    def _dragon(self, shoe: ShoeTracker, analysis: dict) -> dict | None:
        """ドラゴン追従: 5落以上が30目中3回以上で同サイド継続BET"""
        streaks = shoe._compute_streaks()
        if len(streaks) < 5:
            return None

        check_range = streaks[-30:] if len(streaks) >= 30 else streaks
        dragon_count = sum(1 for s in check_range if s["len"] >= 5)
        if dragon_count < 3:
            return None

        last = streaks[-1]
        if last["len"] >= 3:
            return {"side": last["type"], "reason": f"ドラゴン: {last['len']}連続→継続"}

        return None

    def _regularity_based(self, shoe: ShoeTracker, analysis: dict) -> dict | None:
        """規則性ベース: 支配パターンに従う"""
        dominant = analysis["dominant_pattern"]
        streaks = shoe._compute_streaks()
        if not streaks:
            return None

        last = streaks[-1]

        if dominant == "テレコ" and last["len"] == 1:
            bet_side = "banker" if last["type"] == "player" else "player"
            return {"side": bet_side, "reason": f"テレコ: 前回{last['type']}→逆"}

        if dominant == "ニコニコ・ニコイチ" and last["len"] == 2:
            bet_side = "banker" if last["type"] == "player" else "player"
            return {"side": bet_side, "reason": f"ニコニコ: 2落後→逆"}

        if dominant == "ドラゴン" and last["len"] >= 3:
            return {"side": last["type"], "reason": f"ドラゴン: {last['len']}連続→継続"}

        return None
