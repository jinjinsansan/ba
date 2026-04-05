"""LAPLACE Logic API HTTP client.

Provides a drop-in replacement for MaruBatsuBetSession that delegates
ALL logic decisions and state management to the VPS-hosted API server.

The local side only handles:
  - Camoufox browser / Stake navigation (scraper.py)
  - BetExecutor physical BET placement
  - Telegram notifications (via CompositeNotifier)

This class exposes the same interface as MaruBatsuBetSession so that
agent_api.py can swap implementations with a single flag.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from marubatsu_strategy import SEQ, SetData
from notify import TelegramNotifier

logger = logging.getLogger("baccarat.laplace_client")

DEFAULT_TIMEOUT = 10.0


class LaplaceApiError(RuntimeError):
    """Raised when the VPS API returns an error or is unreachable."""


class LaplaceClient:
    """Low-level HTTP client for the LAPLACE Logic API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = self._url(path)
        try:
            resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as e:
            raise LaplaceApiError(f"{method} {path}: {e}") from e
        if not resp.ok:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise LaplaceApiError(f"{method} {path} -> {resp.status_code}: {body}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # --- Endpoints ---

    def health(self) -> dict:
        return self._request("GET", "/api/health")

    def create_session(
        self,
        user_id: str,
        chip_base: float,
        profit_stop: int,
        loss_cut: int,
        resume: bool = True,
    ) -> dict:
        body = {
            "user_id": user_id,
            "chip_base": chip_base,
            "profit_stop": profit_stop,
            "loss_cut": loss_cut,
            "resume": resume,
        }
        return self._request("POST", "/api/sessions", json=body)

    def get_session(self, user_id: str) -> dict:
        return self._request("GET", f"/api/sessions/{user_id}")

    def update_session(
        self,
        user_id: str,
        chip_base: Optional[float] = None,
        profit_stop: Optional[int] = None,
        loss_cut: Optional[int] = None,
    ) -> dict:
        body: dict[str, Any] = {}
        if chip_base is not None:
            body["chip_base"] = chip_base
        if profit_stop is not None:
            body["profit_stop"] = profit_stop
        if loss_cut is not None:
            body["loss_cut"] = loss_cut
        return self._request("PATCH", f"/api/sessions/{user_id}", json=body)

    def decide(self, user_id: str) -> dict:
        return self._request("POST", f"/api/sessions/{user_id}/decide")

    def submit_result(self, user_id: str, result: str) -> dict:
        return self._request(
            "POST", f"/api/sessions/{user_id}/result", json={"result": result}
        )

    def reset(self, user_id: str) -> dict:
        return self._request("POST", f"/api/sessions/{user_id}/reset")

    def shoe_change(self, user_id: str) -> dict:
        return self._request("POST", f"/api/sessions/{user_id}/shoe-change")

    def delete(self, user_id: str) -> dict:
        return self._request("DELETE", f"/api/sessions/{user_id}")


# ======== Local shim objects that mimic marubatsu_strategy types ========
# This lets the existing agent_api.py code continue to read
# session.tracker.current_turns, session.tracker.sets, etc.


class _RemoteTracker:
    """Read-only shim that exposes the same attributes as MaruBatsuTracker."""

    def __init__(self, chip_base: float):
        self.chip_base = chip_base
        self.sets: list[SetData] = []
        self.current_turns: list[str] = []
        self.total_o = 0
        self.total_x = 0
        self.current_unit_idx = 0
        self.cumulative_profit = 0
        self.prev_overshoot = 0
        self.current_set_index = 1
        self.current_turn_number = 1

    def apply_state(self, state: dict) -> None:
        self.chip_base = state.get("chip_base", self.chip_base)
        self.sets = [SetData(**sd) for sd in state.get("sets", [])]
        # State returns turns_display but not raw array; reconstruct from total turns
        # by using turns_display char-by-char (single char O/X)
        turns_display = state.get("turns_display", "")
        self.current_turns = list(turns_display)
        self.total_o = state.get("total_o", 0)
        self.total_x = state.get("total_x", 0)
        self.current_unit_idx = state.get("current_unit_idx", 0)
        self.cumulative_profit = state.get("cumulative_profit", 0)
        self.prev_overshoot = state.get("overshoot", 0)
        self.current_turn_number = len(self.current_turns) + 1
        self.current_set_index = len(self.sets) + 1


# ======== High-level wrapper compatible with MaruBatsuBetSession ========


class RemoteLaplaceSession:
    """Drop-in replacement for MaruBatsuBetSession backed by the VPS API.

    Only the logic + persistence + stats live on the VPS. The local side
    is responsible for:
      - Camoufox scraper / live WebSocket monitoring
      - executor.place_bet / wait_for_result
      - Telegram notifications
    """

    def __init__(
        self,
        executor,
        notifier: TelegramNotifier,
        chip_base: float = 1.0,
        loss_cut: int = 200,
        dry_run: bool = False,
        profit_stop: int = 50,
        resume: bool = True,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.executor = executor
        self.notifier = notifier
        self.chip_base = chip_base
        self.loss_cut = loss_cut
        self.profit_stop = profit_stop
        self.dry_run = dry_run
        self.resume = resume

        self.user_id = user_id or os.getenv("LAPLACE_USER", "dev-machine")
        self.api_url = api_url or os.getenv(
            "LAPLACE_API_URL", "http://127.0.0.1:8000"
        )
        self.api_key = api_key or os.getenv("LAPLACE_API_KEY", "")

        self.client = LaplaceClient(self.api_url, self.api_key)
        self.tracker = _RemoteTracker(chip_base=chip_base)

        # Local mirrors of state (updated from API responses)
        self.session_count = 0
        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0

        # Create / resume remote session
        try:
            health = self.client.health()
            logger.info(f"LAPLACE API health: {health}")
        except LaplaceApiError as e:
            raise LaplaceApiError(
                f"LAPLACE API unreachable at {self.api_url} (tunnel open?): {e}"
            )

        resp = self.client.create_session(
            user_id=self.user_id,
            chip_base=chip_base,
            profit_stop=profit_stop,
            loss_cut=loss_cut,
            resume=resume,
        )
        self._apply_state(resp["state"])
        logger.info(
            f"Remote session {'resumed' if resp.get('resumed') else 'created'}: "
            f"user={self.user_id} sets={len(self.tracker.sets)} "
            f"cp={self.tracker.cumulative_profit:+d}chip"
        )

    def _apply_state(self, state: dict) -> None:
        self.tracker.apply_state(state)
        self.session_count = state.get("session_count", 0)
        self.total_bets = state.get("total_bets", 0)
        self.total_wins = state.get("total_wins", 0)
        self.total_losses = state.get("total_losses", 0)
        self.total_ties = state.get("total_ties", 0)
        # Keep local profit_stop/loss_cut in sync with server
        self.profit_stop = state.get("profit_stop", self.profit_stop)
        self.loss_cut = state.get("loss_cut", self.loss_cut)
        self.chip_base = state.get("chip_base", self.chip_base)
        self.tracker.chip_base = self.chip_base

    # --- Config live update ---

    def update_config(
        self,
        profit_stop: Optional[int] = None,
        loss_cut: Optional[int] = None,
        chip_base: Optional[float] = None,
    ) -> None:
        resp = self.client.update_session(
            self.user_id,
            profit_stop=profit_stop,
            loss_cut=loss_cut,
            chip_base=chip_base,
        )
        self._apply_state(resp["state"])

    # --- Compatibility helpers ---

    def get_bet_amount(self) -> float:
        unit = SEQ[self.tracker.current_unit_idx]
        return unit * self.chip_base

    def effective_profit(self) -> int:
        cp = self.tracker.cumulative_profit
        turns = self.tracker.current_turns
        if turns:
            wins = turns.count("O")
            losses = turns.count("X")
            unit = SEQ[self.tracker.current_unit_idx]
            cp += (wins - losses) * unit
        return cp

    def should_reset(self) -> bool:
        cp = self.effective_profit()
        return cp >= self.profit_stop or cp <= -self.loss_cut

    # --- BET cycle (mirrors MaruBatsuBetSession.run_round) ---

    def run_round(self, running_flag) -> dict:
        if not running_flag():
            return {"action": "exit"}

        if not self.executor.check_and_dismiss_error():
            logger.warning("エラーダイアログ検出 → セッション中断")
            return {"action": "exit"}

        is_first = (self.total_bets == 0 and len(self.tracker.current_turns) == 0)
        if not self.executor.wait_for_betting_phase(
            timeout=180 if is_first else 120, skip_round=is_first
        ):
            if not self.executor.check_and_dismiss_error():
                return {"action": "exit"}
            logger.warning("BETフェーズ待ちタイムアウト")
            return {"action": "exit"}

        # Ask the server for the next BET parameters (always player side)
        try:
            decision = self.client.decide(self.user_id)
        except LaplaceApiError as e:
            logger.error(f"API decide failed: {e}")
            return {"action": "exit"}

        self._apply_state(decision["state"])

        if decision["action"] == "reset":
            # Let the outer loop handle the reset branch
            return {
                "action": "bet",
                "result": None,
                "won": None,
                "bet_amount": 0.0,
                "completed_set": None,
                "should_reset": True,
            }

        bet_amount = float(decision["bet_amount"])
        unit = int(decision["unit_chips"])
        unit_idx = int(decision["unit_idx"])
        turn_num = int(decision["turn_number"])
        set_idx = int(decision["set_index"])

        # Balance check
        if not self.dry_run:
            balance = self.executor.get_balance()
            if balance < bet_amount:
                logger.error(f"残高不足: ${balance:.2f} < ${bet_amount:.2f}")
                self.notifier.send(
                    f"⚠️ 残高不足!\n"
                    f"必要: ${bet_amount:.2f} (SEQ[{unit_idx}]={unit})\n"
                    f"残高: ${balance:.2f}"
                )
                return {"action": "exit"}

        side = "player"
        logger.info(
            f"BET: ${bet_amount:.0f} {side.upper()} "
            f"(SEQ[{unit_idx}]={unit}, Set#{set_idx} Turn{turn_num}/7) [remote]"
        )

        if not self.executor.place_bet(side, bet_amount):
            logger.error("BET失敗")
            return {"action": "exit"}

        # wait for result
        result_info = self.executor.wait_for_result(timeout=90, bet_amount=bet_amount)
        if not result_info or not result_info.get("result"):
            logger.error("結果取得失敗")
            return {"action": "exit"}

        result = result_info["result"]
        balance = result_info.get("balance", 0)

        # Submit to server
        try:
            resp = self.client.submit_result(self.user_id, result)
        except LaplaceApiError as e:
            logger.error(f"API submit_result failed: {e}")
            return {"action": "exit"}

        self._apply_state(resp["state"])

        completed_dict = resp.get("completed_set")
        completed_set: Optional[SetData] = None
        if completed_dict:
            # Reconstruct SetData for downstream code that uses attribute access
            completed_set = SetData(
                set_index=completed_dict["set_index"],
                results=completed_dict["results"],
                wins=completed_dict["wins"],
                losses=completed_dict["losses"],
                overshoot=completed_dict["overshoot"],
                slashed=False,
                used_unit_idx=completed_dict["used_unit_idx"],
                next_unit_idx=completed_dict["next_unit_idx"],
                set_profit=completed_dict["set_profit"],
                cumulative_profit=completed_dict["cumulative_profit"],
            )

        won = resp.get("won")
        need_reset = bool(resp.get("should_reset"))

        # Handle tie / notifications (same as local version)
        if result == "tie":
            logger.info(f"Tie — BET返還、〇❌に影響なし (残高${balance:.2f})")
            return {
                "action": "bet",
                "result": "tie",
                "won": None,
                "bet_amount": bet_amount,
                "completed_set": None,
                "should_reset": need_reset,
            }

        mark = "〇" if won else "✕"
        logger.info(f"結果: {result.upper()} → {mark} (残高${balance:.2f})")

        # Turn notification (same shape as local version)
        turns_display = "".join(
            "〇" if t == "O" else "✕" for t in self.tracker.current_turns
        )
        if not completed_set:
            remaining = 7 - len(self.tracker.current_turns)
            turns_display += "_" * remaining

        try:
            self.notifier.send(
                f"{'〇 的中!' if won else '✕ ハズレ'} Turn {turn_num}/7\n"
                f"結果: {result.upper()} (BET: Player ${bet_amount:.0f})\n"
                f"{turns_display}\n"
                f"残高: ${balance:.2f}"
            )
        except Exception as e:
            logger.warning(f"notify failed: {e}")

        if completed_set:
            self._notify_set_complete(completed_set, balance)

        return {
            "action": "bet",
            "result": result,
            "won": won,
            "bet_amount": bet_amount,
            "completed_set": completed_set,
            "should_reset": need_reset,
        }

    def _notify_set_complete(self, new_set: SetData, balance: float) -> None:
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
        try:
            self.notifier.send(msg)
        except Exception as e:
            logger.warning(f"set-complete notify failed: {e}")
        logger.info(
            f"Set #{new_set.set_index} 確定: {new_set.results} "
            f"{new_set.wins}/{new_set.losses} "
            f"P/L:{new_set.cumulative_profit:+d} [remote]"
        )

    def reset_session(self, reason: str) -> None:
        try:
            resp = self.client.reset(self.user_id)
            self._apply_state(resp["state"])
        except LaplaceApiError as e:
            logger.error(f"API reset failed: {e}")

    def handle_shoe_change(self) -> None:
        if not self.tracker.current_turns:
            return
        partial = "".join(
            "〇" if t == "O" else "✕" for t in self.tracker.current_turns
        )
        logger.info(f"シュー交換 — 途中ターン破棄: {partial} [remote]")
        try:
            self.notifier.send(
                f"⚠️ シュー交換\n"
                f"途中ターン破棄: {partial} ({len(self.tracker.current_turns)}/7)\n"
                f"累計損益: {self.tracker.cumulative_profit:+d} chip"
            )
        except Exception:
            pass
        try:
            resp = self.client.shoe_change(self.user_id)
            self._apply_state(resp["state"])
        except LaplaceApiError as e:
            logger.error(f"API shoe_change failed: {e}")

    def get_summary(self) -> dict:
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
