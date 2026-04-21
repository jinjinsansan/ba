"""SEQ × 元本スケールスキャン — B=51.05% で生き残るに必要な元本を特定

5 SEQ × 6 bankrolls × 2 B_rates × 20 trial = 1200 sims
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "seq_bankroll_scan.html"

SEQS = {
    "A": {
        "label": "新SEQ (SEQ_COUNTER)",
        "seq": [1, 3, 5, 7, 10, 13, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 145, 160, 175, 190, 205, 220, 235, 250, 265, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500],
        "color": "#fbbf24",
    },
    "B": {
        "label": "旧SEQ",
        "seq": [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142, 148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250],
        "color": "#60a5fa",
    },
    "C": {
        "label": "指数1.30x",
        "seq": [1, 2, 3, 4, 5, 7, 9, 12, 15, 20, 26, 34, 44, 57, 74, 96, 125, 163, 212, 275],
        "color": "#a78bfa",
    },
    "D": {
        "label": "指数1.44x",
        "seq": [1, 2, 3, 4, 6, 9, 13, 19, 27, 39, 56, 81, 117, 168, 242, 348, 500],
        "color": "#4ade80",
    },
    "E": {
        "label": "新SEQ2 (÷10)",
        "seq": [1, 2, 3, 4, 5, 7, 9, 11, 14, 17, 20, 25, 30, 35, 43, 51, 59, 70, 81, 94, 109, 126, 144, 164, 187, 215, 245, 280],
        "color": "#f87171",
    },
}

BANKROLLS = [5000, 10000, 20000, 50000, 100000, 200000]
B_RATES = [0.5105, 0.5200]
PROFIT_TARGET = 10
N_HANDS = 1_723_343
N_TRIALS = 20
COMMISSION = 0.05
WIN_FACTOR = 1.0 - COMMISSION
SET_SIZE = 7


def simulate(seq, bankroll, b_rate, seed):
    rng = np.random.default_rng(seed)
    outcomes = rng.random(N_HANDS) < b_rate
    seq_len = len(seq)

    balance = float(bankroll)
    peak = balance
    max_dd = 0.0
    bust = False
    bust_at = None
    below_start = False  # 一度でも元本割れしたか

    seq_idx = 0
    max_seq = 0
    overshoot = 0
    turn_in_set = 0
    wins_in_set = 0
    session_pnl = 0.0

    bets = 0
    wins = 0

    for i in range(N_HANDS):
        seq_val = seq[seq_idx if seq_idx < seq_len else seq_len - 1]
        bet = seq_val

        if bet > balance:
            bust = True
            bust_at = bets + 1
            break

        bets += 1
        if outcomes[i]:
            delta = +WIN_FACTOR * seq_val
            wins += 1
            wins_in_set += 1
        else:
            delta = -seq_val

        balance += delta
        session_pnl += delta

        if balance > peak:
            peak = balance
        if balance < bankroll:
            below_start = True
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd

        if session_pnl >= PROFIT_TARGET:
            seq_idx = 0
            overshoot = 0
            turn_in_set = 0
            wins_in_set = 0
            session_pnl = 0.0
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

    return {
        "bets": bets,
        "balance": balance,
        "pnl": balance - bankroll,
        "max_dd": max_dd,
        "bust": bust,
        "bust_at": bust_at,
        "below_start": below_start,
        "max_seq": max_seq,
    }


def run_all():
    results = {}  # (seq_key, bankroll, b_rate) -> agg
    total = len(SEQS) * len(BANKROLLS) * len(B_RATES)
    cnt = 0
    for seq_key, s in SEQS.items():
        for bankroll in BANKROLLS:
            for b_rate in B_RATES:
                cnt += 1
                trials = []
                for t in range(N_TRIALS):
                    r = simulate(s["seq"], bankroll, b_rate, seed=4000 + t)
                    trials.append(r)
                pnls = [t["pnl"] for t in trials]
                dds = [t["max_dd"] for t in trials]
                busts = [t["bust"] for t in trials]
                below = [t["below_start"] for t in trials]
                agg = {
                    "bust_count": sum(busts),
                    "bust_rate": sum(busts) / N_TRIALS,
                    "below_start_count": sum(below),
                    "avg_pnl": float(np.mean(pnls)),
                    "median_pnl": float(np.median(pnls)),
                    "min_pnl": float(np.min(pnls)),
                    "max_pnl": float(np.max(pnls)),
                    "avg_dd": float(np.mean(dds)),
                    "max_dd_overall": float(np.max(dds)),
                }
                results[(seq_key, bankroll, b_rate)] = agg
                print(
                    f"[{cnt:3d}/{total}] SEQ={seq_key} BR=${bankroll:,} B={b_rate*100:.2f}% | "
                    f"bust {agg['bust_count']:2d}/{N_TRIALS} | "
                    f"avgPNL ${agg['avg_pnl']:+,.0f} | "
                    f"avgDD ${agg['avg_dd']:,.0f}",
                    flush=True,
                )
    return results


def render_html(results):
    def bust_color(rate):
        if rate == 0: return "#4ade80"
        if rate < 0.1: return "#fbbf24"
        if rate < 0.5: return "#fb923c"
        return "#f87171"

    def pnl_color(pnl):
        return "#4ade80" if pnl > 0 else "#f87171" if pnl < 0 else "#cbd5e1"

    tables = ""
    for b_rate in B_RATES:
        b_label = f"{b_rate*100:.2f}%"
        bust_label = "実データ" if b_rate == 0.5105 else "狙い打ち"
        header_br = "".join(f"<th>${br:,}</th>" for br in BANKROLLS)
        rows = ""
        for sk, s in SEQS.items():
            row = f'<tr><td style="color:{s["color"]};font-weight:700">{sk}: {s["label"]}</td>'
            for br in BANKROLLS:
                agg = results[(sk, br, b_rate)]
                bc = bust_color(agg["bust_rate"])
                pc = pnl_color(agg["avg_pnl"])
                row += f'<td><b style="color:{bc}">{agg["bust_count"]}/{N_TRIALS}</b><br><span style="color:{pc};font-size:12px">${agg["avg_pnl"]:+,.0f}</span></td>'
            row += "</tr>"
            rows += row

        tables += f"""
