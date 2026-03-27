"""シュー（Shoe）管理

バカラの1シュー（6〜8デッキのカードセット）を追跡し、
シュー終了時の統計を計算する。

シュー検出:
  - EvolutionのWSメッセージで "newShoe" / "shuffling" を検出
  - フォールバック: 80ハンド以上で結果が途絶えたら新シューと判定
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("baccarat.shoe")

JST = timezone(timedelta(hours=9))

# 通常1シューは60〜80ハンド。安全マージンを持たせる
MAX_HANDS_PER_SHOE = 100
# 新シュー判定のための無結果時間（秒）
NEW_SHOE_TIMEOUT = 180  # 3分（シャッフル＋カット時間）


class ShoeTracker:
    """1シューの結果を追跡"""

    def __init__(self, table_name: str = ""):
        self.table_name = table_name
        self.results: list[str] = []  # ["player", "banker", "tie", ...]
        self.shoe_number = 0
        self.started_at: datetime | None = None
        self._new_shoe_detected = False

    @property
    def hand_count(self) -> int:
        return len(self.results)

    @property
    def player_count(self) -> int:
        return self.results.count("player")

    @property
    def banker_count(self) -> int:
        return self.results.count("banker")

    @property
    def tie_count(self) -> int:
        return self.results.count("tie")

    @property
    def result_sequence(self) -> str:
        """出目履歴を文字列で返す（例: PPBBPPBBBT）"""
        mapping = {"player": "P", "banker": "B", "tie": "T"}
        return "".join(mapping.get(r, "?") for r in self.results)

    @property
    def max_banker_streak(self) -> int:
        """シュー内のバンカー最大連続数"""
        max_streak = 0
        current = 0
        for r in self.results:
            if r == "banker":
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    @property
    def max_player_streak(self) -> int:
        """シュー内のプレイヤー最大連続数"""
        max_streak = 0
        current = 0
        for r in self.results:
            if r == "player":
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    @property
    def all_streaks(self) -> list[dict]:
        """全ての連続記録を返す（バンカー連続のリスト）"""
        streaks = []
        current_type = ""
        current_count = 0
        for r in self.results:
            if r == current_type:
                current_count += 1
            else:
                if current_type and current_count > 0:
                    streaks.append({"type": current_type, "count": current_count})
                current_type = r
                current_count = 1
        if current_type and current_count > 0:
            streaks.append({"type": current_type, "count": current_count})
        return streaks

    def add_result(self, result: str):
        """結果を追加"""
        if result not in ("player", "banker", "tie"):
            logger.warning(f"不明な結果: {result}")
            return

        if not self.started_at:
            self.started_at = datetime.now(JST)

        self.results.append(result)
        logger.debug(
            f"Shoe #{self.shoe_number} Hand #{self.hand_count}: "
            f"{result.upper()} | 出目: {self.result_sequence[-20:]}"
        )

    def signal_new_shoe(self):
        """WebSocketから新シュー信号を受信"""
        self._new_shoe_detected = True
        logger.info("新シュー信号検出")

    def is_shoe_complete(self) -> bool:
        """シューが完了したかどうか"""
        # 1. WSから新シュー信号があった場合
        if self._new_shoe_detected and self.hand_count > 0:
            return True

        # 2. ハンド数がMAXを超えた場合（安全策）
        if self.hand_count >= MAX_HANDS_PER_SHOE:
            logger.info(f"最大ハンド数({MAX_HANDS_PER_SHOE})到達 — シュー完了と判定")
            return True

        return False

    def get_summary(self) -> dict:
        """シューのサマリーを返す"""
        return {
            "shoe_number": self.shoe_number,
            "table_name": self.table_name,
            "hand_count": self.hand_count,
            "player_count": self.player_count,
            "banker_count": self.banker_count,
            "tie_count": self.tie_count,
            "result_sequence": self.result_sequence,
            "max_banker_streak": self.max_banker_streak,
            "max_player_streak": self.max_player_streak,
            "started_at": self.started_at.isoformat() if self.started_at else "",
            "ended_at": datetime.now(JST).isoformat(),
        }

    def reset(self):
        """新しいシューのためにリセット"""
        self.results.clear()
        self.started_at = None
        self._new_shoe_detected = False
        self.shoe_number += 1
        logger.info(f"新シュー開始: #{self.shoe_number}")
