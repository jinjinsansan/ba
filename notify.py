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

    def send(self, message: str):
        if not self.enabled:
            logger.info(f"[通知] {message}")
            return
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message},
                timeout=10,
            )
            if not resp.ok:
                logger.error(f"Telegram送信エラー: {resp.status_code}")
        except Exception as e:
            logger.error(f"Telegram送信エラー: {e}")

    def notify_startup(self, table_name: str):
        self.send(
            f"🃏 バカラモニター起動\n"
            f"テーブル: {table_name}\n"
            f"24時間結果を記録します"
        )

    def notify_result(self, table_name: str, result: str, stats: dict):
        """結果通知（大きな連勝時のみ）"""
        emoji = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}.get(result, "?")
        self.send(
            f"{emoji} {table_name}\n"
            f"直近: P{stats['player']} B{stats['banker']} T{stats['tie']}\n"
            f"({stats['total']}ラウンド)"
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
