"""Pragmatic Play ロビーデータブリッジ

bacopy マスター API の /api/snapshots からリアルタイムデータを取得する。
Evolution scraper_bridge.py の代替として使用。
"""
from __future__ import annotations
import os
import threading
import time
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Optional


MASTER_URL = os.getenv("BACOPY_MASTER_URL", "https://master.bafather.uk")
POLL_INTERVAL = int(os.getenv("PRAGMATIC_POLL_INTERVAL", "10"))  # 秒


def _load_api_key() -> str:
    key = os.getenv("BACOPY_API_KEY", "")
    if key:
        return key
    # .env ファイルから読み込み (Windows 環境対応)
    for candidate in [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]:
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("BACOPY_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return key


def _fetch_snapshots(api_key: str) -> Optional[dict]:
    """master /api/snapshots を叩いて pragmatic テーブルデータを返す"""
    url = f"{MASTER_URL}/api/snapshots"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None
    snaps = (data.get("snapshots") or {}).get("pragmatic") or {}
    return snaps


class PragmaticBridge:
    """master API をポーリングして Pragmatic Play ロビーデータを提供する"""

    def __init__(self):
        self._api_key = _load_api_key()
        self._data: dict = {}          # table_id → snapshot dict
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._status = "stopped"
        self._last_ok_at: float = 0.0
        self._last_error = ""
        self._n_tables = 0

    def start(self) -> dict:
        if self._running:
            return {"ok": False, "error": "既に起動中"}
        if not self._api_key:
            return {"ok": False, "error": "BACOPY_API_KEY が未設定 (.env を確認)"}
        self._running = True
        self._status = "starting"
        self._thread = threading.Thread(target=self._loop, daemon=True, name="PragmaticBridge")
        self._thread.start()
        return {"ok": True}

    def stop(self) -> dict:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._status = "stopped"
        return {"ok": True}

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "status": self._status,
            "ws_connected": self._last_ok_at > 0,
            "browser_alive": self._running,
            "last_heartbeat": self._last_ok_at,
            "seconds_since_heartbeat": (time.time() - self._last_ok_at) if self._last_ok_at else None,
            "last_error": self._last_error,
            "n_tables": self._n_tables,
        }

    def get_lobby(self) -> dict:
        """全 Pragmatic テーブルのロビーデータ (sequence 付き) を返す"""
        with self._lock:
            data = dict(self._data)
        if not data:
            return {"source": "pragmatic", "ok": False,
                    "status": self._status, "tables": []}
        tables = []
        for tid, snap in data.items():
            seq = snap.get("sequence") or ""
            tables.append({
                "table_id": tid,
                "table_name": snap.get("table_name", tid),
                "seq": seq,
                "n_raw": len([c for c in seq if c in "PBT"]),
                "players": 0,
                "captured_at": snap.get("captured_at", ""),
            })
        return {
            "source": "pragmatic",
            "ok": True,
            "status": self._status,
            "ws_connected": True,
            "tables": tables,
        }

    def get_table_bead_road(self, table_name: str) -> dict:
        with self._lock:
            data = dict(self._data)
        for tid, snap in data.items():
            if snap.get("table_name", "").strip() == table_name.strip():
                seq = snap.get("sequence") or ""
                return {"ok": True, "table_id": tid, "seq": seq, "n_raw": len(seq)}
        return {"ok": False, "error": f"'{table_name}' が見つかりません", "seq": ""}

    def _loop(self):
        while self._running:
            try:
                snaps = _fetch_snapshots(self._api_key)
                if snaps is not None:
                    with self._lock:
                        self._data = snaps
                    self._n_tables = len(snaps)
                    self._last_ok_at = time.time()
                    self._status = f"running ({self._n_tables} tables)"
                    self._last_error = ""
                else:
                    self._last_error = "API fetch failed"
                    self._status = f"error: {self._last_error}"
            except Exception as e:
                self._last_error = str(e)
                self._status = f"error: {e}"
            time.sleep(POLL_INTERVAL)
        self._running = False
        self._status = "stopped"


_BRIDGE = PragmaticBridge()


def get_pragmatic_bridge() -> PragmaticBridge:
    return _BRIDGE
