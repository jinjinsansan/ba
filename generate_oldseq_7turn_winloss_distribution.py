"""旧SEQ × 7ターン制 / 常時 Player BET の N勝N負 分布 + 資金推移

対象: analytics_vps_latest.sqlite3 (VPS由来)
期間: 2026-04-06 以降、Evolution Gaming 全テーブル
前提:
  - タイはスキップ (BETせず、ターン数に数えない)
  - 全ハンドに通しで Player BET (テーブル切替なし、連続したセット管理)
  - 1セット = 7ターン。セット確定時に結果 O(=P勝) / X(=B勝) を集計
  - 旧SEQ = [1,2,3,5,7,9,11,13,16,...,250] を MaruBatsuTracker に渡す
出力:
  - stdout サマリ
  - report/oldseq_7turn_winloss_distribution.html
"""
from __future__ import annotations
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from marubatsu_strategy import MaruBatsuTracker, SEQ, SET_SIZE_DEFAULT

DB_PATH = Path(__file__).parent / "analytics_vps_latest.sqlite3"
OUT_HTML = Path(__file__).parent / "report" / "oldseq_7turn_winloss_distribution.html"
CUTOFF = "2026-04-06"
SET_SIZE = 7
CHIP_BASE = 1.0  # $1 unit — 結果はチップ単位そのままドル


def fetch_hands(conn: sqlite3.Connection):
    """started_at昇順・hand_index昇順で全ハンド (Evolution のみ)"""
    q = """
    SELECT h.result
    FROM hands h
    JOIN shoes_analytics s ON h.shoe_id = s.id
    WHERE s.started_at >= ?
    ORDER BY s.started_at ASC, s.id ASC, h.hand_index ASC
    """
    return conn.execute(q, (CUTOFF,))


def run_backtest():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))

    meta = conn.execute(
        "SELECT MIN(started_at), MAX(started_at), COUNT(*), COUNT(DISTINCT table_name) "
        "FROM shoes_analytics WHERE started_at >= ?", (CUTOFF,)
    ).fetchone()
    hand_total = conn.execute(
        "SELECT COUNT(*) FROM hands h JOIN shoes_analytics s ON h.shoe_id=s.id "
        "WHERE s.started_at >= ?", (CUTOFF,)
    ).fetchone()[0]

    tracker = MaruBatsuTracker(chip_base=CHIP_BASE, seq=SEQ, set_size=SET_SIZE)

    dist = Counter()          # wins_count -> set count
    ties = 0
    bets = 0
    p_wins = 0
    b_wins = 0
    equity_points = []        # 10,000 set ごとのスナップショット

    for (res,) in fetch_hands(conn):
        r = (res or "").strip().upper()
        if r in ("T", "TIE"):
            ties += 1
            continue
        if r in ("P", "PLAYER"):
            outcome = "player"
            p_wins += 1
        elif r in ("B", "BANKER"):
            outcome = "banker"
            b_wins += 1
        else:
            continue
        bets += 1
        new_set = tracker.add_result(outcome)
        if new_set is not None:
            dist[new_set.wins] += 1
            sc = len(tracker.sets)
            if sc % 10000 == 0:
                equity_points.append((sc, tracker.cumulative_profit))

    # 末尾ポイントも
    sc = len(tracker.sets)
    equity_points.append((sc, tracker.cumulative_profit))

    conn.close()

    # 理論値 (二項分布, p = Player勝率を実測値から)
    p_rate = p_wins / bets if bets else 0
    from math import comb
    theo = {}
    for w in range(SET_SIZE + 1):
        theo[w] = comb(SET_SIZE, w) * (p_rate ** w) * ((1 - p_rate) ** (SET_SIZE - w))

    summary = {
        "db": str(DB_PATH.name),
        "cutoff": CUTOFF,
        "shoe_min": meta[0],
        "shoe_max": meta[1],
        "shoe_count": meta[2],
        "table_count": meta[3],
        "hand_total": hand_total,
        "ties": ties,
        "bets": bets,
        "p_wins": p_wins,
        "b_wins": b_wins,
        "p_rate": p_rate,
        "sets": len(tracker.sets),
        "cumulative_profit": tracker.cumulative_profit,
        "cumulative_money": tracker.cumulative_profit * CHIP_BASE,
        "dist": dict(dist),
        "theo": theo,
        "final_unit_idx": tracker.current_unit_idx,
        "final_unit": SEQ[min(tracker.current_unit_idx, len(SEQ)-1)],
        "current_turn_leftover": len(tracker.current_turns),
        "equity_points": equity_points,
    }
    return summary


