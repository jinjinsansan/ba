"""ゲーム内WebSocket状態管理

テーブル入場後のEvolution WSメッセージ (framesent) を傍受し、
ラウンド状態・BET受理・結果・残高を提供する。

状態遷移:
  Idle → Betting → (BETクリック) → Accepted → Settled → Idle → Betting → ...

WSメッセージ (CLIENT_BET_ACCEPTED の status フィールド):
  "Idle"     = ディーリング中 / ラウンド間
  "Betting"  = BETフェーズ (チップ配置可能)
  "Accepted" = BET受理完了
  "Settled"  = 結果確定
"""
import json
import threading
import time
import logging

logger = logging.getLogger("baccarat.game_ws")


class GameWSMonitor:
    """ゲーム内WS状態を追跡"""

    def __init__(self):
        self._lock = threading.Lock()
        self._status = "unknown"       # Idle / Betting / Accepted / Settled
        self._balance = 0.0
        self._last_confirmed = {}      # {"Player": 1, "PlayerFee": 0.2}
        self._last_result_multiplier = None  # {"betSpot": "Player", "multiplier": 2}
        self._settled_balance = None   # Settled時の残高
        self._status_changed = threading.Event()
        self._connected = False

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def balance(self) -> float:
        with self._lock:
            return self._balance

    @property
    def is_connected(self) -> bool:
        return self._connected

    def reset(self):
        with self._lock:
            self._status = "unknown"
            self._last_confirmed = {}
            self._last_result_multiplier = None
            self._settled_balance = None
            self._connected = False
        self._status_changed.clear()

    def on_ws_message(self, raw: str):
        """WSメッセージ (framesent/framereceived) を処理"""
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(data, dict):
            return

        self._connected = True

        log_entry = data.get("log", {})
        if not log_entry:
            # framereceived形式: {"type":"...", "args":{...}} の可能性
            msg_type = data.get("type", "")
            args = data.get("args", {})
            if msg_type and args:
                self._handle_server_message(msg_type, args)
            return

        msg_type = log_entry.get("type", "")
        value = log_entry.get("value", {})

        if "BET" in msg_type or "BALANCE" in msg_type or "MULTIPLIER" in msg_type or "SETTLED" in msg_type or "RESULT" in msg_type:
            status = value.get("status", "")
            logger.info(f"WS: {msg_type} status={status}")

        if msg_type == "CLIENT_BET_ACCEPTED":
            self._handle_bet_accepted(value)
        elif msg_type == "CLIENT_BALANCE_UPDATED":
            self._handle_balance_updated(value)
        elif msg_type == "CLIENT_BACCARAT_TOTAL_MULTIPLIER_DISPLAYED":
            self._handle_multiplier(value)
        elif msg_type == "CLIENT_RECEIVED_BET_RESPONSE":
            self._handle_bet_response(value)

    def _handle_bet_accepted(self, value: dict):
        new_status = value.get("status", "")
        if not new_status:
            return

        with self._lock:
            old = self._status
            self._status = new_status

            bal = value.get("balance")
            if bal is not None:
                self._balance = float(bal)

            confirmed = value.get("confirmed", {})
            if confirmed:
                self._last_confirmed = confirmed

            if new_status == "Settled":
                self._settled_balance = self._balance

        if old != new_status:
            logger.debug(f"ラウンド状態: {old} → {new_status}")
            self._status_changed.set()

    def _handle_balance_updated(self, value: dict):
        bal = value.get("balance")
        if bal is not None:
            with self._lock:
                self._balance = float(bal)

    def _handle_multiplier(self, value: dict):
        with self._lock:
            self._last_result_multiplier = {
                "betSpot": value.get("betSpot", ""),
                "multiplier": value.get("multiplier", 0),
            }

    def _handle_bet_response(self, value: dict):
        state = value.get("state", {})
        total = state.get("totalAmount", 0)
        if total > 0:
            logger.debug(f"BET応答: totalAmount={total}")

    def _handle_server_message(self, msg_type: str, args: dict):
        """サーバー→クライアントのメッセージ処理 (framereceived)"""
        # ラウンド結果通知
        if "result" in msg_type.lower() or "settled" in msg_type.lower():
            logger.info(f"サーバーメッセージ: {msg_type} args_keys={list(args.keys())[:5]}")
        # ゲーム状態変化
        if "gameState" in args or "status" in args:
            status = args.get("status") or args.get("gameState", {}).get("status")
            if status:
                with self._lock:
                    old = self._status
                    self._status = status
                if old != status:
                    logger.debug(f"サーバー状態: {old} → {status}")
                    self._status_changed.set()

    # === 待機メソッド ===

    def wait_for_status(self, target: str, timeout: float = 60) -> bool:
        """指定ステータスになるまで待機。成功=True"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.status == target:
                return True
            self._status_changed.clear()
            remaining = deadline - time.time()
            if remaining > 0:
                self._status_changed.wait(timeout=min(remaining, 1.0))
        return self.status == target

    def wait_for_betting_phase(self, timeout: float = 120, dom_checker=None) -> bool:
        """1ラウンド見送り後、次のBETフェーズを待機 (DOMベース)。

        フロー:
          1. タイマー非表示を待つ (=BETフェーズ終了)
          2. タイマー表示を待つ (=次のBETフェーズ開始)
        """
        if not dom_checker:
            logger.warning("dom_checker未設定")
            return False

        logger.info("1ラウンド見送り中...")
        deadline = time.time() + timeout

        # Step 1: タイマーが消えるのを待つ (BETフェーズ外になるのを待つ)
        while time.time() < deadline:
            if not dom_checker():
                logger.info("ディーリング中 (タイマー消失)")
                break
            time.sleep(1.0)
        else:
            logger.warning("タイマー消失待ちタイムアウト")
            return False

        # Step 2: 次のタイマー表示を待つ (次のBETフェーズ開始)
        logger.info("次のBETフェーズを待機...")
        while time.time() < deadline:
            if dom_checker():
                logger.info("BETフェーズ開始")
                return True
            time.sleep(1.0)

        logger.warning("BETフェーズ待機タイムアウト")
        return False

    def wait_for_accepted(self, timeout: float = 30) -> bool:
        """BET受理 (status=Accepted) を待機"""
        return self.wait_for_status("Accepted", timeout)

    def wait_for_settled(self, timeout: float = 60) -> dict | None:
        """結果確定を待機。Settled または Idle (BET後の結果) を待つ"""
        logger.info("勝敗を待ちます...")

        deadline = time.time() + timeout
        while time.time() < deadline:
            s = self.status
            if s in ("Settled", "Idle"):
                logger.info(f"結果確定 (状態: {s})")
                with self._lock:
                    return {
                        "balance": self._balance,
                        "confirmed": dict(self._last_confirmed),
                        "multiplier": dict(self._last_result_multiplier) if self._last_result_multiplier else None,
                    }
            self._status_changed.clear()
            self._status_changed.wait(timeout=1.0)

        logger.warning("結果待ちタイムアウト")
        return None

    def get_result_side(self) -> str | None:
        """直近の結果 (player/banker/tie) を返す。
        multiplier の betSpot + confirmed の内容から判定"""
        with self._lock:
            mult = self._last_result_multiplier
            if mult and mult.get("betSpot"):
                return mult["betSpot"].lower()
        return None
