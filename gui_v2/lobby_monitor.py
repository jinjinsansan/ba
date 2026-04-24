"""ロビー監視モジュール

2 つのソースから「今どのテーブルが打てそうか」を判定:
  A) VPS DB (analytics_vps_latest.sqlite3) から直近のシューを読む
  B) Playwright スクレイパが書き出す lobby_state.json (任意、別プロセス)

どちらも存在しない/古い場合は empty を返す。
"""
from __future__ import annotations
import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategy_engine import classify_strict, check_entry

EVO_DB = Path(__file__).resolve().parent.parent / "analytics_vps_latest.sqlite3"
LOBBY_JSON = Path(__file__).parent / "lobby_state.json"

EXCLUDE_KEYWORDS = ["Always 9", "Lightning"]
BLACKLIST = {
    "Speed Baccarat B", "Thai Speed Baccarat B", "Emperor Speed Baccarat C",
    "Korean Speed Baccarat A", "Baccarat A", "Dynasty Speed Baccarat 2",
    "Dynasty Speed Baccarat 3", "Dynasty Speed Baccarat 10",
    "Super Speed Baccarat",
}
WHITELIST = {
    "Japanese Speed Baccarat E", "Korean Speaking Speed Baccarat 2",
    "Baccarat Squeeze", "Japanese Speed Baccarat A", "Korean Speed Baccarat H",
    "Speed Baccarat D", "Speed Baccarat T", "Lotus Speed Baccarat A",
}


def _is_excluded(tn: str) -> bool:
    return any(kw.lower() in tn.lower() for kw in EXCLUDE_KEYWORDS)


def _current_shoe_seq(conn, table_name: str, lookback_hours: int = 4) -> tuple[str, str] | None:
    """テーブルの最新シューの bead road を取得。lookback_hours 内になければ None."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    row = conn.execute(
        """SELECT id, started_at FROM shoes_analytics
           WHERE table_name = ? AND started_at >= ?
           ORDER BY started_at DESC LIMIT 1""",
        (table_name, cutoff),
    ).fetchone()
    if not row:
        return None
    shoe_id, started_at = row
    hands = conn.execute(
        "SELECT result FROM hands WHERE shoe_id = ? ORDER BY hand_index ASC",
        (shoe_id,),
    ).fetchall()
    seq = []
    for (r,) in hands:
        r = (r or "").strip().upper()
        if r in ("P", "PLAYER"): seq.append("P")
        elif r in ("B", "BANKER"): seq.append("B")
        elif r in ("T", "TIE"): seq.append("T")
    return "".join(seq), started_at


def lobby_from_db(lookback_hours: int = 4, max_entries: int = 40) -> dict:
    """VPS DB から現在進行中のシュー一覧を取得して分類"""
    if not EVO_DB.exists():
        return {"source": "db", "error": "DB not found", "tables": [], "db_latest": None}

    conn = sqlite3.connect(str(EVO_DB))
    # 最新 shoe の started_at (DB 全体の鮮度指標)
    latest = conn.execute("SELECT MAX(started_at) FROM shoes_analytics").fetchone()[0]

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    tables_recent = conn.execute(
        """SELECT DISTINCT table_name FROM shoes_analytics
           WHERE started_at >= ?""",
        (cutoff,),
    ).fetchall()

    entries = []
    for (tname,) in tables_recent:
        if _is_excluded(tname):
            continue
        res = _current_shoe_seq(conn, tname, lookback_hours)
        if not res:
            continue
        seq, started_at = res
        info = classify_strict(seq)
        enter_flag, enter_reason = check_entry(seq, info)

        in_whitelist = tname in WHITELIST
        in_blacklist = tname in BLACKLIST

        score = 0
        if in_whitelist: score += 100
        if in_blacklist: score -= 100
        if info["pattern"] in ("縦面5+密集", "縦面4以下密集"): score += 50
        if info["pattern"] == "ニコニコ・ニコイチ": score += 40
        if info["pattern"] in ("ブリッジ", "不規則"): score -= 20
        if info["pattern"] == "偏り": score -= 40
        if enter_flag: score += 30
        score += min(info["n_cols"], 20)

        entries.append({
            "table": tname,
            "in_whitelist": in_whitelist,
            "in_blacklist": in_blacklist,
            "pattern": info["pattern"],
            "pattern_reason": info["reason"],
            "n_cols": info["n_cols"],
            "n_hands": info["n_hands_nont"],
            "p_cnt": info["p_cnt"],
            "b_cnt": info["b_cnt"],
            "t_cnt": info["t_cnt"],
            "b_lead": info["b_lead"],
            "entry_ok": enter_flag,
            "entry_reason": enter_reason,
            "features": info["features"],
            "started_at": started_at,
            "seq_tail": seq[-40:],
            "score": score,
        })
    conn.close()

    entries.sort(key=lambda x: -x["score"])
    return {
        "source": "db",
        "db_latest": latest,
        "db_path": str(EVO_DB),
        "lookback_hours": lookback_hours,
        "tables": entries[:max_entries],
    }


def lobby_from_scraper() -> dict | None:
    """Playwright スクレイパ が書き出す lobby_state.json を読む (任意)"""
    if not LOBBY_JSON.exists():
        return None
    try:
        data = json.loads(LOBBY_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
    # Expected format: {"updated_at": "...", "tables": [{"table": "...", "seq": "...", ...}]}
    if not isinstance(data, dict) or "tables" not in data:
        return None
    entries = []
    for t in data.get("tables", []):
        tname = t.get("table", "")
        seq = t.get("seq", "")
        if _is_excluded(tname): continue
        info = classify_strict(seq)
        enter_flag, enter_reason = check_entry(seq, info)
        entries.append({
            "table": tname,
            "in_whitelist": tname in WHITELIST,
            "in_blacklist": tname in BLACKLIST,
            "pattern": info["pattern"],
            "pattern_reason": info["reason"],
            "n_cols": info["n_cols"],
            "n_hands": info["n_hands_nont"],
            "p_cnt": info["p_cnt"], "b_cnt": info["b_cnt"], "t_cnt": info["t_cnt"],
            "b_lead": info["b_lead"],
            "entry_ok": enter_flag,
            "entry_reason": enter_reason,
            "features": info["features"],
            "seq_tail": seq[-40:],
            "score": 0,
        })
    entries.sort(key=lambda x: 0 if x["in_whitelist"] else 1)
    return {
        "source": "scraper",
        "updated_at": data.get("updated_at"),
        "tables": entries,
    }


def get_lobby(prefer_scraper: bool = True) -> dict:
    """scraper を優先、なければ DB"""
    if prefer_scraper:
        sc = lobby_from_scraper()
        if sc:
            return sc
    return lobby_from_db()
