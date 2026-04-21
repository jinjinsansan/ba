"""B=52% 狙い打ちフィルタ探索 — 実データ 188万ハンドから「次=Banker が出やすい条件」を抽出

検証フィルタ:
  1. 直近 N ハンドパターン (N=2,3,4) — 無Tie の連続
  2. 連続ストリーク (B x N / P x N, N=2..6)
  3. 時間帯 (JST 0-23 時)
  4. テーブル別 (全 62 テーブル)
  5. シュー内位置 (hand_index を bucket 化)
  6. 曜日 (JST Mon-Sun)

スコア: edge (P(B) - baseline) × sqrt(count) で統計的有意性ランキング
フィルタ「使える」判定: P(B) > 0.52 AND count > 5,000
"""
from __future__ import annotations
import sqlite3
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime, timezone, timedelta
import math

DB_PATH = Path(__file__).parent / "analytics_vps_latest.sqlite3"
OUT_HTML = Path(__file__).parent / "report" / "banker52_filter_scan.html"
CUTOFF = "2026-04-06"
JST = timezone(timedelta(hours=9))


_RMAP = {"player": "P", "banker": "B", "tie": "T", "P": "P", "B": "B", "T": "T"}


def fetch_all(conn):
    """shoe 順 × hand_index 順で全ハンドを取得 (result を P/B/T に正規化)"""
    q = """
    SELECT s.id, s.table_name, s.started_at, h.hand_index, h.result
    FROM hands h
    JOIN shoes_analytics s ON h.shoe_id = s.id
    WHERE s.started_at >= ?
    ORDER BY s.started_at ASC, s.id ASC, h.hand_index ASC
    """
    rows = []
    for sid, tn, sa, hi, res in conn.execute(q, (CUTOFF,)):
        r = _RMAP.get((res or "").strip().lower()) or _RMAP.get((res or "").strip())
        if r:
            rows.append((sid, tn, sa, hi, r))
    return rows


