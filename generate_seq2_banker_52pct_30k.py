"""新SEQ2 × 7ターン × Banker only × B=52% — 利確$30/$100 比較 / 元本$30k

手数料補正なし版:
- BET 額 = seq_val (そのまま)
- 勝ち時 delta = +0.95 × seq_val (Banker 5% rake を実損として反映)
- 負け時 delta = -seq_val
- EV/bet = 0.52 × 0.95 - 0.48 × 1.00 = +0.014 (+1.4%)

目的: この SEQ で $30k 元本が耐えるか / 最大DD / PNL を $30 利確 vs $100 利確で比較
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "seq2_banker_52pct_30k.html"

SEQ = [
    10, 20, 30, 40, 50,
    70, 90, 110,
    140, 170, 200,
    250, 300, 350,
    430, 510, 590,
    700, 810,
    940, 1090,
    1260, 1440,
    1640, 1870,
    2150, 2450,
    2800,
]
SEQ_LEN = len(SEQ)
PROFIT_TARGETS = [30, 100]
B_RATE = 0.52
BANKROLL = 30000
N_HANDS = 1_723_343
N_TRIALS = 20
COMMISSION = 0.05
WIN_FACTOR = 1.0 - COMMISSION  # 勝ち時 0.95×
SET_SIZE = 7
SNAPSHOT_EVERY = 5000
TARGET_COLORS = {30: "#4ade80", 100: "#f87171"}


def simulate(target, seed, track_equity=False):
    rng = np.random.default_rng(seed)
    outcomes = rng.random(N_HANDS) < B_RATE  # True = Banker (我々勝ち)

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
    session_peak_pnl = 0.0

    bets = 0
    wins = 0
    sets = 0
    resets = 0
    longest_session_bets = 0
    deepest_session_dd = 0.0
    equity = [(0, balance)] if track_equity else None

    for i in range(N_HANDS):
        seq_val = SEQ[seq_idx if seq_idx < SEQ_LEN else SEQ_LEN - 1]
        bet = seq_val  # 手数料補正なし

        if bet > balance:
            bust = True
            bust_at = bets + 1
            break

        bets += 1
        session_bets += 1
        if outcomes[i]:
            delta = +WIN_FACTOR * seq_val  # +0.95 × seq_val
            wins += 1
            wins_in_set += 1
        else:
            delta = -seq_val

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
    deep_sdd = [t["deepest_session_dd"] for t in trials]
    max_seqs = [t["max_seq"] for t in trials]
    peaks = [t["peak"] for t in trials]
    return {
        "bust_count": sum(busts),
        "bust_rate": sum(busts) / len(trials),
        "avg_pnl": sum(pnls) / len(pnls),
        "min_pnl": min(pnls),
        "max_pnl": max(pnls),
        "avg_dd": sum(dds) / len(dds),
        "max_dd_overall": max(dds),
        "avg_resets": sum(resets) / len(resets),
        "avg_longest_session": sum(long_sess) / len(long_sess),
        "max_longest_session": max(long_sess),
        "avg_deepest_sdd": sum(deep_sdd) / len(deep_sdd),
        "max_deepest_sdd": max(deep_sdd),
        "avg_max_seq": sum(max_seqs) / len(max_seqs),
        "max_max_seq": max(max_seqs),
        "avg_peak": sum(peaks) / len(peaks),
    }


def run_mc():
    results = {}
    reps = {}
    for target in PROFIT_TARGETS:
        print(f"\n=== 利確 ${target} ===", flush=True)
        trials = []
        for t in range(N_TRIALS):
            r = simulate(target=target, seed=2000 + t, track_equity=(t == 0))
            trials.append(r)
            bust_str = f"YES@{r['bust_at']}" if r["bust"] else "NO"
            print(
                f"  T{t+1:2d}: PNL ${r['pnl']:+,.0f} / DD ${r['max_dd']:,.0f} / "
                f"bust={bust_str} / maxSEQ[{r['max_seq']}]=${r['max_seq_val']} / resets={r['resets']:,}",
                flush=True,
            )
            if t == 0:
                reps[target] = r
        results[target] = (trials, aggregate(trials))
    return results, reps


def render_html(results, reps):
    def color(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    rows = ""
    for tgt in PROFIT_TARGETS:
        trials, a = results[tgt]
        row_color = TARGET_COLORS[tgt]
        rows += f"""
