"""LAPLACE Logic API (FastAPI)

VPS 上で稼働する LAPLACE ロジックエンジン API。
GUI (ローカル PC) からの BET 判断依頼/結果報告を受け付け、
MaruBatsuTracker のロジックと状態管理を一元化する。

エンドポイント:
  POST   /api/sessions               - セッション作成 (user_id 指定)
  GET    /api/sessions/{user_id}     - 現在の状態取得
  POST   /api/sessions/{user_id}/decide       - 次 BET 情報を取得
  POST   /api/sessions/{user_id}/result       - ハンド結果を報告 → 次アクション返却
  POST   /api/sessions/{user_id}/reset        - セッションリセット (利確/損切り)
  POST   /api/sessions/{user_id}/shoe-change  - シュー交換処理
  DELETE /api/sessions/{user_id}     - セッション削除
  GET    /api/health                 - ヘルスチェック

認証: Bearer トークン (LAPLACE_API_KEY 環境変数)
状態永続化: /opt/laplace/api_state/{user_id}.json
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure we can import marubatsu_strategy from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marubatsu_strategy import MaruBatsuTracker, SetData, SEQ
from bot_manager import get_bot_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("laplace.api")

# --- Configuration ---
API_KEY = os.getenv("LAPLACE_API_KEY", "").strip()
STATE_DIR = Path(os.getenv("LAPLACE_STATE_DIR", "/opt/laplace/api_state"))
STATE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PROFIT_STOP = 50
DEFAULT_LOSS_CUT = 200
DEFAULT_CHIP_BASE = 1.0

# --- Thread-safe session store ---
_sessions_lock = threading.RLock()


# ======== Models ========

class CreateSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    chip_base: float = Field(DEFAULT_CHIP_BASE, gt=0)
    profit_stop: int = Field(DEFAULT_PROFIT_STOP, gt=0)
    loss_cut: int = Field(DEFAULT_LOSS_CUT, gt=0)
    resume: bool = True


class UpdateConfigRequest(BaseModel):
    chip_base: Optional[float] = None
    profit_stop: Optional[int] = None
    loss_cut: Optional[int] = None


class ResultRequest(BaseModel):
    result: str = Field(..., description="player | banker | tie")


class SessionState(BaseModel):
    user_id: str
    chip_base: float
    profit_stop: int
    loss_cut: int
    session_count: int
    total_bets: int
    total_wins: int
    total_losses: int
    total_ties: int
    set_count: int
    current_turn: int
    current_unit_idx: int
    current_unit: int
    cumulative_profit: int
    cumulative_money: float
    effective_profit: int
    overshoot: int
    total_o: int
    total_x: int
    turns_display: str
    sets: list[dict]
    should_reset: bool
    reset_reason: Optional[str]
    created_at: str
    updated_at: str


class DecideResponse(BaseModel):
    action: str  # "bet" | "reset"
    side: str    # "player" (常に)
    unit_idx: int
    unit_chips: int
    bet_amount: float  # chip_base * unit
    turn_number: int
    set_index: int
    state: SessionState


class ResultResponse(BaseModel):
    accepted: bool
    result: str
    won: Optional[bool]
    completed_set: Optional[dict]
    should_reset: bool
    reset_reason: Optional[str]
    state: SessionState


class BotStartRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    target_table_name: str = Field(
        "Japanese Speed Baccarat A",
        description="Fixed target table name for verification mode",
    )
    dry_run: bool = True
    chip_base: float = Field(DEFAULT_CHIP_BASE, gt=0)
    profit_stop: int = Field(DEFAULT_PROFIT_STOP, gt=0)
    loss_cut: int = Field(DEFAULT_LOSS_CUT, gt=0)
    resume_session: bool = True


class BotStartResponse(BaseModel):
    started: bool
    run_id: str
    pid: int
    log_path: str
    config: dict


class BotStopResponse(BaseModel):
    was_running: bool
    run_id: Optional[str] = None
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    stopped_at: Optional[float] = None


class BotStatusResponse(BaseModel):
    running: bool
    run_id: Optional[str]
    pid: Optional[int]
    started_at: Optional[float]
    uptime_seconds: Optional[float]
    log_path: Optional[str]
    config: Optional[dict]
    last_exit: Optional[dict]
    session_state: Optional[SessionState] = None


# ======== Auth ========

async def verify_api_key(authorization: Optional[str] = Header(None)):
    if not API_KEY:
        # No API key configured → open access (dev mode)
        return True
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization[len("Bearer ") :].strip()
    if token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return True


# ======== Session Wrapper ========

class LaplaceSession:
    """Pure-logic wrapper around MaruBatsuTracker with persistence."""

    def __init__(
        self,
        user_id: str,
        chip_base: float = DEFAULT_CHIP_BASE,
        profit_stop: int = DEFAULT_PROFIT_STOP,
        loss_cut: int = DEFAULT_LOSS_CUT,
    ):
        self.user_id = user_id
        self.chip_base = chip_base
        self.profit_stop = profit_stop
        self.loss_cut = loss_cut

        self.tracker = MaruBatsuTracker(chip_base=chip_base)
        self.session_count = 0
        self.total_bets = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0
        self.created_at = datetime.utcnow().isoformat() + "Z"
        self.updated_at = self.created_at

    # --- Persistence ---

    @property
    def state_path(self) -> Path:
        # Sanitize user_id for filesystem safety
        safe = "".join(c for c in self.user_id if c.isalnum() or c in ("-", "_"))
        return STATE_DIR / f"{safe or 'default'}.json"

    def save(self) -> None:
        state = {
            "user_id": self.user_id,
            "chip_base": self.chip_base,
            "profit_stop": self.profit_stop,
            "loss_cut": self.loss_cut,
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
            "created_at": self.created_at,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        self.updated_at = state["updated_at"]
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, user_id: str) -> Optional["LaplaceSession"]:
        safe = "".join(c for c in user_id if c.isalnum() or c in ("-", "_")) or "default"
        path = STATE_DIR / f"{safe}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"load {user_id}: {e}")
            return None

        obj = cls(
            user_id=user_id,
            chip_base=data.get("chip_base", DEFAULT_CHIP_BASE),
            profit_stop=data.get("profit_stop", DEFAULT_PROFIT_STOP),
            loss_cut=data.get("loss_cut", DEFAULT_LOSS_CUT),
        )
        for sd in data.get("sets", []):
            obj.tracker.sets.append(SetData(**sd))
        obj.tracker.current_turns = data.get("current_turns", [])
        obj.tracker.total_o = data.get("total_o", 0)
        obj.tracker.total_x = data.get("total_x", 0)
        obj.session_count = data.get("session_count", 0)
        obj.total_bets = data.get("total_bets", 0)
        obj.total_wins = data.get("total_wins", 0)
        obj.total_losses = data.get("total_losses", 0)
        obj.total_ties = data.get("total_ties", 0)
        obj.created_at = data.get("created_at", datetime.utcnow().isoformat() + "Z")
        obj.updated_at = data.get("updated_at", obj.created_at)
        return obj

    def delete_state(self) -> None:
        try:
            if self.state_path.exists():
                self.state_path.unlink()
        except Exception as e:
            logger.warning(f"delete_state {self.user_id}: {e}")

    # --- Logic ---

    def effective_profit(self) -> int:
        cp = self.tracker.cumulative_profit
        turns = self.tracker.current_turns
        if turns:
            wins = turns.count("O")
            losses = turns.count("X")
            unit = SEQ[self.tracker.current_unit_idx]
            cp += (wins - losses) * unit
        return cp

    def should_reset(self) -> tuple[bool, Optional[str]]:
        cp = self.effective_profit()
        if cp >= self.profit_stop:
            return True, "利確"
        if cp <= -self.loss_cut:
            return True, "損切り"
        return False, None

    def add_result(self, result: str) -> tuple[Optional[SetData], Optional[bool]]:
        """Register a hand result. Returns (completed_set | None, won | None)."""
        if result not in ("player", "banker", "tie"):
            raise ValueError(f"invalid result: {result}")

        self.total_bets += 1
        if result == "tie":
            self.total_ties += 1
            return None, None

        won = result == "player"
        if won:
            self.total_wins += 1
        else:
            self.total_losses += 1

        completed = self.tracker.add_result(result)
        return completed, won

    def reset_session(self, reason: str) -> None:
        self.session_count += 1
        self.tracker.sets.clear()
        self.tracker.current_turns.clear()
        # Note: total_o/total_x/total_bets/wins/losses are not reset (cumulative stats)

    def handle_shoe_change(self) -> list[str]:
        discarded = list(self.tracker.current_turns)
        self.tracker.current_turns.clear()
        return discarded

    # --- Serialization ---

    def to_state(self) -> SessionState:
        turns = self.tracker.current_turns
        turns_display = "".join("O" if t == "O" else "X" for t in turns)
        cp = self.tracker.cumulative_profit
        ep = self.effective_profit()
        should, reason = self.should_reset()
        return SessionState(
            user_id=self.user_id,
            chip_base=self.chip_base,
            profit_stop=self.profit_stop,
            loss_cut=self.loss_cut,
            session_count=self.session_count,
            total_bets=self.total_bets,
            total_wins=self.total_wins,
            total_losses=self.total_losses,
            total_ties=self.total_ties,
            set_count=len(self.tracker.sets),
            current_turn=len(turns),
            current_unit_idx=self.tracker.current_unit_idx,
            current_unit=SEQ[self.tracker.current_unit_idx],
            cumulative_profit=cp,
            cumulative_money=cp * self.chip_base,
            effective_profit=ep,
            overshoot=self.tracker.prev_overshoot,
            total_o=self.tracker.total_o,
            total_x=self.tracker.total_x,
            turns_display=turns_display,
            sets=[
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
            should_reset=should,
            reset_reason=reason,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


# ======== In-memory session registry ========

_SESSIONS: dict[str, LaplaceSession] = {}


def get_or_load(user_id: str) -> Optional[LaplaceSession]:
    with _sessions_lock:
        if user_id in _SESSIONS:
            return _SESSIONS[user_id]
        loaded = LaplaceSession.load(user_id)
        if loaded:
            _SESSIONS[user_id] = loaded
        return loaded


def get_required(user_id: str) -> LaplaceSession:
    sess = get_or_load(user_id)
    if sess is None:
        raise HTTPException(status_code=404, detail=f"session '{user_id}' not found")
    return sess


# ======== FastAPI app ========

app = FastAPI(
    title="LAPLACE Logic API",
    version="1.0.0",
    description="VPS-hosted MaruBatsu logic engine for LAPLACE baccarat bot",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    with _sessions_lock:
        in_memory = len(_SESSIONS)
    disk_count = len(list(STATE_DIR.glob("*.json")))
    return {
        "status": "ok",
        "in_memory_sessions": in_memory,
        "persisted_sessions": disk_count,
        "auth_enabled": bool(API_KEY),
        "state_dir": str(STATE_DIR),
        "time": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/api/sessions", dependencies=[Depends(verify_api_key)])
async def create_session(req: CreateSessionRequest):
    with _sessions_lock:
        existing = get_or_load(req.user_id)
        if existing and req.resume:
            # Update config but keep state
            existing.chip_base = req.chip_base
            existing.profit_stop = req.profit_stop
            existing.loss_cut = req.loss_cut
            existing.tracker.chip_base = req.chip_base
            existing.save()
            logger.info(f"session resumed: {req.user_id}")
            return {"created": False, "resumed": True, "state": existing.to_state()}

        # Create fresh (or overwrite)
        if existing and not req.resume:
            existing.delete_state()
            _SESSIONS.pop(req.user_id, None)

        sess = LaplaceSession(
            user_id=req.user_id,
            chip_base=req.chip_base,
            profit_stop=req.profit_stop,
            loss_cut=req.loss_cut,
        )
        sess.save()
        _SESSIONS[req.user_id] = sess
        logger.info(f"session created: {req.user_id}")
        return {"created": True, "resumed": False, "state": sess.to_state()}


@app.get("/api/sessions/{user_id}", dependencies=[Depends(verify_api_key)])
async def get_session(user_id: str):
    with _sessions_lock:
        sess = get_required(user_id)
        return {"state": sess.to_state()}


@app.patch("/api/sessions/{user_id}", dependencies=[Depends(verify_api_key)])
async def update_session(user_id: str, req: UpdateConfigRequest):
    with _sessions_lock:
        sess = get_required(user_id)
        if req.chip_base is not None and req.chip_base > 0:
            sess.chip_base = req.chip_base
            sess.tracker.chip_base = req.chip_base
        if req.profit_stop is not None and req.profit_stop > 0:
            sess.profit_stop = req.profit_stop
        if req.loss_cut is not None and req.loss_cut > 0:
            sess.loss_cut = req.loss_cut
        sess.save()
        return {"updated": True, "state": sess.to_state()}


@app.post("/api/sessions/{user_id}/decide", dependencies=[Depends(verify_api_key)])
async def decide_bet(user_id: str):
    """Return next BET parameters (always Player side for maru-batsu)."""
    with _sessions_lock:
        sess = get_required(user_id)
        should, reason = sess.should_reset()
        if should:
            return DecideResponse(
                action="reset",
                side="player",
                unit_idx=sess.tracker.current_unit_idx,
                unit_chips=SEQ[sess.tracker.current_unit_idx],
                bet_amount=SEQ[sess.tracker.current_unit_idx] * sess.chip_base,
                turn_number=sess.tracker.current_turn_number,
                set_index=sess.tracker.current_set_index,
                state=sess.to_state(),
            )
        unit_idx = sess.tracker.current_unit_idx
        unit = SEQ[unit_idx]
        return DecideResponse(
            action="bet",
            side="player",
            unit_idx=unit_idx,
            unit_chips=unit,
            bet_amount=unit * sess.chip_base,
            turn_number=sess.tracker.current_turn_number,
            set_index=sess.tracker.current_set_index,
            state=sess.to_state(),
        )


@app.post("/api/sessions/{user_id}/result", dependencies=[Depends(verify_api_key)])
async def submit_result(user_id: str, req: ResultRequest):
    with _sessions_lock:
        sess = get_required(user_id)
        try:
            completed, won = sess.add_result(req.result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        completed_dict = None
        if completed:
            completed_dict = {
                "set_index": completed.set_index,
                "results": completed.results,
                "wins": completed.wins,
                "losses": completed.losses,
                "overshoot": completed.overshoot,
                "used_unit_idx": completed.used_unit_idx,
                "next_unit_idx": completed.next_unit_idx,
                "set_profit": completed.set_profit,
                "cumulative_profit": completed.cumulative_profit,
            }

        should, reason = sess.should_reset()
        sess.save()
        return ResultResponse(
            accepted=True,
            result=req.result,
            won=won,
            completed_set=completed_dict,
            should_reset=should,
            reset_reason=reason,
            state=sess.to_state(),
        )


@app.post("/api/sessions/{user_id}/reset", dependencies=[Depends(verify_api_key)])
async def reset_session_endpoint(user_id: str):
    with _sessions_lock:
        sess = get_required(user_id)
        should, reason = sess.should_reset()
        effective = sess.effective_profit()
        sess.reset_session(reason or "manual")
        sess.save()
        return {
            "reset": True,
            "reason": reason or "manual",
            "locked_profit": effective,
            "locked_money": effective * sess.chip_base,
            "state": sess.to_state(),
        }


@app.post("/api/sessions/{user_id}/shoe-change", dependencies=[Depends(verify_api_key)])
async def shoe_change(user_id: str):
    with _sessions_lock:
        sess = get_required(user_id)
        discarded = sess.handle_shoe_change()
        sess.save()
        return {
            "discarded_turns": discarded,
            "discarded_count": len(discarded),
            "state": sess.to_state(),
        }


@app.delete("/api/sessions/{user_id}", dependencies=[Depends(verify_api_key)])
async def delete_session(user_id: str):
    with _sessions_lock:
        sess = get_or_load(user_id)
        if sess is None:
            raise HTTPException(status_code=404, detail=f"session '{user_id}' not found")
        sess.delete_state()
        _SESSIONS.pop(user_id, None)
        return {"deleted": True, "user_id": user_id}


# ======== Bot control endpoints ========


@app.post(
    "/api/bot/start",
    response_model=BotStartResponse,
    dependencies=[Depends(verify_api_key)],
)
async def bot_start(req: BotStartRequest):
    """Spawn the bet runner subprocess with the given config.

    The runner will read config from LAPLACE_BOT_CONFIG env var (pointing
    to a JSON file written by the bot manager).
    """
    # Ensure a session exists for the user (create if missing)
    with _sessions_lock:
        sess = get_or_load(req.user_id)
        if sess is None:
            sess = LaplaceSession(
                user_id=req.user_id,
                chip_base=req.chip_base,
                profit_stop=req.profit_stop,
                loss_cut=req.loss_cut,
            )
            sess.save()
            _SESSIONS[req.user_id] = sess
            logger.info(f"bot_start: auto-created session {req.user_id}")
        else:
            # Sync live config
            sess.chip_base = req.chip_base
            sess.profit_stop = req.profit_stop
            sess.loss_cut = req.loss_cut
            sess.tracker.chip_base = req.chip_base
            if not req.resume_session:
                sess.delete_state()
                _SESSIONS.pop(req.user_id, None)
                sess = LaplaceSession(
                    user_id=req.user_id,
                    chip_base=req.chip_base,
                    profit_stop=req.profit_stop,
                    loss_cut=req.loss_cut,
                )
                _SESSIONS[req.user_id] = sess
            sess.save()

    mgr = get_bot_manager()
    try:
        info = mgr.start(req.dict())
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.info(f"bot_start: run_id={info['run_id']} pid={info['pid']}")
    return BotStartResponse(started=True, **info)


@app.post(
    "/api/bot/stop",
    response_model=BotStopResponse,
    dependencies=[Depends(verify_api_key)],
)
async def bot_stop():
    mgr = get_bot_manager()
    result = mgr.stop()
    logger.info(f"bot_stop: {result}")
    return BotStopResponse(**result)


@app.get(
    "/api/bot/status",
    response_model=BotStatusResponse,
    dependencies=[Depends(verify_api_key)],
)
async def bot_status():
    mgr = get_bot_manager()
    st = mgr.status()

    session_state = None
    cfg = st.get("config") or {}
    user_id = cfg.get("user_id")
    if user_id:
        with _sessions_lock:
            sess = get_or_load(user_id)
            if sess:
                session_state = sess.to_state()

    return BotStatusResponse(
        running=st["running"],
        run_id=st["run_id"],
        pid=st["pid"],
        started_at=st["started_at"],
        uptime_seconds=st["uptime_seconds"],
        log_path=st["log_path"],
        config=st["config"],
        last_exit=st["last_exit"],
        session_state=session_state,
    )


@app.get("/api/bot/log", dependencies=[Depends(verify_api_key)])
async def bot_log(lines: int = 100):
    if lines < 1 or lines > 1000:
        raise HTTPException(status_code=400, detail="lines must be 1..1000")
    mgr = get_bot_manager()
    return {"lines": mgr.log_tail(lines)}


# ======== Sessions listing ========


@app.get("/api/sessions", dependencies=[Depends(verify_api_key)])
async def list_sessions():
    with _sessions_lock:
        # Load any persisted sessions not yet in memory
        for f in STATE_DIR.glob("*.json"):
            uid = f.stem
            if uid not in _SESSIONS:
                loaded = LaplaceSession.load(uid)
                if loaded:
                    _SESSIONS[uid] = loaded
        return {
            "sessions": [
                {
                    "user_id": sid,
                    "cumulative_profit": s.tracker.cumulative_profit,
                    "cumulative_money": s.tracker.cumulative_profit * s.chip_base,
                    "sets": len(s.tracker.sets),
                    "current_turn": len(s.tracker.current_turns),
                    "updated_at": s.updated_at,
                }
                for sid, s in _SESSIONS.items()
            ]
        }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("LAPLACE_API_HOST", "0.0.0.0")
    port = int(os.getenv("LAPLACE_API_PORT", "8000"))
    logger.info(f"LAPLACE API starting on {host}:{port} (auth={'enabled' if API_KEY else 'DISABLED'})")
    uvicorn.run(app, host=host, port=port)