<h2>B={b_label} ({bust_label})</h2>
<table>
<tr><th>SEQ \\ 元本</th>{header_br}</tr>
{rows}
</table>
<div style="font-size:12px;color:#a0a0c0;margin:5px 0 20px">
上段: 破綻数 / {N_TRIALS} (緑=0破綻 / 黄=少数 / 橙=過半数 / 赤=全滅) / 下段: 平均PNL
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>SEQ × 元本スケールスキャン</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:'Noto Sans JP',sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:white;min-height:100vh;padding:40px 20px }}
.container {{ max-width:1400px;margin:0 auto }}
h1 {{ font-size:32px;font-weight:900;background:linear-gradient(135deg,#00c8ff 0%,#6bcf8f 100%);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:8px }}
.sub {{ color:#a0a0c0;margin-bottom:30px }}
h2 {{ color:#00c8ff;font-size:22px;margin:25px 0 15px;border-left:4px solid #00c8ff;padding-left:12px }}
table {{ width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:8px;overflow:hidden;font-size:14px }}
th,td {{ padding:12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.08) }}
th {{ background:rgba(0,200,255,0.1);color:#00c8ff;font-weight:700 }}
td:first-child,th:first-child {{ text-align:left }}
.params {{ background:rgba(0,200,255,0.06);padding:15px;border-radius:8px;margin:15px 0;font-size:14px;line-height:1.7 }}
.back {{ display:inline-block;margin-bottom:20px;color:#00c8ff;text-decoration:none }}
.back:hover {{ text-decoration:underline }}
</style></head><body>
<div class="container">
<a href="index.html" class="back">← index に戻る</a>
<h1>SEQ × 元本スケールスキャン</h1>
<div class="sub">5 SEQ × 6 bankrolls × 2 B_rates × {N_TRIALS} trial = {5*6*2*N_TRIALS} sims / 手数料補正なし / 7T</div>

<div class="params">
<b>狙い</b>: 各 SEQ が B=51.05% (実データ) で生き残るに最低いくら元本が必要か?<br>
<b>条件</b>: base $1 統一 / 利確 $10 / BET そのまま / 勝ち 0.95× / 7ターン制 / N_TRIALS={N_TRIALS} / seed共有
</div>

{tables}

<div style="margin-top:30px;padding:20px;background:rgba(0,200,255,0.06);border-radius:8px;font-size:14px;line-height:1.7">
<b style="color:#00c8ff">読み方</b>:<br>
・<b>破綻数</b>: 20 試行中、元本が尽きて BET 不能になった数<br>
・<b>平均PNL</b>: 元本からの純損益 ($ — 破綻すれば -元本 相当の損失が記録される)<br>
・<b>B=51.05%</b>: 実データ勝率 (フィルタなし)、負け戦略<br>
・<b>B=52%</b>: 狙い打ちできた場合、+1.4% EV の勝ち戦略<br>
・<b>破綻 0/{N_TRIALS}</b> = 緑、<b>全滅 {N_TRIALS}/{N_TRIALS}</b> = 赤
</div>
</div></body></html>"""


def main():
    print(f"=== SEQ × 元本スケールスキャン ===", flush=True)
    print(f"SEQs={list(SEQS.keys())} / Bankrolls={BANKROLLS} / B={B_RATES}", flush=True)
    print(f"{len(SEQS)*len(BANKROLLS)*len(B_RATES)} 条件 × {N_TRIALS} trial = {len(SEQS)*len(BANKROLLS)*len(B_RATES)*N_TRIALS} sims", flush=True)
    print(f"PROFIT_TARGET=${PROFIT_TARGET} / N_HANDS={N_HANDS:,}", flush=True)

    results = run_all()

    print("\n\n=== サマリ: 破綻率 (B=51.05% / 実データ) ===", flush=True)
    for sk in SEQS:
        row = f"  {sk}: "
        for br in BANKROLLS:
            agg = results[(sk, br, 0.5105)]
            row += f"${br//1000}k→{agg['bust_count']}/{N_TRIALS} "
        print(row, flush=True)

    print("\n=== サマリ: 破綻率 (B=52% / 狙い打ち) ===", flush=True)
    for sk in SEQS:
        row = f"  {sk}: "
        for br in BANKROLLS:
            agg = results[(sk, br, 0.52)]
            row += f"${br//1000}k→{agg['bust_count']}/{N_TRIALS} "
        print(row, flush=True)

    html = render_html(results)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
