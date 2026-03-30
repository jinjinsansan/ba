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
        """シュー終了時の通知 — メイン通知 + 分析結果"""

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
        )

        # 規則性判定
        regularity = summary.get("regularity", "")
        reg_score = summary.get("regularity_score", 0)
        if regularity:
            reg_emoji = "✅" if regularity == "規則性" else "⚠️"
            msg += (
                f"\n{reg_emoji} 判定: {regularity} (スコア: {reg_score})\n"
            )

        # パターン分析
        patterns = summary.get("pattern_breakdown", {})
        dominant = summary.get("dominant_pattern", "")
        if patterns:
            msg += f"📋 パターン分析:\n"
            for name, pct in sorted(patterns.items(), key=lambda x: -x[1]):
                bar = "█" * (pct // 10)
                marker = " ◀" if name == dominant else ""
                msg += f"  {name}: {pct}% {bar}{marker}\n"

        # 流れ分割
        flow_type = summary.get("flow_type", "")
        if flow_type:
            msg += f"🔄 流れ: {flow_type}\n"

        # 出目順
        seq = summary.get("result_sequence", "")
        if seq:
            display_seq = self._format_sequence(seq)
            msg += f"\n📝 出目:\n  {display_seq}\n"

        msg += (
            f"\n🔥 B最大連続: {summary['max_banker_streak']}回\n"
            f"⚡ P最大連続: {summary['max_player_streak']}回\n"
        )

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

    # === BET通知 ===

    def notify_bet_placed(self, bet_info: dict):
        """BET実行通知"""
        side_emoji = "🔵" if bet_info["side"] == "player" else "🔴"
        side_name = "Player" if bet_info["side"] == "player" else "Banker"
        self.send(
            f"🎯 BET実行\n"
            f"📍 {bet_info.get('table_name', '')}\n"
            f"{side_emoji} {side_name} ${bet_info.get('amount', 0):.2f}\n"
            f"📋 {bet_info.get('reason', '')}\n"
            f"📊 規則性: {bet_info.get('regularity_score', 0)}"
        )

    def notify_bet_result(self, bet_result: dict):
        """BET結果通知"""
        result = bet_result.get("result", "")
        profit = bet_result.get("profit", 0)
        emoji = "✅" if result == "win" else "❌" if result == "lose" else "➖"
        self.send(
            f"{emoji} BET結果: {result.upper()}\n"
            f"📍 {bet_result.get('table_name', '')}\n"
            f"💰 収支: ${profit:+.2f}\n"
            f"📊 累計: ${bet_result.get('cumulative_profit', 0):+.2f}"
        )

    def notify_session_summary(self, session: dict):
        """セッション収支通知"""
        self.send(
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 BETレポート\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"📊 セッション結果\n"
            f"  BET回数: {session.get('total_bets', 0)}\n"
            f"  勝ち: {session.get('wins', 0)} "
            f"({session.get('win_rate', 0):.1f}%)\n"
            f"  負け: {session.get('losses', 0)}\n"
            f"  収支: ${session.get('total_profit', 0):+.2f}\n"
            f"\n"
            f"🎯 戦略: {session.get('strategy', '')}\n"
            f"\n"
            f"💵 資金状況\n"
            f"  開始: ${session.get('starting_balance', 0):.2f}\n"
            f"  現在: ${session.get('ending_balance', 0):.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )

    def notify_daily_limit(self, limit_type: str, amount: float):
        """日次制限到達通知"""
        if limit_type == "loss":
            self.send(
                f"🛑 日次損失上限到達\n"
                f"損失額: ${abs(amount):.2f}\n"
                f"自動停止します"
            )
        elif limit_type == "profit":
            self.send(
                f"🎉 日次利益目標達成\n"
                f"利益額: ${amount:.2f}\n"
                f"自動停止します"
            )
