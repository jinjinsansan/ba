"""B=52% 組み合わせフィルタ全探索 — 14 個別フィルタから 2-way/3-way AND 合成を全列挙"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from itertools import combinations
import math

import numpy as np

DB_PATH = Path(__file__).parent / "analytics_vps_latest.sqlite3"
OUT_HTML = Path(__file__).parent / "report" / "banker52_combo_scan.html"
CUTOFF = "2026-04-06"
JST = timezone(timedelta(hours=9))
MIN_SAMPLE = 3000  # 組み合わせ後の最低サンプル数 (統計ノイズ除外)

_RMAP = {"player": "P", "banker": "B", "tie": "T"}


def load_hands():
    print(f"[LOAD] {DB_PATH.name}", flush=True)
    conn = sqlite3.connect(str(DB_PATH))
    rows = []
    q = """
    SELECT s.id, s.table_name, s.started_at, h.hand_index, h.result
    FROM hands h
    JOIN shoes_analytics s ON h.shoe_id = s.id
    WHERE s.started_at >= ?
    ORDER BY s.started_at ASC, s.id ASC, h.hand_index ASC
    """
    for sid, tn, sa, hi, res in conn.execute(q, (CUTOFF,)):
        r = _RMAP.get((res or "").strip().lower())
        if r:
            rows.append((sid, tn, sa, hi, r))
    conn.close()
    print(f"[LOAD] {len(rows):,} hands", flush=True)
    return rows


def build_feature_matrix(rows):
    """各ハンドに対して、その位置が各フィルタにマッチするかを boolean matrix で返す。
    特徴量は『このハンドを BET する時』の直前状態で評価 (look-ahead 禁止)。
    N = ハンド数 / 出力: (outcomes: 'P'/'B'/'T', features: (N, n_filters) bool)
    """
    n = len(rows)
    outcomes = np.array([r[4] for r in rows])

    # 状態変数: shoe境界でreset
    filter_names = []
    # (1) 直近 N パターン (N=2,3,4) × 上位 pattern
    filter_names += ["last2=BB", "last3=BBB", "last4=BBBB", "last4=BBBP", "last4=PBBB"]
    # (2) B 連続 (2..6)
    filter_names += [f"Bstreak>={k}" for k in (2, 3, 4, 5, 6)]
    # (3) hour 22, 14, 0, 16
    filter_names += ["hour=22", "hour=14", "hour=0", "hour=16"]
    # (4) shoe position 61+
    filter_names += ["shoe>=61"]
    # (5) 高B率テーブル (Always 9 除く上位)
    filter_names += ["table=SpeedBaccaratC", "table=SpeedBaccaratT"]

    n_f = len(filter_names)
    mat = np.zeros((n, n_f), dtype=bool)

    prev_shoe = None
    buffer = []      # 非-tie のみ
    run_side = None
    run_len = 0
    for i, (sid, tn, sa, hi, res) in enumerate(rows):
        if sid != prev_shoe:
            buffer = []
            run_side = None
            run_len = 0
            prev_shoe = sid

        # 直近 N パターン (buffer の末尾)
        if len(buffer) >= 2:
            last2 = "".join(buffer[-2:])
            mat[i, 0] = last2 == "BB"
        if len(buffer) >= 3:
            last3 = "".join(buffer[-3:])
            mat[i, 1] = last3 == "BBB"
        if len(buffer) >= 4:
            last4 = "".join(buffer[-4:])
            mat[i, 2] = last4 == "BBBB"
            mat[i, 3] = last4 == "BBBP"
            mat[i, 4] = last4 == "PBBB"

        # B ストリーク
        for k_idx, k in enumerate((2, 3, 4, 5, 6)):
            mat[i, 5 + k_idx] = (run_side == "B" and run_len >= k)

        # hour
        try:
            dt = datetime.fromisoformat(sa.replace("Z", "+00:00")) if "T" in sa else datetime.strptime(sa, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            h = dt.astimezone(JST).hour
        except Exception:
            h = -1
        mat[i, 10] = (h == 22)
        mat[i, 11] = (h == 14)
        mat[i, 12] = (h == 0)
        mat[i, 13] = (h == 16)

        # shoe position
        mat[i, 14] = (hi >= 61)

        # table
        mat[i, 15] = (tn == "Speed Baccarat C")
        mat[i, 16] = (tn == "Speed Baccarat T")

        # --- update state (this hand を buffer/run に反映) ---
        if res == "B":
            if run_side == "B":
                run_len += 1
            else:
                run_side = "B"
                run_len = 1
            buffer.append("B")
        elif res == "P":
            run_side = "P"
            run_len = 1
            buffer.append("P")
        # Tie は buffer / run に影響しない

    return outcomes, mat, filter_names


def evaluate_combo(outcomes, mat, combo, baseline):
    """フィルタ combo (tuple of indices) の AND マッチを評価"""
    mask = np.ones(mat.shape[0], dtype=bool)
    for fi in combo:
        mask &= mat[:, fi]
    if mask.sum() == 0:
        return None
    sub = outcomes[mask]
    b = int(np.sum(sub == "B"))
    p = int(np.sum(sub == "P"))
    t = int(np.sum(sub == "T"))
    non_tie = b + p
    if non_tie < MIN_SAMPLE:
        return None
    b_rate = b / non_tie
    edge = b_rate - baseline
    score = edge * math.sqrt(non_tie)
    return {
        "count": b + p + t,
        "non_tie": non_tie,
        "p": p, "b": b, "t": t,
        "b_rate": b_rate,
        "edge": edge,
        "score": score,
    }


def main():
    rows = load_hands()
    outcomes, mat, filter_names = build_feature_matrix(rows)
    print(f"[FEAT] {len(filter_names)} filters, matrix shape={mat.shape}", flush=True)

    # baseline 全体 B 率 (非 Tie)
    total_b = int(np.sum(outcomes == "B"))
    total_p = int(np.sum(outcomes == "P"))
    baseline = total_b / (total_b + total_p)
    print(f"[BASE] 全体 B 率: {baseline*100:.3f}% (P={total_p:,} B={total_b:,})", flush=True)

    # 1-way (sanity check)
    print(f"\n=== 1-way フィルタ (単体) ===", flush=True)
    single = []
    for fi, fn in enumerate(filter_names):
        r = evaluate_combo(outcomes, mat, (fi,), baseline)
        if r:
            r["filters"] = [fn]
            single.append(r)
            mark = "⭐" if r["b_rate"] > 0.52 else "  "
            print(f"  {mark} {fn:25s} n={r['non_tie']:7,} P(B)={r['b_rate']*100:6.3f}% edge={r['edge']*100:+.3f}% score={r['score']:+.1f}", flush=True)

    # 2-way combinations
    print(f"\n=== 2-way 組み合わせ全探索 ({math.comb(len(filter_names), 2)} 通り) ===", flush=True)
    pairs = []
    for combo in combinations(range(len(filter_names)), 2):
        r = evaluate_combo(outcomes, mat, combo, baseline)
        if r:
            r["filters"] = [filter_names[i] for i in combo]
            pairs.append(r)
    pairs.sort(key=lambda x: x["score"], reverse=True)
    for r in pairs[:15]:
        mark = "⭐" if r["b_rate"] > 0.52 else "  "
        print(f"  {mark} [{' ∧ '.join(r['filters']):50s}] n={r['non_tie']:7,} P(B)={r['b_rate']*100:6.3f}% edge={r['edge']*100:+.3f}% score={r['score']:+.1f}", flush=True)

    # 3-way combinations
    print(f"\n=== 3-way 組み合わせ全探索 ({math.comb(len(filter_names), 3)} 通り) ===", flush=True)
    triples = []
    for combo in combinations(range(len(filter_names)), 3):
        r = evaluate_combo(outcomes, mat, combo, baseline)
        if r:
            r["filters"] = [filter_names[i] for i in combo]
            triples.append(r)
    triples.sort(key=lambda x: x["score"], reverse=True)
    for r in triples[:15]:
        mark = "⭐" if r["b_rate"] > 0.52 else "  "
        print(f"  {mark} [{' ∧ '.join(r['filters']):60s}] n={r['non_tie']:6,} P(B)={r['b_rate']*100:6.3f}% edge={r['edge']*100:+.3f}% score={r['score']:+.1f}", flush=True)

    # 集計
    viable_1 = [r for r in single if r["b_rate"] > 0.52]
    viable_2 = [r for r in pairs if r["b_rate"] > 0.52]
    viable_3 = [r for r in triples if r["b_rate"] > 0.52]
    print(f"\n=== 使える候補 (P(B)>52% AND 非Tie>{MIN_SAMPLE:,}) ===", flush=True)
    print(f"  1-way: {len(viable_1)} / {len(single)}", flush=True)
    print(f"  2-way: {len(viable_2)} / {len(pairs)}", flush=True)
    print(f"  3-way: {len(viable_3)} / {len(triples)}", flush=True)

    # render HTML
    def mkrow(r, baseline):
        color = "#4ade80" if r["b_rate"] > 0.52 else "#fbbf24" if r["b_rate"] > baseline + 0.003 else "#cbd5e1"
        star = "⭐" if r["b_rate"] > 0.52 else ""
        return f"<tr><td>{' ∧ '.join(r['filters'])}</td><td>{r['non_tie']:,}</td><td style='color:{color};font-weight:700'>{r['b_rate']*100:.3f}% {star}</td><td>{r['edge']*100:+.3f}%</td><td>{r['score']:+.2f}</td></tr>"

    rows_single = "\n".join(mkrow(r, baseline) for r in sorted(single, key=lambda x: x["score"], reverse=True))
    rows_pair = "\n".join(mkrow(r, baseline) for r in pairs[:30])
    rows_triple = "\n".join(mkrow(r, baseline) for r in triples[:30])

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>B=52% 組み合わせフィルタ全探索</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:'Noto Sans JP',sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:white;min-height:100vh;padding:40px 20px }}
.container {{ max-width:1400px;margin:0 auto }}
h1 {{ font-size:32px;font-weight:900;background:linear-gradient(135deg,#00c8ff 0%,#6bcf8f 100%);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:8px }}
.sub {{ color:#a0a0c0;margin-bottom:30px }}
h2 {{ color:#00c8ff;font-size:22px;margin:25px 0 10px;border-left:4px solid #00c8ff;padding-left:12px }}
table {{ width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:8px;overflow:hidden;font-size:13px;margin:10px 0 }}
th,td {{ padding:8px 12px;text-align:right;border-bottom:1px solid rgba(255,255,255,0.08) }}
th {{ background:rgba(0,200,255,0.1);color:#00c8ff;font-weight:700 }}
td:first-child,th:first-child {{ text-align:left;font-family:monospace;font-size:12px }}
.params {{ background:rgba(0,200,255,0.06);padding:15px;border-radius:8px;margin:15px 0;font-size:14px;line-height:1.7 }}
.back {{ display:inline-block;margin-bottom:20px;color:#00c8ff;text-decoration:none }}
.verdict {{ margin-top:30px;padding:25px;border-radius:8px;font-size:16px;line-height:1.8 }}
.verdict.fail {{ background:rgba(248,113,113,0.12);border:2px solid #f87171 }}
.verdict.pass {{ background:rgba(74,222,128,0.12);border:2px solid #4ade80 }}
</style></head><body>
<div class="container">
<a href="index.html" class="back">← index に戻る</a>
<h1>B=52% 組み合わせフィルタ全探索</h1>
<div class="sub">14 個別フィルタ × 1/2/3-way AND 合成 = 計 {len(single)+len(pairs)+len(triples):,} 通り</div>

<div class="params">
<b>ベースライン</b>: 全体 B 率 (非Tie) = {baseline*100:.3f}%<br>
<b>最低サンプル数</b>: 非Tie &gt; {MIN_SAMPLE:,} (統計ノイズ除外)<br>
<b>使える候補</b>: P(B) &gt; 52.00% ⭐
</div>

<h2>🎯 使える候補サマリ</h2>
<table>
<tr><th>次数</th><th>評価数</th><th>⭐候補 (P(B)&gt;52%)</th></tr>
<tr><td>1-way (単体)</td><td>{len(single)}</td><td style="color:{'#4ade80' if viable_1 else '#f87171'}">{len(viable_1)}</td></tr>
<tr><td>2-way (AND)</td><td>{len(pairs)}</td><td style="color:{'#4ade80' if viable_2 else '#f87171'}">{len(viable_2)}</td></tr>
<tr><td>3-way (AND)</td><td>{len(triples)}</td><td style="color:{'#4ade80' if viable_3 else '#f87171'}">{len(viable_3)}</td></tr>
</table>

<h2>1-way 単体フィルタ</h2>
<table>
<tr><th>フィルタ</th><th>非Tie</th><th>P(B)</th><th>edge</th><th>score</th></tr>
{rows_single}
</table>

<h2>2-way AND 組み合わせ (Top 30 by score)</h2>
<table>
<tr><th>フィルタ</th><th>非Tie</th><th>P(B)</th><th>edge</th><th>score</th></tr>
{rows_pair}
</table>

<h2>3-way AND 組み合わせ (Top 30 by score)</h2>
<table>
<tr><th>フィルタ</th><th>非Tie</th><th>P(B)</th><th>edge</th><th>score</th></tr>
{rows_triple}
</table>

<div class="verdict {'pass' if (viable_1 or viable_2 or viable_3) else 'fail'}">
<b style="color:{'#4ade80' if (viable_1 or viable_2 or viable_3) else '#f87171'};font-size:20px">
{'✅ 使える組み合わせが見つかりました' if (viable_1 or viable_2 or viable_3) else '❌ 使える組み合わせはありませんでした'}
</b><br><br>
{'候補の out-of-sample 検証、及び過剰適合チェックが次の課題。' if (viable_1 or viable_2 or viable_3) else '14 フィルタの AND 合成 ' + f'{len(single)+len(pairs)+len(triples):,}通り' + ' を全探索したが、いずれも P(B)&gt;52% を満たさない。Evolution の統計設計が堅牢で、単純フィルタでは edge が抽出できないことが数値で確定。<br>→ <b>bacopy (友人判断学習) が唯一の勝ち筋</b>'}
</div>
</div></body></html>"""

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}", flush=True)


if __name__ == "__main__":
    main()
