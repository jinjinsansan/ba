"""SEQ 4案 比較バックテスト — Banker + 1.0526x 上乗せ / $50利確リセット

条件:
  $1 chip_base / 元本 $50,000 / 損切なし / 利確 $50 に達したら SEQ を 0 にリセット
  Tie はスキップ / 1セット = 7ターン
  SEQ progression: 簡略MaruBatsu (overshoot=0でリセット / diff<0で+1 / diff>0で-diff)

SEQ候補:
  A: 新SEQ (SEQ_COUNTER) — 43要素 max $500 平均1.25x成長 [baseline]
  B: 旧SEQ — 48要素 max $250 平均1.15x成長
  C: 指数1.30x — 20要素 max $275 圧縮版
  D: 指数1.44x — 17要素 max $500 理論最適(4W3L recovery完全)

Banker率:
  51.05% (実データ / EV -0.72%)
  52.00% (狙い撃ち仮定 / EV +1.47%)

N_TRIALS=5 で seed を共有(同じ outcome列で比較)。
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "seq_comparison_banker_upsize.html"

SEQS = {
    "A": {
        "label": "新SEQ (SEQ_COUNTER)",
        "seq": [1, 3, 5, 7, 10, 13, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 145, 160, 175, 190, 205, 220, 235, 250, 265, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500],
        "desc": "現行新SEQ / 43要素 / max $500 / 平均1.25x",
        "color": "#fbbf24",
    },
    "B": {
        "label": "旧SEQ",
        "seq": [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142, 148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250],
        "desc": "旧SEQ / 48要素 / max $250 / 平均1.15x",
        "color": "#60a5fa",
    },
    "C": {
        "label": "指数1.30x圧縮",
        "seq": [1, 2, 3, 4, 5, 7, 9, 12, 15, 20, 26, 34, 44, 57, 74, 96, 125, 163, 212, 275],
        "desc": "指数成長1.30x / 20要素 / max $275",
        "color": "#a78bfa",
    },
    "D": {
        "label": "指数1.44x理論最適",
        "seq": [1, 2, 3, 4, 6, 9, 13, 19, 27, 39, 56, 81, 117, 168, 242, 348, 500],
        "desc": "指数成長1.44x / 17要素 / max $500 / 4W3L recovery保証",
        "color": "#4ade80",
    },
}

B_RATES = [0.5105, 0.5200]  # 実データ / 狙い撃ち

BANKROLL = 50000
PROFIT_TARGET = 50
N_HANDS = 1_723_343
N_TRIALS = 5
COMMISSION = 0.05
UPSIZE = 1.0 / (1.0 - COMMISSION)
SET_SIZE = 7
SNAPSHOT_EVERY = 5000


def simulate(seq, b_rate, seed, track_equity=False):
    rng = np.random.default_rng(seed)
    outcomes = rng.random(N_HANDS) < b_rate
    seq_len = len(seq)

    balance = float(BANKROLL)
    peak = balance
    max_dd = 0.0
    bust = False
    bust_at = None

    seq_idx = 0
    max_seq = 0
    overshoot = 0
    turn_in_set = 0
    wins_in_set = 0
    session_pnl = 0.0

    bets = 0
    wins = 0
    sets = 0
    resets = 0
    equity = [(0, balance)] if track_equity else None

    for i in range(N_HANDS):
        seq_val = seq[seq_idx if seq_idx < seq_len else seq_len - 1]
        bet = seq_val * UPSIZE

        if bet > balance:
            bust = True
            bust_at = bets + 1
            break

        bets += 1
        if outcomes[i]:
            delta = seq_val
            wins += 1
            wins_in_set += 1
        else:
            delta = -bet

        balance += delta
        session_pnl += delta

        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd

        if track_equity and bets % SNAPSHOT_EVERY == 0:
            equity.append((bets, balance))

        # 利確リセット
        if session_pnl >= PROFIT_TARGET:
            seq_idx = 0
            overshoot = 0
            turn_in_set = 0
            wins_in_set = 0
            session_pnl = 0.0
            resets += 1
            continue

        turn_in_set += 1
        if turn_in_set == SET_SIZE:
            diff = 2 * wins_in_set - SET_SIZE
            new_overshoot = max(overshoot - diff, 0)
            if new_overshoot == 0:
                seq_idx = 0
            elif diff < 0:
                seq_idx = seq_idx + 1
                if seq_idx >= seq_len:
                    seq_idx = seq_len - 1
            else:
                seq_idx = seq_idx - diff
                if seq_idx < 0:
                    seq_idx = 0
            if seq_idx > max_seq:
                max_seq = seq_idx
            overshoot = new_overshoot
            turn_in_set = 0
            wins_in_set = 0
            sets += 1

    if track_equity and equity is not None:
        equity.append((bets, balance))

    return {
        "seed": seed,
        "b_rate": b_rate,
        "bets": bets,
        "wins": wins,
        "win_rate": wins / bets if bets else 0,
        "sets": sets,
        "resets": resets,
        "max_seq": max_seq,
        "max_seq_val": seq[min(max_seq, seq_len - 1)],
        "balance": balance,
        "pnl": balance - BANKROLL,
        "peak": peak,
        "max_dd": max_dd,
        "bust": bust,
        "bust_at": bust_at,
        "equity": equity,
    }


def run_all():
    results = {}  # key: (seq_key, b_rate) -> list[trials]
    reps = {}     # key: (seq_key, b_rate) -> rep trial (trial 0)
    for seq_key, info in SEQS.items():
        for b_rate in B_RATES:
            trials = []
            for t in range(N_TRIALS):
                seed = 10000 + int(b_rate * 100) * 100 + t  # 同じrateなら同じseed並び
                r = simulate(info["seq"], b_rate, seed=seed, track_equity=(t == 0))
                trials.append(r)
            results[(seq_key, b_rate)] = trials
            reps[(seq_key, b_rate)] = trials[0]
            # 進捗ログ
            busts = sum(1 for tr in trials if tr["bust"])
            avg_pnl = sum(tr["pnl"] for tr in trials) / len(trials)
            avg_dd = sum(tr["max_dd"] for tr in trials) / len(trials)
            print(f"[{seq_key}] B={b_rate*100:.2f}% → bust {busts}/{N_TRIALS}, avgPNL ${avg_pnl:+,.0f}, avgDD ${avg_dd:,.0f}", flush=True)
    return results, reps


def aggregate(trials):
    busts = [t["bust"] for t in trials]
    pnls = [t["pnl"] for t in trials]
    dds = [t["max_dd"] for t in trials]
    peaks = [t["peak"] for t in trials]
    resets = [t["resets"] for t in trials]
    max_seqs = [t["max_seq"] for t in trials]
    return {
        "bust_count": sum(busts),
        "bust_rate": sum(busts) / len(trials),
        "avg_pnl": sum(pnls) / len(pnls),
        "max_pnl": max(pnls),
        "min_pnl": min(pnls),
        "avg_dd": sum(dds) / len(dds),
        "max_dd": max(dds),
        "avg_peak": sum(peaks) / len(peaks),
        "avg_resets": sum(resets) / len(resets),
        "avg_max_seq": sum(max_seqs) / len(max_seqs),
    }


def render_html(results, reps):
    def color(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    # 集計テーブル (SEQ × B率)
    headers = "<tr><th>SEQ</th><th>説明</th>"
    for b in B_RATES:
        headers += f"<th colspan=5>B={b*100:.2f}%</th>"
    headers += "</tr><tr><th></th><th></th>"
    for _ in B_RATES:
        headers += "<th>破綻</th><th>平均PNL</th><th>最悪PNL</th><th>平均DD</th><th>利確回数</th>"
    headers += "</tr>"

    rows = [headers]
    for seq_key, info in SEQS.items():
        row = f"<tr><td><b style='color:{info['color']}'>{seq_key}: {info['label']}</b></td><td style='font-size:11px;color:#94a3b8'>{info['desc']}</td>"
        for b in B_RATES:
            agg = aggregate(results[(seq_key, b)])
            row += (
                f"<td>{agg['bust_count']}/{N_TRIALS}</td>"
                f"<td style='color:{color(agg['avg_pnl'])}'>${agg['avg_pnl']:+,.0f}</td>"
                f"<td class='neg'>${agg['min_pnl']:+,.0f}</td>"
                f"<td>${agg['avg_dd']:,.0f}</td>"
                f"<td>{agg['avg_resets']:,.0f}</td>"
            )
        row += "</tr>"
        rows.append(row)

    # 試行別詳細テーブル
    detail_rows = ["<tr><th>SEQ</th><th>B率</th><th>seed</th><th>Banker勝率</th><th>maxSEQ</th><th>セット</th><th>利確</th><th>PNL</th><th>Peak</th><th>DD</th><th>破綻</th></tr>"]
    for seq_key, info in SEQS.items():
        for b in B_RATES:
            for tr in results[(seq_key, b)]:
                detail_rows.append(
                    f"<tr><td style='color:{info['color']}'><b>{seq_key}</b></td>"
                    f"<td>{b*100:.2f}%</td>"
                    f"<td>{tr['seed']}</td>"
                    f"<td>{tr['win_rate']*100:.3f}%</td>"
                    f"<td>SEQ[{tr['max_seq']}]=${tr['max_seq_val']}</td>"
                    f"<td>{tr['sets']:,}</td>"
                    f"<td>{tr['resets']:,}</td>"
                    f"<td style='color:{color(tr['pnl'])}'>${tr['pnl']:+,.0f}</td>"
                    f"<td>${tr['peak']:,.0f}</td>"
                    f"<td class='neg'>${tr['max_dd']:,.0f}</td>"
                    f"<td>{'<span class=neg>YES@'+str(tr['bust_at'])+'</span>' if tr['bust'] else '<span class=pos>NO</span>'}</td>"
                    "</tr>"
                )

    # equity curves (trial 0 of each combo, 2チャートに分けて B=51.05% と B=52% を表示)
    def eq_json(eq):
        if not eq:
            return "[]"
        return "[" + ",".join(f"[{x},{y:.1f}]" for x, y in eq) + "]"

    curves_51 = []
    curves_52 = []
    for seq_key, info in SEQS.items():
        rep51 = reps[(seq_key, 0.5105)]
        rep52 = reps[(seq_key, 0.5200)]
        curves_51.append((seq_key, info["label"], info["color"], eq_json(rep51["equity"])))
        curves_52.append((seq_key, info["label"], info["color"], eq_json(rep52["equity"])))

    def curves_js(curves_list, var_name):
        return f"const {var_name} = [" + ",".join(
            f"{{k:'{k}',lbl:'{lbl}',c:'{c}',d:{d}}}" for k, lbl, c, d in curves_list
        ) + "];"

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>SEQ比較 Banker upsize / $50利確リセット</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:28px;background:linear-gradient(135deg,#4ade80,#fbbf24,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden;font-size:12px}}
th,td{{padding:8px 10px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(74,222,128,0.15);color:#4ade80;text-align:left;font-size:11px}}
td:nth-child(-n+2),th:nth-child(-n+2){{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #4ade80;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
canvas{{width:100%;height:340px;background:rgba(255,255,255,0.02);border-radius:12px;margin:10px 0 30px}}
h2{{color:#4ade80;margin-top:36px}}
h3{{color:#94a3b8;font-weight:500;margin-top:24px}}
</style></head><body>
<div class="container">
<h1>🔬 SEQ 4案 比較バックテスト</h1>
<div class="sub">Banker only + 1.0526x上乗せ / $1 base / 元本$50,000 / 損切なし / $50利確でSEQリセット / Bernoulli合成 × {N_TRIALS}試行 seed共有</div>

<div class="note">
<b>SEQ候補</b>:
<ul style="margin:8px 0;line-height:1.8">
<li><b style="color:#fbbf24">A: 新SEQ</b> (43要素 max $500, 1.25x) — 現行ベースライン</li>
<li><b style="color:#60a5fa">B: 旧SEQ</b> (48要素 max $250, 1.15x) — 刻み細かい</li>
<li><b style="color:#a78bfa">C: 指数1.30x</b> (20要素 max $275) — 圧縮</li>
<li><b style="color:#4ade80">D: 指数1.44x</b> (17要素 max $500) — 理論最適 (負けは勝ちの1.437倍重い補正)</li>
</ul>
<b>Banker勝率</b>: 51.05% (実データ / EV -0.72%/bet) / 52.00% (狙い撃ち仮定 / EV +1.47%/bet)
</div>

<h2>📊 集計 (全{N_TRIALS}試行 × 4 SEQ × 2 B率)</h2>
<table>{''.join(rows)}</table>

<h2>📋 試行別詳細</h2>
<table>{''.join(detail_rows)}</table>

<h2>📈 残高推移 (trial#0)</h2>
<h3>B = 51.05% (実データ相当 / EV -0.72%)</h3>
<canvas id="eq51"></canvas>

<h3>B = 52.00% (狙い撃ち仮定 / EV +1.47%)</h3>
<canvas id="eq52"></canvas>

<script>
{curves_js(curves_51, 'C51')}
{curves_js(curves_52, 'C52')}

function drawAll(canvasId, curves) {{
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W*dpr; canvas.height = H*dpr; ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  const all = curves.flatMap(c=>c.d);
  if (!all.length) return;
  const xs = all.map(p=>p[0]); const ys = all.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const ymin=Math.min(0,...ys), ymax=Math.max(...ys);
  const pad=60;
  const sx = x=>pad+(x-xmin)/((xmax-xmin)||1)*(W-pad*2);
  const sy = y=>H-pad-(y-ymin)/((ymax-ymin)||1)*(H-pad*2);
  // zero + bankroll
  ctx.strokeStyle='rgba(255,255,255,0.2)'; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad,sy(0)); ctx.lineTo(W-pad,sy(0)); ctx.stroke();
  ctx.setLineDash([4,4]); ctx.strokeStyle='rgba(148,163,184,0.4)';
  ctx.beginPath(); ctx.moveTo(pad,sy(50000)); ctx.lineTo(W-pad,sy(50000)); ctx.stroke();
  ctx.setLineDash([]);
  // labels
  ctx.fillStyle='#94a3b8'; ctx.font='11px sans-serif';
  ctx.fillText('0', 10, sy(0)+4);
  ctx.fillText('$50k', 10, sy(50000)+4);
  ctx.fillText('ymax $'+Math.round(ymax).toLocaleString(), 10, pad-6);
  ctx.fillText(xmin.toLocaleString()+' bets', pad, H-30);
  ctx.fillText(xmax.toLocaleString()+' bets', W-pad-80, H-30);
  // lines
  curves.forEach((c,i) => {{
    ctx.strokeStyle = c.c; ctx.lineWidth = 2;
    ctx.beginPath();
    c.d.forEach((p,j)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(j==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
    ctx.stroke();
    ctx.fillStyle = c.c; ctx.fillText('● ' + c.k + ': ' + c.lbl, W-230, 24 + i*18);
  }});
}}
drawAll('eq51', C51);
drawAll('eq52', C52);
window.addEventListener('resize', () => {{ drawAll('eq51', C51); drawAll('eq52', C52); }});
</script>

<div class="note" style="border-left-color:#fbbf24">
<b>⚠️ 注意</b><br>
SEQ progression は簡略版 (MaruBatsu slashed logic 省略)。実運用コードとはわずかに挙動が異なる可能性あり。<br>
EV がマイナス (B=51.05%) の場合、どのSEQでも長期的に破綻する傾向(利確リセットで延命するが回収できない)。<br>
EV がプラス (B=52%) の場合、全SEQで黒字だが利益総額・DD・利確回数に差が出る。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    print(f"=== SEQ 4案 比較 / Banker+1.0526x / $50利確リセット / 元本${BANKROLL:,} ===")
    print(f"N_TRIALS={N_TRIALS} × 4 SEQ × {len(B_RATES)} rates = {N_TRIALS*4*len(B_RATES)} sims")
    print(f"N_HANDS={N_HANDS:,}/trial")
    print()

    results, reps = run_all()

    print("\n=== 集計 ===")
    for seq_key, info in SEQS.items():
        print(f"\n[{seq_key}: {info['label']}]")
        for b in B_RATES:
            agg = aggregate(results[(seq_key, b)])
            print(f"  B={b*100:.2f}%: 破綻 {agg['bust_count']}/{N_TRIALS} | "
                  f"PNL 平均 ${agg['avg_pnl']:+,.0f} (最悪 ${agg['min_pnl']:+,.0f}) | "
                  f"DD 平均 ${agg['avg_dd']:,.0f} | "
                  f"利確 {agg['avg_resets']:,.0f}回 | "
                  f"maxSEQ avg {agg['avg_max_seq']:.1f}")

    html = render_html(results, reps)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")
