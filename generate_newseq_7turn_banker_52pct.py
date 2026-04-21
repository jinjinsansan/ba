"""Banker 52% 狙い撃ちができた場合の 新SEQ×7T×Banker+1.0526x シミュレーション (高速版)

仮定: 何らかのフィルタで Banker 勝率 52% (非Tieベース) の状態だけを捕捉できる。
方法: Bernoulli(0.52) で 1,723,343 ハンド × N_TRIALS 回、$50k / $100k 並行シミュレート。
SEQ progression: MaruBatsu の簡略化版
  - 1セット = 7ターン
  - セット終了時、diff = wins - losses
  - overshoot = max(prev_overshoot - diff, 0)
  - overshoot=0 → seq_idx = 0 (リセット)
  - diff < 0 → seq_idx += 1 (前進)
  - diff > 0 (with overshoot > 0) → seq_idx -= diff (部分回復)

理論: EV/bet = 0.52 × 1.00 - 0.48 × 1.0526 = +0.01474 (+1.47%)
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from marubatsu_strategy import SEQ_COUNTER  # noqa

OUT_HTML = Path(__file__).parent / "report" / "newseq_7turn_banker_52pct.html"
N_HANDS = 1_723_343
B_RATE = 0.52
SEQ = SEQ_COUNTER
SEQ_LEN = len(SEQ)
SET_SIZE = 7
COMMISSION = 0.05
UPSIZE = 1.0 / (1.0 - COMMISSION)
BANKROLLS = [50000, 100000]
N_TRIALS = 10
SNAPSHOT_EVERY = 5000


def simulate(seed: int, track_equity: bool = False):
    rng = np.random.default_rng(seed)
    outcomes = rng.random(N_HANDS) < B_RATE  # True = Banker → 我々勝ち

    states = {}
    for br in BANKROLLS:
        states[br] = {
            "balance": float(br),
            "peak": float(br),
            "max_dd": 0.0,
            "bust": False,
            "bust_at": None,
            "equity": [(0, float(br))] if track_equity else None,
        }

    seq_idx = 0
    overshoot = 0
    turn_in_set = 0
    wins_in_set = 0
    bets = 0
    max_seq = 0
    sets_done = 0
    total_wins = 0

    for i in range(N_HANDS):
        seq_val = SEQ[seq_idx]
        bet = seq_val * UPSIZE

        # bust check
        all_busted = True
        for br, st in states.items():
            if st["bust"]:
                continue
            if bet > st["balance"]:
                st["bust"] = True
                st["bust_at"] = bets + 1
            else:
                all_busted = False
        if all_busted:
            break

        bets += 1
        if outcomes[i]:
            delta = seq_val
            wins_in_set += 1
            total_wins += 1
        else:
            delta = -bet

        for br, st in states.items():
            if st["bust"]:
                continue
            st["balance"] += delta
            if st["balance"] > st["peak"]:
                st["peak"] = st["balance"]
            dd = st["peak"] - st["balance"]
            if dd > st["max_dd"]:
                st["max_dd"] = dd
            if track_equity and bets % SNAPSHOT_EVERY == 0:
                st["equity"].append((bets, st["balance"]))

        turn_in_set += 1
        if turn_in_set == SET_SIZE:
            diff = 2 * wins_in_set - SET_SIZE
            new_overshoot = max(overshoot - diff, 0)
            if new_overshoot == 0:
                seq_idx = 0
            elif diff < 0:
                seq_idx = seq_idx + 1
                if seq_idx >= SEQ_LEN:
                    seq_idx = SEQ_LEN - 1
            else:
                seq_idx = seq_idx - diff
                if seq_idx < 0:
                    seq_idx = 0
            overshoot = new_overshoot
            if seq_idx > max_seq:
                max_seq = seq_idx
            sets_done += 1
            turn_in_set = 0
            wins_in_set = 0

    if track_equity:
        for st in states.values():
            if st["equity"] is not None:
                st["equity"].append((bets, st["balance"]))

    return {
        "seed": seed,
        "bets": bets,
        "wins": total_wins,
        "win_rate": total_wins / bets if bets else 0,
        "max_seq": max_seq,
        "sets": sets_done,
        "states": states,
    }


def run_mc():
    trials = []
    rep = None
    for t in range(N_TRIALS):
        print(f"Trial {t+1}/{N_TRIALS}...", flush=True)
        r = simulate(seed=1000 + t, track_equity=(t == 0))
        trials.append(r)
        if t == 0:
            rep = r
        s50 = r["states"][50000]
        s100 = r["states"][100000]
        pnl50 = s50["balance"] - 50000
        pnl100 = s100["balance"] - 100000
        print(f"  Banker={r['win_rate']*100:.3f}% maxSEQ[{r['max_seq']}] sets={r['sets']:,}", flush=True)
        print(f"  $50k: PNL ${pnl50:+,.0f} / bust={'YES@'+str(s50['bust_at']) if s50['bust'] else 'NO'} / DD ${s50['max_dd']:,.0f}", flush=True)
        print(f"  $100k: PNL ${pnl100:+,.0f} / bust={'YES@'+str(s100['bust_at']) if s100['bust'] else 'NO'} / DD ${s100['max_dd']:,.0f}", flush=True)
    return trials, rep


def aggregate(trials):
    agg = {}
    for br in BANKROLLS:
        busts = [t["states"][br]["bust"] for t in trials]
        pnls = [t["states"][br]["balance"] - br for t in trials]
        dds = [t["states"][br]["max_dd"] for t in trials]
        peaks = [t["states"][br]["peak"] for t in trials]
        bust_ats = [t["states"][br]["bust_at"] for t in trials if t["states"][br]["bust"]]
        agg[br] = {
            "bust_count": sum(busts),
            "bust_rate": sum(busts) / len(trials),
            "avg_pnl": sum(pnls) / len(pnls),
            "max_pnl": max(pnls),
            "min_pnl": min(pnls),
            "avg_dd": sum(dds) / len(dds),
            "max_dd_overall": max(dds),
            "avg_peak": sum(peaks) / len(peaks),
            "max_peak": max(peaks),
            "bust_avg_bet": sum(bust_ats) / len(bust_ats) if bust_ats else None,
        }
    return agg


def render_html(trials, rep, agg):
    def color(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    agg_rows = ["<tr><th>元本</th><th>破綻</th><th>破綻率</th><th>平均PNL</th><th>最悪PNL</th><th>最良PNL</th><th>平均DD</th><th>最大DD</th><th>平均Peak</th></tr>"]
    for br in BANKROLLS:
        a = agg[br]
        agg_rows.append(
            f"<tr><td><b>${br:,}</b></td>"
            f"<td>{a['bust_count']}/{N_TRIALS}</td>"
            f"<td>{a['bust_rate']*100:.0f}%</td>"
            f"<td style='color:{color(a['avg_pnl'])}'>${a['avg_pnl']:+,.0f}</td>"
            f"<td class='neg'>${a['min_pnl']:+,.0f}</td>"
            f"<td class='pos'>${a['max_pnl']:+,.0f}</td>"
            f"<td>${a['avg_dd']:,.0f}</td>"
            f"<td class='neg'>${a['max_dd_overall']:,.0f}</td>"
            f"<td class='pos'>${a['avg_peak']:,.0f}</td></tr>"
        )

    trial_rows = ["<tr><th>seed</th><th>Banker勝率</th><th>maxSEQ</th><th>セット</th><th>$50k PNL</th><th>$50k bust</th><th>$100k PNL</th><th>$100k bust</th></tr>"]
    for t in trials:
        s50 = t["states"][50000]
        s100 = t["states"][100000]
        pnl50 = s50["balance"] - 50000
        pnl100 = s100["balance"] - 100000
        trial_rows.append(
            f"<tr><td>{t['seed']}</td>"
            f"<td>{t['win_rate']*100:.3f}%</td>"
            f"<td>SEQ[{t['max_seq']}]=${SEQ[t['max_seq']]}</td>"
            f"<td>{t['sets']:,}</td>"
            f"<td style='color:{color(pnl50)}'>${pnl50:+,.0f}</td>"
            f"<td>{'<span class=neg>YES@'+str(s50['bust_at'])+'</span>' if s50['bust'] else '<span class=pos>NO</span>'}</td>"
            f"<td style='color:{color(pnl100)}'>${pnl100:+,.0f}</td>"
            f"<td>{'<span class=neg>YES@'+str(s100['bust_at'])+'</span>' if s100['bust'] else '<span class=pos>NO</span>'}</td></tr>"
        )

    def eq_json(eq):
        if not eq:
            return "[]"
        return "[" + ",".join(f"[{x},{y:.1f}]" for x, y in eq) + "]"

    eq_50 = eq_json(rep["states"][50000]["equity"])
    eq_100 = eq_json(rep["states"][100000]["equity"])

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>新SEQ × 7T × Banker only + 1.0526x (Banker 52% 狙い撃ち)</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1100px;margin:0 auto}}
h1{{font-size:28px;background:linear-gradient(135deg,#4ade80,#fbbf24);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}}
.card{{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:18px}}
.card .k{{font-size:12px;color:#94a3b8}}
.card .v{{font-size:22px;font-weight:700;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden;font-size:13px}}
th,td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(74,222,128,0.15);color:#4ade80;text-align:left}}
td:first-child,th:first-child{{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #4ade80;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
canvas{{width:100%;height:360px;background:rgba(255,255,255,0.02);border-radius:12px;margin:20px 0}}
</style></head><body>
<div class="container">
<h1>🎯 新SEQ × 7T × Banker only + 1.0526x 上乗せ<br><small style="font-size:20px">(Banker 52% 狙い撃ちシミュレーション)</small></h1>
<div class="sub">Bernoulli(0.52) × 1,723,343 合成ハンド × {N_TRIALS}試行</div>

<div class="note">
<b>仮定</b>: フィルタで Banker 勝率 52%(非Tieベース)の区間だけを捕捉できる前提。<br>
<b>理論EV</b>: <code>0.52 × 1.00 - 0.48 × 1.0526 = +0.01474</code> → <b>+1.47%/bet</b> 長期プラス。<br>
<b>検証</b>: {N_TRIALS}回の独立シミュレーションで <b>短期破綻するか</b>。<br>
<b>SEQ progression</b>: 簡略化(overshoot=0でリセット / diff&lt;0で+1進行 / diff&gt;0で-diff戻る)
</div>

<h2>📊 モンテカルロ集計 ({N_TRIALS}試行)</h2>
<table>{''.join(agg_rows)}</table>

<h2>📋 試行別結果</h2>
<table>{''.join(trial_rows)}</table>

<h2>📈 代表トラジェクトリ (Trial seed=1000)</h2>
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
  ctx.strokeStyle='rgba(255,255,255,0.2)'; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad,sy(0)); ctx.lineTo(W-pad,sy(0)); ctx.stroke();
  ctx.setLineDash([4,4]); ctx.strokeStyle='rgba(74,222,128,0.3)';
  ctx.beginPath(); ctx.moveTo(pad,sy(50000)); ctx.lineTo(W-pad,sy(50000)); ctx.stroke();
  ctx.strokeStyle='rgba(251,191,36,0.3)';
  ctx.beginPath(); ctx.moveTo(pad,sy(100000)); ctx.lineTo(W-pad,sy(100000)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle='#94a3b8'; ctx.font='11px sans-serif';
  ctx.fillText('0', 10, sy(0)+4);
  ctx.fillText('$50k', 10, sy(50000)+4);
  ctx.fillText('$100k', 10, sy(100000)+4);
  ctx.fillText('ymax $'+Math.round(ymax).toLocaleString(), 10, pad-6);
  ctx.fillText(xmin.toLocaleString()+' bets', pad, H-30);
  ctx.fillText(xmax.toLocaleString()+' bets', W-pad-80, H-30);
  ctx.strokeStyle='#4ade80'; ctx.lineWidth=2;
  ctx.beginPath();
  eq50.forEach((p,i)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(i==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
  ctx.stroke();
  ctx.strokeStyle='#fbbf24'; ctx.lineWidth=2;
  ctx.beginPath();
  eq100.forEach((p,i)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(i==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
  ctx.stroke();
  ctx.fillStyle='#4ade80'; ctx.fillText('● 元本 $50,000', W-160, 30);
  ctx.fillStyle='#fbbf24'; ctx.fillText('● 元本 $100,000', W-160, 48);
}}
draw();
window.addEventListener('resize', draw);
</script>

<div class="note" style="border-left-color:#fbbf24">
<b>⚠️ 前提条件の重さ</b>: この結果は「B=52% のストリームを外れなく選別できる」という非現実的仮定下。
実際のフィルタ精度は LLN 収束に必要な観測窓が長く、選別の瞬間には既にエッジが消えていることが多い。
52% の区間は確かに存在するが、<b>事前に予測する</b>のは別次元の難題。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    print(f"=== 新SEQ × 7T × Banker + 1.0526x (Banker {B_RATE*100:.0f}%狙い撃ち) ===")
    print(f"N_TRIALS={N_TRIALS}, N_HANDS={N_HANDS:,}/trial")
    print(f"理論EV/bet = +{(B_RATE*1.0 - (1-B_RATE)*UPSIZE)*100:.3f}%")
    print()

    trials, rep = run_mc()
    agg = aggregate(trials)

    print()
    print("=== 集計 ===")
    for br in BANKROLLS:
        a = agg[br]
        print(f"${br:,}: 破綻 {a['bust_count']}/{N_TRIALS} ({a['bust_rate']*100:.0f}%)")
        print(f"  PNL 平均 ${a['avg_pnl']:+,.0f} / 最悪 ${a['min_pnl']:+,.0f} / 最良 ${a['max_pnl']:+,.0f}")
        print(f"  DD 平均 ${a['avg_dd']:,.0f} / 最大 ${a['max_dd_overall']:,.0f}")
        print()

    html = render_html(trials, rep, agg)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"HTML: {OUT_HTML}")
