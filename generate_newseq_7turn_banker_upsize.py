"""新SEQ × 7ターン × Banker only + 1.0526x 上乗せ バックテスト

設定:
  SEQ: SEQ_COUNTER (新SEQ, 43要素, max $500)
  セット: 7ターン制 (SET_SIZE=7)
  BET: 常時 Banker、チップを1/(1-0.05)=1.0526x 上乗せして手数料相殺
  chip_base: $1 スタート
  元本: $50,000 と $100,000 の2パターンを同一トラジェクトリで比較
  Tie: スキップ (ターン数/BET数に数えない)

破綻判定: 残高 < 次のBET額 で bust
対象: analytics_vps_latest.sqlite3 / Evolution 62テーブル / 2026-04-06〜2026-04-19
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from marubatsu_strategy import MaruBatsuTracker, SEQ_COUNTER, SET_SIZE_DEFAULT  # noqa

DB_PATH = Path(__file__).parent / "analytics_vps_latest.sqlite3"
OUT_HTML = Path(__file__).parent / "report" / "newseq_7turn_banker_upsize.html"
CUTOFF = "2026-04-06"
SET_SIZE = 7            # 旧 default = 7ターン
SEQ = SEQ_COUNTER       # 新SEQ
COMMISSION = 0.05
UPSIZE = 1.0 / (1.0 - COMMISSION)  # 1.05263157...
CHIP_BASE = 1.0         # $1スタート
BANKROLLS = [50000, 100000]
SNAPSHOT_EVERY = 5000   # 何BETごとに残高をサンプル


def fetch_hands(conn):
    q = """
    SELECT h.result
    FROM hands h
    JOIN shoes_analytics s ON h.shoe_id = s.id
    WHERE s.started_at >= ?
    ORDER BY s.started_at ASC, s.id ASC, h.hand_index ASC
    """
    return conn.execute(q, (CUTOFF,))


def run_backtest():
    conn = sqlite3.connect(str(DB_PATH))
    meta = conn.execute(
        "SELECT MIN(started_at), MAX(started_at), COUNT(*), COUNT(DISTINCT table_name) "
        "FROM shoes_analytics WHERE started_at >= ?", (CUTOFF,)
    ).fetchone()

    tracker = MaruBatsuTracker(chip_base=CHIP_BASE, seq=SEQ, set_size=SET_SIZE)

    # 両シナリオを単一ループで計算
    states = {}
    for br in BANKROLLS:
        states[br] = {
            "balance": float(br),
            "peak": float(br),
            "trough": float(br),
            "max_dd": 0.0,
            "bust": False,
            "bust_at_bet": None,
            "bust_seq_idx": None,
            "bust_seq_val": None,
            "equity": [(0, float(br))],
        }

    bets = 0
    b_wins = 0     # Banker 出現 = 我々の BET 勝ち
    p_wins = 0     # Player 出現 = 我々の BET 負け
    ties = 0
    max_seq_reached = 0

    for (res,) in fetch_hands(conn):
        r = (res or "").strip().upper()
        if r in ("T", "TIE"):
            ties += 1
            continue
        if r not in ("B", "BANKER", "P", "PLAYER"):
            continue

        seq_idx = tracker.current_unit_idx
        seq_val = SEQ[min(seq_idx, len(SEQ)-1)]
        bet_dollar = seq_val * UPSIZE * CHIP_BASE
        max_seq_reached = max(max_seq_reached, seq_idx)

        # バンクロール判定 (両方)
        all_busted = True
        for br, st in states.items():
            if st["bust"]:
                continue
            if bet_dollar > st["balance"]:
                st["bust"] = True
                st["bust_at_bet"] = bets + 1
                st["bust_seq_idx"] = seq_idx
                st["bust_seq_val"] = seq_val
            else:
                all_busted = False
        if all_busted:
            break

        bets += 1
        # 結果適用
        if r in ("B", "BANKER"):
            # 我々勝ち: +seq_val * CHIP_BASE (手数料相殺後 1:1)
            delta = seq_val * CHIP_BASE
            b_wins += 1
            tracker.add_result("player")  # Treat as W for tracker
        else:
            # 我々負け: -seq_val * UPSIZE * CHIP_BASE
            delta = -bet_dollar
            p_wins += 1
            tracker.add_result("banker")  # Treat as L for tracker

        for br, st in states.items():
            if st["bust"]:
                continue
            st["balance"] += delta
            if st["balance"] > st["peak"]:
                st["peak"] = st["balance"]
            if st["balance"] < st["trough"]:
                st["trough"] = st["balance"]
            dd = st["peak"] - st["balance"]
            if dd > st["max_dd"]:
                st["max_dd"] = dd
            if bets % SNAPSHOT_EVERY == 0:
                st["equity"].append((bets, st["balance"]))

    # 末尾スナップショット
    for st in states.values():
        st["equity"].append((bets, st["balance"]))

    conn.close()

    return {
        "cutoff": CUTOFF,
        "shoe_min": meta[0],
        "shoe_max": meta[1],
        "shoe_count": meta[2],
        "table_count": meta[3],
        "bets": bets,
        "b_wins": b_wins,
        "p_wins": p_wins,
        "ties": ties,
        "b_rate": b_wins / bets if bets else 0,
        "max_seq_reached": max_seq_reached,
        "max_seq_val": SEQ[min(max_seq_reached, len(SEQ)-1)],
        "sets_completed": len(tracker.sets),
        "final_seq_idx": tracker.current_unit_idx,
        "final_seq_val": SEQ[min(tracker.current_unit_idx, len(SEQ)-1)],
        "states": states,
    }


def render_html(s: dict) -> str:
    def color(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    rows = ["<tr><th>元本</th><th>最終残高</th><th>PNL</th><th>Peak</th><th>Trough</th><th>最大DD</th><th>破綻</th><th>破綻ハンド</th></tr>"]
    for br, st in s["states"].items():
        pnl = st["balance"] - br
        bust_cell = (f"<span class='neg'><b>YES</b></span><br>"
                     f"<small>bet#{st['bust_at_bet']:,}, SEQ[{st['bust_seq_idx']}]=${st['bust_seq_val']}</small>") \
                    if st["bust"] else "<span class='pos'>NO</span>"
        rows.append(
            f"<tr><td><b>${br:,}</b></td>"
            f"<td style='color:{color(pnl)}'>${st['balance']:,.0f}</td>"
            f"<td style='color:{color(pnl)}'><b>${pnl:+,.0f}</b></td>"
            f"<td>${st['peak']:,.0f}</td>"
            f"<td>${st['trough']:,.0f}</td>"
            f"<td class='neg'>${st['max_dd']:,.0f}</td>"
            f"<td>{bust_cell}</td>"
            f"<td>{st['bust_at_bet'] or '-'}</td></tr>"
        )

    # Equity curves JSON
    def eq_json(eq):
        return "[" + ",".join(f"[{x},{y:.1f}]" for x, y in eq) + "]"

    eq_50 = eq_json(s["states"][50000]["equity"])
    eq_100 = eq_json(s["states"][100000]["equity"])

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>新SEQ × 7ターン × Banker only + 1.0526x上乗せ</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1100px;margin:0 auto}}
h1{{font-size:28px;background:linear-gradient(135deg,#fbbf24,#f87171);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}}
.card{{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:18px}}
.card .k{{font-size:12px;color:#94a3b8}}
.card .v{{font-size:22px;font-weight:700;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden}}
th,td{{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(251,191,36,0.15);color:#fbbf24;text-align:left}}
td:first-child,th:first-child{{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #fbbf24;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
canvas{{width:100%;height:360px;background:rgba(255,255,255,0.02);border-radius:12px;margin:20px 0}}
</style></head><body>
<div class="container">
<h1>🏦 新SEQ × 7ターン × Banker only + 1.0526x 上乗せ</h1>
<div class="sub">対象: Evolution 62テーブル / {s['cutoff']} 〜 {s['shoe_max'][:10]}</div>

<div class="note">
<b>戦略</b>: 常時 Bankerに BET。手数料5%相殺のため賭け額を <code>1/(1-0.05) = 1.0526x</code> 上乗せ。<br>
<b>資金管理</b>: 新SEQ (SEQ_COUNTER, 43レベル max $500) × 7ターン制 MaruBatsuロジック / chip_base $1 スタート<br>
<b>破綻</b>: 残高が次BETの必要額を下回った時点で bust
</div>

<div class="grid">
  <div class="card"><div class="k">総BET</div><div class="v">{s['bets']:,}</div></div>
  <div class="card"><div class="k">Banker勝ち</div><div class="v pos">{s['b_wins']:,}</div></div>
  <div class="card"><div class="k">Banker勝率</div><div class="v">{s['b_rate']*100:.3f}%</div></div>
  <div class="card"><div class="k">Tieスキップ</div><div class="v">{s['ties']:,}</div></div>
  <div class="card"><div class="k">完成セット</div><div class="v">{s['sets_completed']:,}</div></div>
  <div class="card"><div class="k">到達最大SEQ</div><div class="v">SEQ[{s['max_seq_reached']}]=${s['max_seq_val']}</div></div>
  <div class="card"><div class="k">最終SEQ</div><div class="v">SEQ[{s['final_seq_idx']}]=${s['final_seq_val']}</div></div>
</div>

<h2>💰 元本別結果</h2>
<table>{''.join(rows)}</table>

<h2>📉 残高推移 ({SNAPSHOT_EVERY:,}BETごと)</h2>
<canvas id="eq"></canvas>

<script>
const eq50 = {eq_50};
const eq100 = {eq_100};
const canvas = document.getElementById('eq');
const ctx = canvas.getContext('2d');

function draw() {{
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W*dpr; canvas.height = H*dpr; ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  const all = [...eq50, ...eq100];
  if (!all.length) return;
  const xs = all.map(p=>p[0]); const ys = all.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const ymin=Math.min(0,...ys), ymax=Math.max(...ys);
  const pad=60;
  const sx = x=>pad+(x-xmin)/((xmax-xmin)||1)*(W-pad*2);
  const sy = y=>H-pad-(y-ymin)/((ymax-ymin)||1)*(H-pad*2);
  // zero line
  ctx.strokeStyle='rgba(255,255,255,0.2)'; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad,sy(0)); ctx.lineTo(W-pad,sy(0)); ctx.stroke();
  // starting bankrolls (dashed)
  ctx.setLineDash([4,4]); ctx.strokeStyle='rgba(74,222,128,0.3)';
  ctx.beginPath(); ctx.moveTo(pad,sy(50000)); ctx.lineTo(W-pad,sy(50000)); ctx.stroke();
  ctx.strokeStyle='rgba(251,191,36,0.3)';
  ctx.beginPath(); ctx.moveTo(pad,sy(100000)); ctx.lineTo(W-pad,sy(100000)); ctx.stroke();
  ctx.setLineDash([]);
  // labels
  ctx.fillStyle='#94a3b8'; ctx.font='11px sans-serif';
  ctx.fillText('0', 10, sy(0)+4);
  ctx.fillText('$50k', 10, sy(50000)+4);
  ctx.fillText('$100k', 10, sy(100000)+4);
  ctx.fillText('ymax: '+ymax.toLocaleString(), 10, pad-6);
  ctx.fillText(xmin.toLocaleString()+' bets', pad, H-30);
  ctx.fillText(xmax.toLocaleString()+' bets', W-pad-80, H-30);
  // line eq50
  ctx.strokeStyle='#4ade80'; ctx.lineWidth=2;
  ctx.beginPath();
  eq50.forEach((p,i)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(i==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
  ctx.stroke();
  // line eq100
  ctx.strokeStyle='#fbbf24'; ctx.lineWidth=2;
  ctx.beginPath();
  eq100.forEach((p,i)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(i==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
  ctx.stroke();
  // legend
  ctx.fillStyle='#4ade80'; ctx.fillText('● 元本 $50,000', W-160, 30);
  ctx.fillStyle='#fbbf24'; ctx.fillText('● 元本 $100,000', W-160, 48);
}}
draw();
window.addEventListener('resize', draw);
</script>

<div class="note" style="border-left-color:#f87171;line-height:1.9">
<b>⚠️ 数学的な結論</b><br>
Banker 50.93% × 上乗せ1.0526x の EV = <code>0.5093 × 1.00 - 0.4907 × 1.0526 = -0.00721</code><br>
→ 1BET あたり <b>-0.72%</b> の期待値。賭け額を上乗せしても「負ける時も上乗せされる」ため、
1.0526x 倍はハウスエッジを消さず、むしろわずかに悪化させる。<br>
利益を出すための必要条件は <code>P(B) > 51.28%</code>。実測50.93%では<b>0.35%足りない</b> → 長期的には負ける。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    s = run_backtest()
    print("=== 新SEQ × 7ターン × Banker only + 1.0526x ===")
    print(f"期間: {s['cutoff']} 〜 {s['shoe_max'][:10]}")
    print(f"BET: {s['bets']:,} / Banker勝ち: {s['b_wins']:,} ({s['b_rate']*100:.3f}%) / Tie: {s['ties']:,}")
    print(f"完成セット: {s['sets_completed']:,} / 到達最大SEQ: SEQ[{s['max_seq_reached']}]=${s['max_seq_val']}")
    print(f"最終SEQ[{s['final_seq_idx']}]=${s['final_seq_val']}")
    print()
    print(f"{'元本':<10}{'最終残高':>15}{'PNL':>15}{'Peak':>15}{'最大DD':>15}{'破綻':>10}")
    for br, st in s["states"].items():
        pnl = st["balance"] - br
        bust = f"YES@#{st['bust_at_bet']:,}" if st["bust"] else "NO"
        print(f"${br:,}    ${st['balance']:>10,.0f}    ${pnl:>+10,.0f}    ${st['peak']:>10,.0f}    ${st['max_dd']:>10,.0f}    {bust:>10}")

    html = render_html(s)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")
