"""SQLiteデータベース管理"""
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger("baccarat.db")

JST = timezone(timedelta(hours=9))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """テーブル作成"""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            round_id TEXT,
            result TEXT NOT NULL,          -- 'player', 'banker', 'tie'
            player_pair INTEGER DEFAULT 0, -- 1=ペアあり
            banker_pair INTEGER DEFAULT 0, -- 1=ペアあり
            player_score INTEGER,
            banker_score INTEGER,
            shoe_number TEXT,
            created_at TEXT NOT NULL       -- ISO8601 JST
        );

        CREATE INDEX IF NOT EXISTS idx_rounds_table ON rounds(table_name);
        CREATE INDEX IF NOT EXISTS idx_rounds_created ON rounds(created_at);
        CREATE INDEX IF NOT EXISTS idx_rounds_result ON rounds(result);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_rounds_unique ON rounds(table_name, round_id);
    """)
    conn.commit()
    conn.close()
    logger.info(f"DB initialized: {DB_PATH}")


def insert_round(
    table_name: str,
    round_id: str,
    result: str,
    player_pair: bool = False,
    banker_pair: bool = False,
    player_score: int | None = None,
    banker_score: int | None = None,
    shoe_number: str = "",
) -> bool:
    """ラウンド結果を保存。重複はスキップ。挿入されたらTrue"""
    now = datetime.now(JST).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO rounds
               (table_name, round_id, result, player_pair, banker_pair,
                player_score, banker_score, shoe_number, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                table_name, round_id, result,
                int(player_pair), int(banker_pair),
                player_score, banker_score,
                shoe_number, now,
            ),
        )
        conn.commit()
        inserted = conn.total_changes > 0
        return inserted
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_stats(table_name: str = "", hours: int = 24) -> dict:
    """統計情報を取得"""
    conn = get_connection()
    cutoff = (datetime.now(JST) - timedelta(hours=hours)).isoformat()

    where = "WHERE created_at >= ?"
    params: list = [cutoff]
    if table_name:
        where += " AND table_name = ?"
        params.append(table_name)

    row = conn.execute(
        f"SELECT COUNT(*) as total FROM rounds {where}", params
    ).fetchone()
    total = row["total"]

    if total == 0:
        conn.close()
        return {"total": 0, "player": 0, "banker": 0, "tie": 0,
                "player_pct": 0, "banker_pct": 0, "tie_pct": 0,
                "player_pair": 0, "banker_pair": 0}

    results = {}
    for result_type in ("player", "banker", "tie"):
        r = conn.execute(
            f"SELECT COUNT(*) as cnt FROM rounds {where} AND result = ?",
            params + [result_type],
        ).fetchone()
        results[result_type] = r["cnt"]

    pp = conn.execute(
        f"SELECT SUM(player_pair) as cnt FROM rounds {where}", params
    ).fetchone()
    bp = conn.execute(
        f"SELECT SUM(banker_pair) as cnt FROM rounds {where}", params
    ).fetchone()

    conn.close()

    return {
        "total": total,
        "player": results["player"],
        "banker": results["banker"],
        "tie": results["tie"],
        "player_pct": round(results["player"] / total * 100, 1),
        "banker_pct": round(results["banker"] / total * 100, 1),
        "tie_pct": round(results["tie"] / total * 100, 1),
        "player_pair": pp["cnt"] or 0,
        "banker_pair": bp["cnt"] or 0,
    }


def get_recent_results(table_name: str = "", limit: int = 20) -> list[dict]:
    """直近の結果を取得"""
    conn = get_connection()
    where = ""
    params: list = []
    if table_name:
        where = "WHERE table_name = ?"
        params.append(table_name)

    rows = conn.execute(
        f"SELECT * FROM rounds {where} ORDER BY id DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_streak(table_name: str = "") -> dict:
    """現在の連勝・連続記録"""
    results = get_recent_results(table_name, limit=100)
    if not results:
        return {"current": "", "count": 0}

    current = results[0]["result"]
    count = 0
    for r in results:
        if r["result"] == current:
            count += 1
        else:
            break

    return {"current": current, "count": count}