<tr>
<td style="color:{row_color};font-weight:700">${tgt}</td>
<td>{a['bust_count']}/{N_TRIALS} ({a['bust_rate']*100:.0f}%)</td>
<td style="color:{color(a['avg_pnl'])}">${a['avg_pnl']:+,.0f}</td>
<td style="color:{color(a['min_pnl'])}">${a['min_pnl']:+,.0f}</td>
<td style="color:{color(a['max_pnl'])}">${a['max_pnl']:+,.0f}</td>
<td>${a['avg_dd']:,.0f}</td>
<td style="color:#fbbf24">${a['max_dd_overall']:,.0f}</td>
<td>{a['avg_resets']:,.0f}</td>
<td>SEQ[{a['max_max_seq']}]=${SEQ[min(a['max_max_seq'], SEQ_LEN-1)]:,}</td>
<td>${a['avg_peak']:,.0f}</td>
</tr>
"""

    trial_rows = ""
    for tgt in PROFIT_TARGETS:
        trials, _ = results[tgt]
        for t in trials:
            trial_rows += f"""
<tr>
<td style="color:{TARGET_COLORS[tgt]}">${tgt}</td>
<td>#{t['seed']}</td>
<td style="color:{color(t['pnl'])}">${t['pnl']:+,.0f}</td>
<td>${t['max_dd']:,.0f}</td>
<td style="color:{'#f87171' if t['bust'] else '#4ade80'}">{'YES@'+str(t['bust_at']) if t['bust'] else 'NO'}</td>
<td>SEQ[{t['max_seq']}]=${t['max_seq_val']:,}</td>
<td>{t['resets']:,}</td>
</tr>
"""

    seq_display = ", ".join(f"${v}" for v in SEQ)

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>新SEQ2 × 7T × Banker 52% × $30k 利確比較</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
* {{ box-sizing: border-box; margin:0; padding:0; }}
body {{ font-family: 'Noto Sans JP', sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color:white; min-height:100vh; padding:40px 20px; }}
.container {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:36px; font-weight:900; background:linear-gradient(135deg,#00c8ff 0%,#6bcf8f 100%); -webkit-background-clip:text; background-clip:text; color:transparent; margin-bottom:8px; }}
.sub {{ color:#a0a0c0; margin-bottom:30px; }}
h2 {{ color:#00c8ff; font-size:22px; margin:30px 0 15px; border-left:4px solid #00c8ff; padding-left:12px; }}
table {{ width:100%; border-collapse:collapse; background:rgba(255,255,255,0.03); border-radius:8px; overflow:hidden; }}
th, td {{ padding:10px 12px; text-align:right; border-bottom:1px solid rgba(255,255,255,0.08); font-size:14px; }}
th {{ background:rgba(0,200,255,0.1); color:#00c8ff; font-weight:700; }}
td:first-child, th:first-child {{ text-align:left; }}
.seq-box {{ background:rgba(255,255,255,0.05); padding:15px; border-radius:8px; font-family:monospace; font-size:13px; color:#6bcf8f; margin:15px 0; word-wrap:break-word; }}
.params {{ background:rgba(0,200,255,0.06); padding:15px; border-radius:8px; margin:15px 0; font-size:14px; line-height:1.8; }}
.back {{ display:inline-block; margin-bottom:20px; color:#00c8ff; text-decoration:none; }}
.back:hover {{ text-decoration:underline; }}
</style></head><body>
<div class="container">
<a href="index.html" class="back">← index に戻る</a>
<h1>新SEQ2 × 7ターン × Banker 52% × $30k 元本</h1>
<div class="sub">利確 $30 vs $100 の比較 / 手数料補正なし (勝ち 0.95× で実損反映) / Bernoulli MC × {N_TRIALS} 試行</div>

<div class="params">
<b>SEQ ({SEQ_LEN} 段)</b>:<br>
<div class="seq-box">{seq_display}</div>
<b>条件</b>: B=52% (狙い打ち仮定) / 7ターン制 (SET_SIZE=7) / $10 base / 元本 $30,000 / 損切なし /
BET そのまま (1.0526× 補正なし) / 勝ち時 ×0.95 (5% rake 実損)<br>
<b>EV/bet</b> = 0.52 × 0.95 - 0.48 × 1.00 = <b style="color:#6bcf8f">+1.40%</b><br>
<b>MC</b>: Bernoulli({B_RATE}) × {N_HANDS:,} ハンド × {N_TRIALS} trial
</div>

<h2>📊 集計 ($30 vs $100)</h2>
<table>
<tr><th>利確</th><th>破綻</th><th>平均PNL</th><th>最悪PNL</th><th>最良PNL</th><th>平均DD</th><th>最大DD</th><th>平均リセット数</th><th>最大到達SEQ</th><th>平均Peak</th></tr>
{rows}
</table>

<h2>🎲 各試行の結果 (全 {N_TRIALS*2} trial)</h2>
<table>
<tr><th>利確</th><th>seed</th><th>PNL</th><th>最大DD</th><th>破綻</th><th>最大到達SEQ</th><th>リセット数</th></tr>
{trial_rows}
</table>

<div style="margin-top:30px; padding:20px; background:rgba(0,200,255,0.06); border-radius:8px; font-size:14px; line-height:1.7;">
<b style="color:#00c8ff">読み方</b>:<br>
・<b>破綻</b>: $30k 元本が尽きて次の BET が打てなくなった試行数 / 全 {N_TRIALS} 試行<br>
・<b>最大DD</b>: ピーク残高からの最大下落幅 (全試行の最悪値)<br>
・<b>平均リセット数</b>: 利確達成でSEQリセットした回数の平均<br>
・<b>最大到達SEQ</b>: 全試行で最も深く進んだ SEQ インデックスとその額
</div>
</div></body></html>"""


