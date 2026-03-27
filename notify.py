"""Telegram通知"""
import logging
import requests

logger = logging.getLogger("baccarat.notify")


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)
        if not self.enabled:
            logger.info("Telegram通知無効（設定なし）")

    def send(self, message: str, parse_mode: str = ""):
        if not self.enabled:
            logger.info(f"[通知] {message}")
            return
        try:
            payload = {"chat_id": self.chat_id, "text": message}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
                timeout=10,
            )
            if not resp.ok:
                logger.error(f"Telegram送信エラー: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Telegram送信エラー: {e}")

    def notify_startup(self, table_name: str):
        self.send(
            f"🃏 バカラモニター起動\n"
            f"テーブル: {table_name}\n"
            f"シュー単位で結果を記録・通知します"
        )

    def notify_shoe_complete(self, summary: dict):
        """シュー終了時の通知 — メイン通知"""
        seq = summary["result_sequence"]
        # 出目を見やすく色付き絵文字に変換
        display_seq = self._format_sequence(seq)

        # バンカー連続の詳細
        banker_streaks = self._get_banker_streak_detail(summary["result_sequence"])

        msg = (
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🃏 シュー #{summary['shoe_number']} 完了\n"
            f"📍 {summary['table_name']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"📊 結果 ({summary['hand_count']}ハンド)\n"
            f"  🔵 Player: {summary['player_count']}\n"
            f"  🔴 Banker: {summary['banker_count']}\n"
            f"  🟢 Tie:    {summary['tie_count']}\n"
            f"\n"
            f"📝 出目:\n"
            f"  {display_seq}\n"
            f"\n"
            f"🔥 バンカー最大連続: {summary['max_banker_streak']}回\n"
            f"⚡ プレイヤー最大連続: {summary['max_player_streak']}回\n"
        )

        if banker_streaks:
            msg += f"\n📈 バンカー連続詳細:\n{banker_streaks}\n"

        msg += f"━━━━━━━━━━━━━━━━━━━"

        self.send(msg)

    def notify_hand_result(self, hand_num: int, result: str, shoe_summary: dict):
        """各ハンドの結果を簡易通知（オプション）"""
        emoji = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}.get(result, "?")
        seq = shoe_summary["result_sequence"][-20:]  # 直近20手
        display = self._format_sequence(seq)
        self.send(
            f"{emoji} Hand #{hand_num}\n"
            f"直近: {display}\n"
            f"P:{shoe_summary['player_count']} "
            f"B:{shoe_summary['banker_count']} "
            f"T:{shoe_summary['tie_count']}"
        )

    def notify_report(self, table_name: str, stats: dict, streak: dict):
        """定期レポート"""
        self.send(
            f"━━ バカラレポート ━━\n"
            f"テーブル: {table_name}\n"
            f"\n"
            f"📊 24時間統計 ({stats['total']}ラウンド)\n"
            f"  🔵 Player: {stats['player']} ({stats['player_pct']}%)\n"
            f"  🔴 Banker: {stats['banker']} ({stats['banker_pct']}%)\n"
            f"  🟢 Tie:    {stats['tie']} ({stats['tie_pct']}%)\n"
            f"  ペア: P={stats['player_pair']} B={stats['banker_pair']}\n"
            f"\n"
            f"現在: {streak['current']} {streak['count']}連続"
        )

    def notify_shutdown(self, reason: str = ""):
        self.send(f"⛔ バカラモニター停止{': ' + reason if reason else ''}")

    def _format_sequence(self, seq: str) -> str:
        """出目文字列を絵文字付きに変換（例: PPBBT → 🔵🔵🔴🔴🟢）"""
        mapping = {"P": "🔵", "B": "🔴", "T": "🟢"}
        # 長い出目は改行で折り返す（30文字ごと）
        chars = [mapping.get(c, c) for c in seq]
        lines = []
        chunk_size = 30
        for i in range(0, len(chars), chunk_size):
            lines.append("".join(chars[i:i + chunk_size]))
        return "\n  ".join(lines)

    def _get_banker_streak_detail(self, seq: str) -> str:
        """バンカー連続の詳細を返す"""
        streaks = []
        current = 0
        start_pos = 0
        for i, c in enumerate(seq):
            if c == "B":
                if current == 0:
                    start_pos = i + 1  # 1-based
                current += 1
            else:
                if current >= 3:  # 3連続以上のみ表示
                    streaks.append(f"  Hand {start_pos}〜: {current}連続🔴")
                current = 0
        if current >= 3:
            streaks.append(f"  Hand {start_pos}〜: {current}連続🔴")

        return "\n".join(streaks) if streaks else ""