def analyze():
    print(f"[LOAD] DB: {DB_PATH.name}", flush=True)
    conn = sqlite3.connect(str(DB_PATH))
    rows = fetch_all(conn)
    total_hands = len(rows)
    print(f"[LOAD] 全ハンド数: {total_hands:,}", flush=True)

    # 全体ベースライン
    total_counter = Counter(r[4] for r in rows)
    total_non_tie = total_counter.get("P", 0) + total_counter.get("B", 0)
    baseline_b = total_counter.get("B", 0) / total_non_tie if total_non_tie else 0
    print(f"[BASE] 全体 B 率 (非Tie): {baseline_b*100:.3f}% / P={total_counter['P']:,} B={total_counter['B']:,} T={total_counter.get('T',0):,}", flush=True)

    # フィルタごとに bucket[filter_key] -> Counter("P"/"B"/"T")
    results = {}

    # 1. 直近 N ハンドパターン (non-Tie のみを buffer に)
    for N in (2, 3, 4):
        buckets = defaultdict(Counter)
        prev_shoe = None
        buffer = []
        for shoe_id, table_name, _started, hand_idx, res in rows:
            if shoe_id != prev_shoe:
                buffer = []
                prev_shoe = shoe_id
            if len(buffer) >= N:
                key = "".join(buffer[-N:])
                buckets[key][res] += 1
            if res in ("P", "B"):
                buffer.append(res)
        results[f"直近{N}ハンド"] = buckets

    # 2. ストリーク (現在の non-Tie 連勝)
    #   直前 k 連続 B → 次は?
    for side in ("B", "P"):
        for streak_len in (2, 3, 4, 5, 6):
            key = f"{side}×{streak_len}連続後"
            bucket = Counter()
            prev_shoe = None
            run_side = None
            run_len = 0
            for shoe_id, _tn, _st, _hi, res in rows:
                if shoe_id != prev_shoe:
                    run_side = None
                    run_len = 0
                    prev_shoe = shoe_id
                if run_side == side and run_len >= streak_len:
                    bucket[res] += 1
                if res == side:
                    if run_side == side:
                        run_len += 1
                    else:
                        run_side = side
                        run_len = 1
                elif res in ("P", "B"):
                    run_side = res
                    run_len = 1
                # Tie はストリーク維持
            results.setdefault("ストリーク後", {})[key] = bucket

    # 3. 時間帯 (JST 0-23)
    hour_buckets = defaultdict(Counter)
    for _sid, _tn, started, _hi, res in rows:
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00")) if "T" in started else datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            jst_h = dt.astimezone(JST).hour
            hour_buckets[jst_h][res] += 1
        except Exception:
            continue
    results["時間帯JST"] = hour_buckets

    # 4. テーブル別
    table_buckets = defaultdict(Counter)
    for _sid, tn, _st, _hi, res in rows:
        table_buckets[tn][res] += 1
    results["テーブル別"] = table_buckets

    # 5. シュー内位置 (hand_index bucket)
    pos_buckets = defaultdict(Counter)
    for _sid, _tn, _st, hi, res in rows:
        if hi <= 20:
            bk = "1-20"
        elif hi <= 40:
            bk = "21-40"
        elif hi <= 60:
            bk = "41-60"
        else:
            bk = "61+"
        pos_buckets[bk][res] += 1
    results["シュー位置"] = pos_buckets

    # 6. 曜日
    dow_buckets = defaultdict(Counter)
    for _sid, _tn, started, _hi, res in rows:
        try:
            dt = datetime.fromisoformat(started.replace("Z", "+00:00")) if "T" in started else datetime.strptime(started, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dow = dt.astimezone(JST).strftime("%a")
            dow_buckets[dow][res] += 1
        except Exception:
            continue
    results["曜日JST"] = dow_buckets

    conn.close()
    return baseline_b, results, total_hands


def compute_rates(buckets):
    """bucket 辞書 -> list of {key, count, p, b, t, pb_rate, bb_rate, edge, score}"""
    out = []
    for key, cnt in buckets.items():
        p = cnt.get("P", 0)
        b = cnt.get("B", 0)
        t = cnt.get("T", 0)
        total = p + b + t
        non_tie = p + b
        b_rate = b / non_tie if non_tie else 0.0
        p_rate = p / non_tie if non_tie else 0.0
        out.append({
            "key": str(key),
            "count": total,
            "non_tie": non_tie,
            "p": p, "b": b, "t": t,
            "b_rate": b_rate,
            "p_rate": p_rate,
        })
    return out


def rank(items, baseline):
    for it in items:
        it["edge"] = it["b_rate"] - baseline
        it["score"] = it["edge"] * math.sqrt(it["non_tie"]) if it["non_tie"] > 0 else 0
    items.sort(key=lambda x: x["score"], reverse=True)
    return items


def render_html(baseline, all_results, total_hands):
    def pct(x): return f"{x*100:.3f}%"
    def color_b(br, bl):
        if br > 0.52: return "#4ade80"
        if br > bl + 0.005: return "#fbbf24"
        if br < bl - 0.005: return "#f87171"
        return "#cbd5e1"

    sections = ""
    for cat_name, buckets in all_results.items():
        items = compute_rates(buckets)
        items = rank(items, baseline)
        # 使える候補 (P(B) > 0.52 AND non_tie > 5000)
        viable = [it for it in items if it["b_rate"] > 0.52 and it["non_tie"] > 5000]

        rows = ""
        for it in items[:30]:  # Top 30 by score
            star = "⭐" if (it["b_rate"] > 0.52 and it["non_tie"] > 5000) else ""
            color = color_b(it["b_rate"], baseline)
            rows += f"""
<tr>
<td>{it['key']}</td>
<td>{it['count']:,}</td>
<td>{it['non_tie']:,}</td>
<td style="color:{color};font-weight:700">{pct(it['b_rate'])} {star}</td>
<td>{pct(it['p_rate'])}</td>
<td style="color:{'#4ade80' if it['edge']>0 else '#f87171'}">{it['edge']*100:+.3f}%</td>
<td>{it['score']:+.1f}</td>
</tr>
"""
        viable_str = f"<b style='color:#4ade80'>使える候補: {len(viable)} 個</b>" if viable else "<b style='color:#f87171'>使える候補なし</b>"
        sections += f"""
<h2>{cat_name}</h2>
<div style="margin-bottom:10px">{viable_str} (条件: P(B) &gt; 52.00% AND 非Tie &gt; 5,000)</div>
<table>
<tr><th>条件</th><th>件数</th><th>非Tie</th><th>P(次=B)</th><th>P(次=P)</th><th>edge vs baseline</th><th>score (edge×√N)</th></tr>
{rows}
</table>
"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>B=52% 狙い打ちフィルタ探索 — 実データ分析</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:'Noto Sans JP',sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:white;min-height:100vh;padding:40px 20px }}
.container {{ max-width:1300px;margin:0 auto }}
h1 {{ font-size:32px;font-weight:900;background:linear-gradient(135deg,#00c8ff 0%,#6bcf8f 100%);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:8px }}
.sub {{ color:#a0a0c0;margin-bottom:30px }}
h2 {{ color:#00c8ff;font-size:22px;margin:25px 0 10px;border-left:4px solid #00c8ff;padding-left:12px }}
table {{ width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:8px;overflow:hidden;font-size:13px;margin-top:8px }}
th,td {{ padding:8px 10px;text-align:right;border-bottom:1px solid rgba(255,255,255,0.08) }}
th {{ background:rgba(0,200,255,0.1);color:#00c8ff;font-weight:700 }}
td:first-child,th:first-child {{ text-align:left;font-family:monospace }}
.params {{ background:rgba(0,200,255,0.06);padding:15px;border-radius:8px;margin:15px 0;font-size:14px;line-height:1.7 }}
.back {{ display:inline-block;margin-bottom:20px;color:#00c8ff;text-decoration:none }}
.back:hover {{ text-decoration:underline }}
</style></head><body>
<div class="container">
<a href="index.html" class="back">← index に戻る</a>
<h1>B=52% 狙い打ちフィルタ探索</h1>
<div class="sub">実データ {total_hands:,} ハンドから「次=Banker が出やすい条件」を多角的に抽出</div>

<div class="params">
<b>ベースライン</b>: 全体 B 率 (非Tie) = <b style="color:#fbbf24">{baseline*100:.3f}%</b><br>
<b>使える候補</b>: P(B) &gt; 52.00% <b>AND</b> 非Tie 件数 &gt; 5,000 (統計的ノイズ排除)<br>
<b>score</b> = (P(B) - baseline) × √非Tie件数 — edge の大きさ × サンプルサイズで統計的有意性を反映<br>
<b>使い方</b>: ⭐付き条件が見つかれば、それを入場トリガーとして実運用で B=52%+ を狙える候補
</div>

{sections}

<div style="margin-top:30px;padding:20px;background:rgba(0,200,255,0.06);border-radius:8px;font-size:14px;line-height:1.7">
<b style="color:#00c8ff">解釈</b>:<br>
・<b>edge &gt; +1%</b>: バカラの理論 edge (~0.5%) を超える異常値。モデル化 or データ取り違え疑うレベル<br>
・<b>edge &lt; baseline ± 0.5%</b>: 統計ノイズ、エッジなし<br>
・<b>⭐条件が 0 個</b>: この軸では Banker 52% を狙えない (自動化 edge 無しの裏付け)<br>
・<b>⭐条件が複数</b>: 組み合わせフィルタの基礎材料、次は AND/OR 合成で検証
</div>
</div></body></html>"""


def main():
    baseline, results, total = analyze()

    # コンソール出力: 各カテゴリの Top 5
    for cat_name, buckets in results.items():
        items = rank(compute_rates(buckets), baseline)
        print(f"\n=== {cat_name} Top 5 ===", flush=True)
        for it in items[:5]:
            mark = "⭐" if (it["b_rate"] > 0.52 and it["non_tie"] > 5000) else "  "
            print(f"  {mark} {it['key']:40s} n={it['non_tie']:7,} P(B)={it['b_rate']*100:6.3f}% edge={it['edge']*100:+.3f}% score={it['score']:+.1f}", flush=True)

    html = render_html(baseline, results, total)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}", flush=True)


if __name__ == "__main__":
    main()