def main():
    print(f"=== 新SEQ2 × 7T × Banker 52% × $30k 元本 (手数料補正なし) ===", flush=True)
    print(f"SEQ: {SEQ}", flush=True)
    print(f"SEQ_LEN={SEQ_LEN} / BANKROLL=${BANKROLL:,} / 利確 {PROFIT_TARGETS}", flush=True)
    print(f"N_TRIALS={N_TRIALS} / N_HANDS={N_HANDS:,}/trial", flush=True)
    print(f"EV/bet = {B_RATE:.2f} × {WIN_FACTOR:.2f} - {1-B_RATE:.2f} × 1.00 = {(B_RATE*WIN_FACTOR - (1-B_RATE)):+.4f}", flush=True)

    results, reps = run_mc()

    print("\n=== 集計 ===", flush=True)
    for tgt in PROFIT_TARGETS:
        trials, a = results[tgt]
        print(f"\n利確 ${tgt}:", flush=True)
        print(f"  破綻 {a['bust_count']}/{N_TRIALS} ({a['bust_rate']*100:.0f}%)", flush=True)
        print(f"  PNL 平均 ${a['avg_pnl']:+,.0f} / 最悪 ${a['min_pnl']:+,.0f} / 最良 ${a['max_pnl']:+,.0f}", flush=True)
        print(f"  DD 平均 ${a['avg_dd']:,.0f} / 最大 ${a['max_dd_overall']:,.0f}", flush=True)
        print(f"  リセット 平均 {a['avg_resets']:,.0f} / 最大到達 SEQ[{a['max_max_seq']}]=${SEQ[min(a['max_max_seq'], SEQ_LEN-1)]:,}", flush=True)

    html = render_html(results, reps)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