def render_html(s: dict) -> str:
    total_sets = s["sets"]
    dist = s["dist"]
    theo = s["theo"]

    # 分布テーブル (7勝0負 → 0勝7負 降順)
    rows_html = []
    rows_html.append(
        "<tr><th>W/L</th><th>観測セット数</th><th>観測%</th>"
        "<th>理論% (Bin(7,p))</th><th>差</th><th>セット損益/chip</th></tr>"
    )
    for w in range(SET_SIZE, -1, -1):
        n = dist.get(w, 0)
        pct = n / total_sets * 100 if total_sets else 0
        tpct = theo[w] * 100
        diff = pct - tpct
        set_profit = (w - (SET_SIZE - w))  # wins - losses chip per set (SEQ[0]=1 unit想定)
        bar_w = int(pct * 4)  # scale
        rows_html.append(
            f"<tr><td><b>{w}勝{SET_SIZE-w}負</b></td>"
            f"<td>{n:,}</td>"
            f"<td>{pct:.3f}% <span class='bar' style='width:{bar_w}px'></span></td>"
            f"<td>{tpct:.3f}%</td>"
            f"<td class='{ 'pos' if diff>0 else 'neg' }'>{diff:+.3f}%</td>"
            f"<td class='{ 'pos' if set_profit>0 else ('neg' if set_profit<0 else '') }'>{set_profit:+d}</td>"
            "</tr>"
        )

    eq = s["equity_points"]
    if eq:
        eq_json = "[" + ",".join(f"[{x},{y}]" for x, y in eq) + "]"
    else:
        eq_json = "[]"

    profit = s["cumulative_profit"]
    color = "#4ade80" if profit > 0 else ("#f87171" if profit < 0 else "#cbd5e1")

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>旧SEQ × 7ターン制 Player常時BET 分布 / {s['cutoff']}〜</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1100px;margin:0 auto}}
h1{{font-size:32px;background:linear-gradient(135deg,#00c8ff,#6bcf8f);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}}
.card{{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:18px}}
.card .k{{font-size:12px;color:#94a3b8}}
.card .v{{font-size:22px;font-weight:700;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden}}
th,td{{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(0,200,255,0.1);color:#00c8ff;text-align:left}}
td:first-child,th:first-child{{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.bar{{display:inline-block;height:10px;background:linear-gradient(90deg,#00c8ff,#6bcf8f);border-radius:4px;margin-left:8px;vertical-align:middle}}
canvas{{width:100%;height:300px;background:rgba(255,255,255,0.02);border-radius:12px;margin:20px 0}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #00c8ff;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
.profit{{color:{color}}}
</style></head><body>
<div class="container">
<h1>旧SEQ × 7ターン制 — 常時 Player BET</h1>
<div class="sub">対象: Evolution Gaming 全テーブル / {s['cutoff']} 〜 {s['shoe_max'][:10]}</div>

<div class="grid">
  <div class="card"><div class="k">対象シュー</div><div class="v">{s['shoe_count']:,}</div></div>
  <div class="card"><div class="k">対象テーブル</div><div class="v">{s['table_count']}</div></div>
  <div class="card"><div class="k">総ハンド</div><div class="v">{s['hand_total']:,}</div></div>
  <div class="card"><div class="k">有効BET</div><div class="v">{s['bets']:,}</div></div>
  <div class="card"><div class="k">Tie(スキップ)</div><div class="v">{s['ties']:,}</div></div>
  <div class="card"><div class="k">Player勝率</div><div class="v">{s['p_rate']*100:.3f}%</div></div>
  <div class="card"><div class="k">完成セット数</div><div class="v">{s['sets']:,}</div></div>
  <div class="card"><div class="k">累計損益 (chip)</div><div class="v profit">{s['cumulative_profit']:+,}</div></div>
  <div class="card"><div class="k">最終SEQ位置</div><div class="v">SEQ[{s['final_unit_idx']}]=${s['final_unit']}</div></div>
</div>

<div class="note">
<b>旧SEQ</b> = [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142, 148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250] (49要素)<br>
<b>セット損益 (chip列)</b> は SEQ[0]=1 unit でBETした場合の1セットの chip 増減 (W-L) を示す。実際の累計は MaruBatsuTracker のSEQ進行ロジックで計算。
</div>

<h2>📊 N勝N負 分布</h2>
<table>{''.join(rows_html)}</table>

<h2>📈 セット毎 累計損益 (chip, 10,000セット毎スナップショット)</h2>
<canvas id="eq"></canvas>

<script>
const pts = {eq_json};
const canvas = document.getElementById('eq');
const ctx = canvas.getContext('2d');
function draw() {{
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W*dpr; canvas.height = H*dpr; ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  if (!pts.length) return;
  const xs = pts.map(p=>p[0]); const ys = pts.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const ymin=Math.min(0,...ys), ymax=Math.max(0,...ys);
  const pad=40;
  const sx = x=>pad+(x-xmin)/((xmax-xmin)||1)*(W-pad*2);
  const sy = y=>H-pad-(y-ymin)/((ymax-ymin)||1)*(H-pad*2);
  // zero line
  ctx.strokeStyle='rgba(255,255,255,0.2)'; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad,sy(0)); ctx.lineTo(W-pad,sy(0)); ctx.stroke();
  // axis labels
  ctx.fillStyle='#94a3b8'; ctx.font='11px sans-serif';
  ctx.fillText(xmin.toLocaleString()+' sets', pad, H-10);
  ctx.fillText(xmax.toLocaleString()+' sets', W-pad-80, H-10);
  ctx.fillText(ymax.toLocaleString()+' chip', 4, pad+10);
  ctx.fillText(ymin.toLocaleString()+' chip', 4, H-pad);
  // line
  ctx.strokeStyle='{color}'; ctx.lineWidth=2;
  ctx.beginPath();
  pts.forEach((p,i)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(i==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
  ctx.stroke();
}}
draw();
window.addEventListener('resize', draw);
</script>

<div class="note" style="border-left-color:#f87171">
<b>⚠️ 注意</b>: テーブル乗換えなしで全ハンドを1本の時系列として流している。実運用ではテーブル切替・BET窓逃し・$500上限などの要因が効くため、ここで見えた分布はあくまで「Evolution P/B列を連続読みした場合の生の分布」。実運用のPNLとは一致しない。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    s = run_backtest()
    print(f"=== 旧SEQ × 7ターン制 Player常時BET ===")
    print(f"期間: {s['cutoff']} 〜 {s['shoe_max'][:10]}")
    print(f"シュー: {s['shoe_count']:,} / テーブル: {s['table_count']} / ハンド: {s['hand_total']:,}")
    print(f"Tie: {s['ties']:,} / BET: {s['bets']:,} / Player勝率: {s['p_rate']*100:.3f}%")
    print(f"完成セット: {s['sets']:,} / 残り進行中: {s['current_turn_leftover']}")
    print(f"累計損益 (旧SEQ): {s['cumulative_profit']:+,} chip  (${s['cumulative_money']:+,.0f})")
    print(f"最終SEQ[{s['final_unit_idx']}] = ${s['final_unit']}")
    print()
    total = s["sets"]
    print(f"{'W/L':<8}{'観測':>14}{'観測%':>10}{'理論%':>10}{'差':>10}")
    for w in range(SET_SIZE, -1, -1):
        n = s["dist"].get(w, 0)
        pct = n / total * 100 if total else 0
        tpct = s["theo"][w] * 100
        print(f"{w}勝{SET_SIZE-w}負    {n:>12,}  {pct:>8.3f}%  {tpct:>8.3f}%  {pct-tpct:+8.3f}%")

    html = render_html(s)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")
