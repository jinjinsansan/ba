"""新SEQ2 × 7ターン × Banker only × B=52% — 利確$30/$50/$100 比較 / 元本$100k

手数料補正なし版:
- BET 額 = seq_val (そのまま)
- 勝ち時 delta = +0.95 × seq_val (Banker 5% rake を実損として反映)
- 負け時 delta = -seq_val
- EV/bet = 0.52 × 0.95 - 0.48 × 1.00 = +0.014 (+1.4%)

目的: この SEQ で $100k 元本が耐えるか / 最大DD / PNL を $30 vs $50 vs $100 利確で比較
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "seq2_banker_52pct_30k.html"

SEQ = [
    1, 5, 10, 20, 30, 40, 50,
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
PROFIT_TARGETS = [30, 50, 100]
B_RATE = 0.52
BANKROLL = 100000
N_HANDS = 1_723_343
N_TRIALS = 20
COMMISSION = 0.05
WIN_FACTOR = 1.0 - COMMISSION  # 勝ち時 0.95×
SET_SIZE = 7
SNAPSHOT_EVERY = 5000
TARGET_COLORS = {30: "#4ade80", 50: "#fbbf24", 100: "#f87171"}


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
    def color_pnl(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#8a96a8")

    def best_target():
        """最も平均PNLが高い target を選ぶ"""
        return max(PROFIT_TARGETS, key=lambda t: results[t][1]["avg_pnl"])

    # 全体 KPI (全 target 合算)
    all_trials = [t for tgt in PROFIT_TARGETS for t in results[tgt][0]]
    total_bust = sum(1 for t in all_trials if t["bust"])
    all_pnls = [t["pnl"] for t in all_trials]
    all_dds = [t["max_dd"] for t in all_trials]
    avg_pnl_all = sum(all_pnls) / len(all_pnls)
    max_dd_all = max(all_dds)
    best_tgt = best_target()
    best_avg = results[best_tgt][1]["avg_pnl"]

    # 集計テーブル
    rows = ""
    for tgt in PROFIT_TARGETS:
        trials, a = results[tgt]
        row_color = TARGET_COLORS[tgt]
        bust_cls = ' style="color:#f87171;font-weight:bold"' if a["bust_count"] > 0 else ' style="color:#4ade80"'
        rows += f"""
<tr>
<td style="color:{row_color};font-weight:bold">${tgt} 利確</td>
<td{bust_cls}>{a['bust_count']} / {N_TRIALS}</td>
<td style="color:{color_pnl(a['avg_pnl'])};font-weight:bold">${a['avg_pnl']:+,.0f}</td>
<td style="color:{color_pnl(a['min_pnl'])}">${a['min_pnl']:+,.0f}</td>
<td style="color:{color_pnl(a['max_pnl'])}">${a['max_pnl']:+,.0f}</td>
<td>${a['avg_dd']:,.0f}</td>
<td style="color:#fbbf24">${a['max_dd_overall']:,.0f}</td>
<td>{a['avg_resets']:,.0f}</td>
<td>SEQ[{a['max_max_seq']}]=${SEQ[min(a['max_max_seq'], SEQ_LEN-1)]:,}</td>
</tr>
"""

    # trial 詳細
    trial_rows = ""
    for tgt in PROFIT_TARGETS:
        trials, _ = results[tgt]
        for t in trials:
            bust_html = f'<span style="color:#f87171;font-weight:bold">破綻 @{t["bust_at"]:,}</span>' if t["bust"] else '<span style="color:#4ade80">✓ 生存</span>'
            trial_rows += f"""
