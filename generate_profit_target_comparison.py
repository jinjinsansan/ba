"""利確額 比較バックテスト — 新SEQ × Banker + 1.0526x / B=52%

利確額候補: $20 / $30 / $50 / $75 / $100 / $150
他条件: $1 base / 元本 $50,000 / 損切なし / 新SEQ(SEQ_COUNTER)
Banker率: 52.00% (狙い撃ち仮定)
試行: 10回 seed共有 (全利確額で同じoutcome列)
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "profit_target_comparison.html"

SEQ = [1, 3, 5, 7, 10, 13, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 145, 160, 175, 190, 205, 220, 235, 250, 265, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500]
SEQ_LEN = len(SEQ)
PROFIT_TARGETS = [20, 30, 50, 75, 100, 150]
B_RATE = 0.52
BANKROLL = 50000
N_HANDS = 1_723_343
N_TRIALS = 10
COMMISSION = 0.05
UPSIZE = 1.0 / (1.0 - COMMISSION)
SET_SIZE = 7
SNAPSHOT_EVERY = 5000
TARGET_COLORS = {
    20: "#60a5fa", 30: "#4ade80", 50: "#fbbf24",
    75: "#fb923c", 100: "#f87171", 150: "#a78bfa",
}


def simulate(target, seed, track_equity=False):
    rng = np.random.default_rng(seed)
    outcomes = rng.random(N_HANDS) < B_RATE

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
    session_bets = 0
    session_peak_pnl = 0.0  # セッション内最大利益 (リセット前のピーク)

    bets = 0
    wins = 0
    sets = 0
    resets = 0
    longest_session_bets = 0
    deepest_session_dd = 0.0  # セッション内最大DD
    equity = [(0, balance)] if track_equity else None

    for i in range(N_HANDS):
        seq_val = SEQ[seq_idx if seq_idx < SEQ_LEN else SEQ_LEN - 1]
        bet = seq_val * UPSIZE

        if bet > balance:
            bust = True
            bust_at = bets + 1
            break

        bets += 1
        session_bets += 1
        if outcomes[i]:
            delta = seq_val
            wins += 1
            wins_in_set += 1
        else:
            delta = -bet

        balance += delta
        session_pnl += delta

        if session_pnl > session_peak_pnl:
            session_peak_pnl = session_pnl
        session_dd = session_peak_pnl - session_pnl
        if session_dd > deepest_session_dd:
            deepest_session_dd = session_dd

        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd

        if track_equity and bets % SNAPSHOT_EVERY == 0:
            equity.append((bets, balance))

        # 利確リセット
        if session_pnl >= target:
            if session_bets > longest_session_bets:
                longest_session_bets = session_bets
            seq_idx = 0
            overshoot = 0
            turn_in_set = 0
            wins_in_set = 0
            session_pnl = 0.0
            session_bets = 0
            session_peak_pnl = 0.0
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
                if seq_idx >= SEQ_LEN:
                    seq_idx = SEQ_LEN - 1
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
        "target": target,
        "seed": seed,
        "bets": bets,
        "wins": wins,
        "win_rate": wins / bets if bets else 0,
        "sets": sets,
        "resets": resets,
        "max_seq": max_seq,
        "max_seq_val": SEQ[min(max_seq, SEQ_LEN - 1)],
        "balance": balance,
        "pnl": balance - BANKROLL,
        "peak": peak,
        "max_dd": max_dd,
        "longest_session_bets": longest_session_bets,
        "deepest_session_dd": deepest_session_dd,
        "bust": bust,
        "bust_at": bust_at,
        "equity": equity,
    }


def aggregate(trials):
    pnls = [t["pnl"] for t in trials]
    dds = [t["max_dd"] for t in trials]
    busts = [t["bust"] for t in trials]
    resets = [t["resets"] for t in trials]
    long_sess = [t["longest_session_bets"] for t in trials]
    deep_sess_dd = [t["deepest_session_dd"] for t in trials]
    return {
        "bust_count": sum(busts),
        "avg_pnl": sum(pnls) / len(pnls),
        "min_pnl": min(pnls),
        "max_pnl": max(pnls),
        "avg_dd": sum(dds) / len(dds),
        "max_dd": max(dds),
        "avg_resets": sum(resets) / len(resets),
        "avg_long_sess": sum(long_sess) / len(long_sess),
        "avg_deep_sess_dd": sum(deep_sess_dd) / len(deep_sess_dd),
    }


def run_all():
    results = {}
    reps = {}
    for target in PROFIT_TARGETS:
        trials = []
        for t in range(N_TRIALS):
            seed = 30000 + t  # seed共有 (同じoutcome列)
            r = simulate(target, seed=seed, track_equity=(t == 0))
            trials.append(r)
        results[target] = trials
        reps[target] = trials[0]
        agg = aggregate(trials)
        print(f"利確 ${target}: bust {agg['bust_count']}/{N_TRIALS} | "
              f"avgPNL ${agg['avg_pnl']:+,.0f} | avgDD ${agg['avg_dd']:,.0f} | "
              f"利確 {agg['avg_resets']:,.0f}回 | 最長セッション {agg['avg_long_sess']:,.0f}bet",
              flush=True)
    return results, reps


def render_html(results, reps):
    def color(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    # 集計
    rows = ["<tr><th>利確額</th><th>破綻</th><th>平均PNL</th><th>最悪PNL</th><th>最良PNL</th><th>平均DD</th><th>最大DD</th><th>利確回数</th><th>最長セッション</th><th>セッション内最深DD</th></tr>"]
    for target in PROFIT_TARGETS:
        agg = aggregate(results[target])
        c = TARGET_COLORS.get(target, "#cbd5e1")
        rows.append(
            f"<tr><td><b style='color:{c}'>${target}</b></td>"
            f"<td>{agg['bust_count']}/{N_TRIALS}</td>"
            f"<td style='color:{color(agg['avg_pnl'])}'><b>${agg['avg_pnl']:+,.0f}</b></td>"
            f"<td class='neg'>${agg['min_pnl']:+,.0f}</td>"
            f"<td class='pos'>${agg['max_pnl']:+,.0f}</td>"
            f"<td>${agg['avg_dd']:,.0f}</td>"
            f"<td class='neg'>${agg['max_dd']:,.0f}</td>"
            f"<td>{agg['avg_resets']:,.0f}</td>"
            f"<td>{agg['avg_long_sess']:,.0f} bet</td>"
            f"<td>${agg['avg_deep_sess_dd']:,.0f}</td></tr>"
        )

    # 詳細試行
    detail_rows = ["<tr><th>利確</th><th>seed</th><th>Banker勝率</th><th>maxSEQ</th><th>PNL</th><th>Peak</th><th>DD</th><th>利確</th><th>最長Sess</th><th>Sess最深DD</th></tr>"]
    for target in PROFIT_TARGETS:
        for tr in results[target]:
            c = TARGET_COLORS.get(target, "#cbd5e1")
            detail_rows.append(
                f"<tr><td style='color:{c}'><b>${target}</b></td>"
                f"<td>{tr['seed']}</td>"
                f"<td>{tr['win_rate']*100:.3f}%</td>"
                f"<td>SEQ[{tr['max_seq']}]=${tr['max_seq_val']}</td>"
                f"<td style='color:{color(tr['pnl'])}'>${tr['pnl']:+,.0f}</td>"
                f"<td>${tr['peak']:,.0f}</td>"
                f"<td class='neg'>${tr['max_dd']:,.0f}</td>"
                f"<td>{tr['resets']:,}</td>"
                f"<td>{tr['longest_session_bets']:,}</td>"
                f"<td>${tr['deepest_session_dd']:,.0f}</td></tr>"
            )

    # equity curves
    def eq_json(eq):
        if not eq:
            return "[]"
        return "[" + ",".join(f"[{x},{y:.1f}]" for x, y in eq) + "]"

    curves = []
    for target in PROFIT_TARGETS:
        curves.append({
            "k": f"${target}",
            "c": TARGET_COLORS.get(target, "#cbd5e1"),
            "d": eq_json(reps[target]["equity"]),
        })
    curves_js = "const CURVES = [" + ",".join(
        f"{{k:'{c['k']}',c:'{c['c']}',d:{c['d']}}}" for c in curves
    ) + "];"

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>利確額比較 / 新SEQ Banker upsize / B=52%</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1200px;margin:0 auto}}
h1{{font-size:28px;background:linear-gradient(135deg,#60a5fa,#4ade80,#fbbf24,#f87171);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden;font-size:13px}}
th,td{{padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(74,222,128,0.15);color:#4ade80;text-align:left;font-size:12px}}
td:first-child,th:first-child{{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #4ade80;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
canvas{{width:100%;height:400px;background:rgba(255,255,255,0.02);border-radius:12px;margin:20px 0}}
h2{{color:#4ade80;margin-top:36px}}
</style></head><body>
<div class="container">
<h1>💎 利確額比較バックテスト</h1>
<div class="sub">新SEQ × Banker + 1.0526x / B=52% 狙い撃ち / 元本$50,000 / 損切なし / {N_TRIALS}試行seed共有</div>

<div class="note">
<b>検証</b>: $20 / $30 / $50 / $75 / $100 / $150 の6パターンで <code>利確達成で SEQ リセット</code> 動作を比較。<br>
<b>seed共有</b>: 各試行は利確額間で同じoutcome列を使うので、純粋に「利確額」だけの影響を観察できる。<br>
<b>理論</b>: Banker 52% / EV +1.47%/bet では長期プラスが保証されるが、利確額で <b>サイクル数・DD・総利益</b> が変化。
</div>

<h2>📊 利確額別集計 ({N_TRIALS}試行)</h2>
<table>{''.join(rows)}</table>

<h2>📋 試行別詳細</h2>
<table>{''.join(detail_rows)}</table>

<h2>📈 残高推移 (trial#0 / seed=30000)</h2>
<canvas id="eq"></canvas>

<script>
{curves_js}

function draw() {{
  const canvas = document.getElementById('eq');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W*dpr; canvas.height = H*dpr; ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  const all = CURVES.flatMap(c=>c.d);
  if (!all.length) return;
  const xs = all.map(p=>p[0]); const ys = all.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs);
  const ymin=Math.min(0,...ys), ymax=Math.max(...ys);
  const pad=60;
  const sx = x=>pad+(x-xmin)/((xmax-xmin)||1)*(W-pad*2);
  const sy = y=>H-pad-(y-ymin)/((ymax-ymin)||1)*(H-pad*2);
  ctx.strokeStyle='rgba(255,255,255,0.2)'; ctx.lineWidth=1;
  ctx.beginPath(); ctx.moveTo(pad,sy(0)); ctx.lineTo(W-pad,sy(0)); ctx.stroke();
  ctx.setLineDash([4,4]); ctx.strokeStyle='rgba(148,163,184,0.4)';
  ctx.beginPath(); ctx.moveTo(pad,sy(50000)); ctx.lineTo(W-pad,sy(50000)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle='#94a3b8'; ctx.font='11px sans-serif';
  ctx.fillText('0', 10, sy(0)+4);
  ctx.fillText('$50k', 10, sy(50000)+4);
  ctx.fillText('ymax $'+Math.round(ymax).toLocaleString(), 10, pad-6);
  ctx.fillText(xmin.toLocaleString()+' bets', pad, H-30);
  ctx.fillText(xmax.toLocaleString()+' bets', W-pad-80, H-30);
  CURVES.forEach((c,i) => {{
    ctx.strokeStyle = c.c; ctx.lineWidth = 2;
    ctx.beginPath();
    c.d.forEach((p,j)=>{{ const X=sx(p[0]),Y=sy(p[1]); if(j==0)ctx.moveTo(X,Y); else ctx.lineTo(X,Y); }});
    ctx.stroke();
    ctx.fillStyle = c.c; ctx.fillText('● 利確 ' + c.k, W-120, 24 + i*18);
  }});
}}
draw();
window.addEventListener('resize', draw);
</script>

<div class="note" style="border-left-color:#fbbf24">
<b>⚠️ 注意</b><br>
B=52% 狙い撃ちが維持できる前提。実運用でフィルタ精度が落ちたら EV マイナスになり、どの利確額でも赤字化する。<br>
SEQ progression は簡略版(slashed logic 省略)。実運用コードとはわずかに挙動が異なる可能性あり。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    print(f"=== 利確額比較 / 新SEQ × Banker+1.0526x / B={B_RATE*100:.0f}% ===")
    print(f"元本 ${BANKROLL:,} / 損切なし / N_TRIALS={N_TRIALS} / N_HANDS={N_HANDS:,}")
    print(f"候補: ${' / $'.join(str(t) for t in PROFIT_TARGETS)}")
    print()

    results, reps = run_all()

    print("\n=== 総合ランキング (平均PNL降順) ===")
    sorted_targets = sorted(PROFIT_TARGETS, key=lambda t: -aggregate(results[t])["avg_pnl"])
    for rank, target in enumerate(sorted_targets, 1):
        agg = aggregate(results[target])
        print(f"{rank}. 利確 ${target}: avgPNL ${agg['avg_pnl']:+,.0f} / avgDD ${agg['avg_dd']:,.0f} / 利確{agg['avg_resets']:,.0f}回 / 最長セッション{agg['avg_long_sess']:,.0f}bet")

    html = render_html(results, reps)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")
