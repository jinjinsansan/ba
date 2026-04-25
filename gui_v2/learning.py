"""AI 学習システム (Phase 1: データ蓄積 + Bayesian prior)

仕組み:
  - BET が resolve されるたびに特徴量 + 結果を logs/training_data.jsonl に 1 行追加
  - (pattern, table) ごとに win rate + n を集計
  - forecast() の confidence をルールベース + 履歴加重平均で出す
  - 件数が増えるほど履歴の重みが上がる (n=10 未満はルール固定, n>=50 で履歴だけ)

将来拡張 (Phase 2):
  - sklearn で勾配ブースティング
  - 時間帯 / depth / streak 長などの特徴量で精密化
"""
from __future__ import annotations
import json
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / "logs" / "training_data.jsonl"
LOG_FILE.parent.mkdir(exist_ok=True)


_LOCK = threading.Lock()
_CACHE: dict = {"loaded": False, "stats": defaultdict(lambda: {"bets": 0, "wins": 0})}


def _key(pattern: str | None, table: str, side: str) -> str:
    """統計キー"""
    return f"{pattern or 'none'}|{table}|{side}"


def load_stats() -> None:
    """jsonl から統計を再計算 (起動時 or 定期)。undone=true の行は skip"""
    _CACHE["stats"].clear()
    if not LOG_FILE.exists():
        _CACHE["loaded"] = True
        return
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line.strip())
                except Exception:
                    continue
                if r.get("undone"):
                    continue
                k = _key(r.get("entry_pattern"), r.get("table", ""), r.get("bet_side", ""))
                _CACHE["stats"][k]["bets"] += 1
                if r.get("won"):
                    _CACHE["stats"][k]["wins"] += 1
    except Exception:
        pass
    _CACHE["loaded"] = True


def log_bet(record: dict) -> None:
    """BET 結果を 1 行追加 + cache 更新"""
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "undone": False,
        **record,
    }
    with _LOCK:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass
        if not _CACHE["loaded"]:
            load_stats()
        k = _key(row.get("entry_pattern"), row.get("table", ""), row.get("bet_side", ""))
        _CACHE["stats"][k]["bets"] += 1
        if row.get("won"):
            _CACHE["stats"][k]["wins"] += 1


def undo_last_bet() -> dict | None:
    """直前の log_bet() を統計から取り消す (undo hand と連動)

    jsonl は append-only のため、該当行に undone マーカーを追記し、
    cache の bets / wins を減算する。
    """
    with _LOCK:
        if not LOG_FILE.exists():
            return None
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        except Exception:
            return None
        # 末尾から undone=false の行を探す
        target_idx = -1
        target = None
        for i in range(len(lines) - 1, -1, -1):
            try:
                r = json.loads(lines[i])
            except Exception:
                continue
            if not r.get("undone"):
                target_idx = i
                target = r
                break
        if target is None:
            return None
        # undone=true に書き換え
        target["undone"] = True
        target["undone_ts"] = datetime.now().isoformat(timespec="seconds")
        lines[target_idx] = json.dumps(target, ensure_ascii=False)
        try:
            LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception:
            return None
        # cache 減算
        k = _key(target.get("entry_pattern"), target.get("table", ""), target.get("bet_side", ""))
        s = _CACHE["stats"].get(k)
        if s:
            s["bets"] = max(0, s["bets"] - 1)
            if target.get("won"):
                s["wins"] = max(0, s["wins"] - 1)
        return target


def pattern_win_rate(pattern: str, table: str | None = None, side: str = "P") -> tuple[float | None, int]:
    """(pattern, table) の履歴 win rate + n を返す。0件なら (None, 0)"""
    if not _CACHE["loaded"]:
        load_stats()
    if table:
        k = _key(pattern, table, side)
        s = _CACHE["stats"].get(k)
        if s and s["bets"] > 0:
            return s["wins"] / s["bets"], s["bets"]
    # table 無指定 → pattern 全体
    total = 0
    wins = 0
    for key, v in _CACHE["stats"].items():
        p, _t, sd = key.split("|", 2)
        if p == pattern and sd == side:
            total += v["bets"]
            wins += v["wins"]
    if total > 0:
        return wins / total, total
    return None, 0


def adjusted_confidence(rule_conf: int | None, pattern: str | None, table: str | None) -> tuple[int | None, dict]:
    """ルール確信度 + 履歴で重み付け調整

    n=0    → ルール確信度そのまま
    n=1-9  → 9:1 (ルール優位)
    n=10-49→ 逐次線形補間
    n>=50  → 履歴だけ
    """
    meta = {"rule_conf": rule_conf, "hist_rate": None, "hist_n": 0, "blended": rule_conf}
    if rule_conf is None or not pattern:
        return rule_conf, meta
    rate, n = pattern_win_rate(pattern, table, "P")
    meta["hist_rate"] = round(rate * 100, 1) if rate is not None else None
    meta["hist_n"] = n
    if n == 0 or rate is None:
        return rule_conf, meta
    hist_conf = round(rate * 100)
    if n >= 50:
        blended = hist_conf
    else:
        # n が増えるほど履歴比重 up
        w_hist = min(n / 50, 1.0)
        blended = round(rule_conf * (1 - w_hist) + hist_conf * w_hist)
    meta["blended"] = blended
    return blended, meta


def overall_stats() -> dict:
    """全体学習統計 (UI 表示用)"""
    if not _CACHE["loaded"]:
        load_stats()
    total_bets = 0
    total_wins = 0
    per_pattern: dict = defaultdict(lambda: {"bets": 0, "wins": 0})
    per_table: dict = defaultdict(lambda: {"bets": 0, "wins": 0})
    for key, v in _CACHE["stats"].items():
        p, t, _s = key.split("|", 2)
        total_bets += v["bets"]
        total_wins += v["wins"]
        per_pattern[p]["bets"] += v["bets"]
        per_pattern[p]["wins"] += v["wins"]
        per_table[t]["bets"] += v["bets"]
        per_table[t]["wins"] += v["wins"]

    def to_list(d):
        out = []
        for k, v in d.items():
            if v["bets"] == 0:
                continue
            out.append({
                "key": k, "bets": v["bets"], "wins": v["wins"],
                "win_rate": round(v["wins"] / v["bets"] * 100, 2),
            })
        out.sort(key=lambda x: -x["bets"])
        return out

    return {
        "total_bets": total_bets,
        "total_wins": total_wins,
        "overall_win_rate": round(total_wins / total_bets * 100, 2) if total_bets else 0,
        "per_pattern": to_list(per_pattern),
        "per_table": to_list(per_table)[:20],
    }


# 起動時にロード
load_stats()