<tr>
<td style="color:{TARGET_COLORS[tgt]};font-weight:bold">${tgt}</td>
<td style="font-family:monospace;color:#8a96a8">#{t['seed']}</td>
<td style="color:{color_pnl(t['pnl'])};font-weight:bold">${t['pnl']:+,.0f}</td>
<td>${t['max_dd']:,.0f}</td>
<td style="text-align:center">{bust_html}</td>
<td>SEQ[{t['max_seq']}]=${t['max_seq_val']:,}</td>
<td>{t['resets']:,}</td>
</tr>
"""

    seq_display = ", ".join(f"${v:,}" for v in SEQ)

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>AI. 新SEQ2 × 7T × Banker 52% × $100k 元本 — 利確比較</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Segoe UI", "Noto Sans JP", sans-serif; background: #0f1419; color: #e0e6ed; margin: 0; padding: 24px; line-height: 1.5; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #ffd700; font-size: 28px; border-bottom: 2px solid #ffd700; padding-bottom: 8px; }}
h2 {{ color: #c084fc; margin-top: 32px; font-size: 20px; }}
.nav {{ margin: 16px 0 24px; }}
.nav a {{ display: inline-block; margin-right: 12px; padding: 8px 16px; background: #1a2332; color: #6dd5ed; text-decoration: none; border-radius: 4px; border: 1px solid #2a3441; font-size: 13px; }}
.nav a:hover {{ border-color: #c084fc; }}
.banner {{ background: #2a1a3a; border-left: 5px solid #c084fc; padding: 14px 18px; margin: 16px 0; font-size: 14px; border-radius: 4px; line-height: 1.8; }}
.banner strong {{ color: #c084fc; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
.card {{ background: #1a2332; padding: 14px; border-radius: 4px; border-left: 4px solid #6dd5ed; }}
.card .label {{ font-size: 11px; color: #8a96a8; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .value {{ font-size: 22px; font-weight: bold; color: #ffd700; margin-top: 4px; }}
.card .sub {{ font-size: 11px; color: #8a96a8; margin-top: 2px; }}
.card.profit {{ border-left-color: #4ade80; }}
.card.profit .value {{ color: #4ade80; }}
.card.bankrupt {{ border-left-color: #f87171; }}
.card.bankrupt .value {{ color: #f87171; }}
.card.dd {{ border-left-color: #fbbf24; }}
.card.dd .value {{ color: #fbbf24; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 16px 0; background: #1a2332; border-radius: 4px; overflow: hidden; }}
table th {{ background: #0f1419; color: #c084fc; padding: 10px 8px; text-align: right; border-bottom: 2px solid #2a3441; font-weight: 600; }}
table th:first-child, table td:first-child {{ text-align: left; }}
table td {{ padding: 8px; text-align: right; border-bottom: 1px solid #2a3441; }}
.seq-box {{ background: #0f1419; padding: 12px; border-radius: 4px; font-family: monospace; font-size: 12px; color: #6dd5ed; word-wrap: break-word; margin: 8px 0; }}
.note {{ background: #1a2332; border-left: 4px solid #6dd5ed; padding: 12px 16px; margin: 20px 0; font-size: 13px; color: #b8c5d6; border-radius: 4px; line-height: 1.7; }}
.note b {{ color: #6dd5ed; }}
</style></head><body>
<div class="container">
<h1>AI. 新SEQ2 × 7ターン × Banker 52% × 元本 $100,000</h1>

<div class="nav">
<a href="index.html">← レポートTOP</a>
<a href="seq_fair_comparison.html">AJ. 5 SEQ 公平比較</a>
<a href="seq_bankroll_scan.html">AK. 利確額スキャン</a>
</div>

<div class="banner">
<strong>📊 新 SEQ2 ($1 起点, 30 段, max $2,800) 単独バックテスト</strong><br>
Banker のみ BET / 手数料補正なし (勝ち時 ×0.95 で実損反映) / 利確 $30 vs $50 vs $100 を比較。<br>
<strong>$100k 元本が耐えられるか、どの利確が最適か?</strong>
</div>

<h2>🎯 全体サマリー</h2>
<div class="summary">
  <div class="card bankrupt"><div class="label">総破綻数</div><div class="value">{total_bust} / {N_TRIALS * len(PROFIT_TARGETS)}</div><div class="sub">全 {len(PROFIT_TARGETS)} 利確 × {N_TRIALS} trial</div></div>
  <div class="card profit"><div class="label">全試行 平均 PNL</div><div class="value">${avg_pnl_all:+,.0f}</div><div class="sub">最優秀 ${best_tgt} 利確: ${best_avg:+,.0f}</div></div>
  <div class="card dd"><div class="label">最大 DD (全試行中)</div><div class="value">${max_dd_all:,.0f}</div><div class="sub">元本比 {max_dd_all/BANKROLL*100:.1f}%</div></div>
  <div class="card"><div class="label">EV/bet (B=52%)</div><div class="value">+1.40%</div><div class="sub">0.52×0.95 − 0.48×1.00</div></div>
</div>

<h2>📋 前提条件 & SEQ</h2>
<div class="note">
<b>元本</b>: ${BANKROLL:,} / <b>勝率</b>: {B_RATE*100:.1f}% (Banker 狙い打ち仮定) / <b>ハンド数</b>: {N_HANDS:,} × {N_TRIALS} trial<br>
<b>ルール</b>: 7 ターン制 / BET = seq_val (補正なし) / 勝ち ×0.95 / 負け ×(−1) / 利確でリセット / 損切なし<br>
<b>SEQ ({SEQ_LEN} 段)</b>:
<div class="seq-box">{seq_display}</div>
</div>

<h2>💰 利確額別 集計</h2>
<table>
<thead>
<tr><th>利確</th><th>破綻</th><th>平均 PNL</th><th>最悪 PNL</th><th>最良 PNL</th><th>平均 DD</th><th>最大 DD</th><th>平均リセット</th><th>最大到達 SEQ</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>

<h2>🎲 試行別詳細 (全 {N_TRIALS * len(PROFIT_TARGETS)} trial)</h2>
<table>
<thead>
<tr><th>利確</th><th>seed</th><th>PNL</th><th>最大 DD</th><th>状態</th><th>最大到達 SEQ</th><th>リセット数</th></tr>
</thead>
<tbody>
{trial_rows}
</tbody>
</table>

<div class="note">
<b>📖 読み方</b><br>
・<b>破綻</b>: ${BANKROLL:,} 元本が尽きて次の BET が打てなくなった試行の数<br>
・<b>最大 DD</b>: ピーク残高からの最大下落幅 (ドローダウン)<br>
・<b>リセット数</b>: 利確達成で SEQ[0] に戻った回数 (多いほど高頻度小利確)<br>
・<b>最大到達 SEQ</b>: SEQ 配列で最も深く進んだインデックスとその BET 額
</div>
</div></body></html>"""


def main():
    print(f"=== 新SEQ2 × 7T × Banker 52% × ${BANKROLL:,} 元本 (手数料補正なし) ===", flush=True)
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
