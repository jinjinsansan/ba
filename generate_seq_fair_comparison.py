"""SEQ 5種類の公平比較 — 同一条件 (base $1, 元本$5k, 手数料補正なし)

全 SEQ を base $1 に正規化 (E は ÷10):
- A: 新SEQ (SEQ_COUNTER) — max $500, 43要素
- B: 旧SEQ — max $250, 48要素
- C: 指数1.30x — max $275, 20要素
- D: 指数1.44x — max $500, 17要素
- E: 新SEQ2 (user, ÷10) — max $280, 28要素

条件:
- 7ターン制 (SET_SIZE=7)
- BET = seq_val (手数料補正 1.0526x なし)
- 勝ち delta = +0.95 × seq_val (5% rake 実損)
- 負け delta = -seq_val
- 元本 $5,000 / 損切なし / 利確$3 & $10
- B = 51.05% (実データ) / 52.00% (狙い打ち) 両方
- N_TRIALS=30 / N_HANDS=1,723,343 / seed共有
"""
from __future__ import annotations
from pathlib import Path

import numpy as np

OUT_HTML = Path(__file__).parent / "report" / "seq_fair_comparison.html"

SEQS = {
    "A": {
        "label": "新SEQ (SEQ_COUNTER)",
        "seq": [1, 3, 5, 7, 10, 13, 16, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 145, 160, 175, 190, 205, 220, 235, 250, 265, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500],
        "desc": "43要素 / max $500 / 平均1.25x成長",
        "color": "#fbbf24",
    },
    "B": {
        "label": "旧SEQ",
        "seq": [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142, 148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250],
        "desc": "48要素 / max $250 / 平均1.15x成長",
        "color": "#60a5fa",
    },
    "C": {
        "label": "指数1.30x圧縮",
        "seq": [1, 2, 3, 4, 5, 7, 9, 12, 15, 20, 26, 34, 44, 57, 74, 96, 125, 163, 212, 275],
        "desc": "20要素 / max $275 / 指数1.30x",
        "color": "#a78bfa",
    },
    "D": {
        "label": "指数1.44x理論最適",
        "seq": [1, 2, 3, 4, 6, 9, 13, 19, 27, 39, 56, 81, 117, 168, 242, 348, 500],
        "desc": "17要素 / max $500 / 指数1.44x (4W3L recovery保証)",
        "color": "#4ade80",
    },
    "E": {
        "label": "新SEQ2 (user, ÷10 正規化)",
        "seq": [1, 2, 3, 4, 5, 7, 9, 11, 14, 17, 20, 25, 30, 35, 43, 51, 59, 70, 81, 94, 109, 126, 144, 164, 187, 215, 245, 280],
        "desc": "28要素 / max $280 / ÷10 正規化",
        "color": "#f87171",
    },
}

B_RATES = [0.5105, 0.5200]
PROFIT_TARGETS = [3, 10]
BANKROLL = 5000
N_HANDS = 1_723_343
N_TRIALS = 30
COMMISSION = 0.05
WIN_FACTOR = 1.0 - COMMISSION  # 0.95
SET_SIZE = 7


def simulate(seq, b_rate, target, seed):
    """単一 trial。seed 共有で全 SEQ/rate/target 間の分散を揃える。"""
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
        dd = peak - balance
        if dd > max_dd:
            max_dd = dd

        # 利確リセット
        if session_pnl >= target:
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

    return {
        "bets": bets,
        "wins": wins,
        "sets": sets,
        "resets": resets,
        "max_seq": max_seq,
        "balance": balance,
        "pnl": balance - BANKROLL,
        "peak": peak,
        "max_dd": max_dd,
        "bust": bust,
        "bust_at": bust_at,
    }


def aggregate(trials):
    pnls = [t["pnl"] for t in trials]
    dds = [t["max_dd"] for t in trials]
    busts = [t["bust"] for t in trials]
    peaks = [t["peak"] for t in trials]
    max_seqs = [t["max_seq"] for t in trials]
    resets = [t["resets"] for t in trials]
    return {
        "n": len(trials),
        "bust_count": sum(busts),
        "bust_rate": sum(busts) / len(trials),
        "avg_pnl": float(np.mean(pnls)),
        "median_pnl": float(np.median(pnls)),
        "min_pnl": float(np.min(pnls)),
        "max_pnl": float(np.max(pnls)),
        "std_pnl": float(np.std(pnls)),
        "avg_dd": float(np.mean(dds)),
        "max_dd_overall": float(np.max(dds)),
        "avg_resets": float(np.mean(resets)),
        "avg_max_seq": float(np.mean(max_seqs)),
        "max_max_seq": int(np.max(max_seqs)),
        "avg_peak": float(np.mean(peaks)),
    }


def run_all():
    results = {}  # (seq_key, b_rate, target) -> (trials, agg)
    total = len(SEQS) * len(B_RATES) * len(PROFIT_TARGETS)
    cnt = 0
    for seq_key, seq_data in SEQS.items():
        for b_rate in B_RATES:
            for target in PROFIT_TARGETS:
                cnt += 1
                print(f"\n[{cnt}/{total}] SEQ={seq_key} B={b_rate*100:.2f}% TG=${target}", flush=True)
                trials = []
                for t in range(N_TRIALS):
                    r = simulate(seq_data["seq"], b_rate, target, seed=3000 + t)
                    trials.append(r)
                agg = aggregate(trials)
                results[(seq_key, b_rate, target)] = (trials, agg)
                print(
                    f"  破綻 {agg['bust_count']}/{N_TRIALS} | "
                    f"avgPNL ${agg['avg_pnl']:+,.2f} | "
                    f"avgDD ${agg['avg_dd']:,.2f} | "
                    f"medPNL ${agg['median_pnl']:+,.2f}",
                    flush=True,
                )
    return results


def rank_seqs(results):
    """目的別に SEQ をランキング"""
    rankings = {}
    # 各条件での PNL / DD ランキング
    conditions = [(b, t) for b in B_RATES for t in PROFIT_TARGETS]
    for cond in conditions:
        b, t = cond
        pnls = {sk: results[(sk, b, t)][1]["avg_pnl"] for sk in SEQS}
        dds = {sk: results[(sk, b, t)][1]["avg_dd"] for sk in SEQS}
        busts = {sk: results[(sk, b, t)][1]["bust_rate"] for sk in SEQS}
        rankings[cond] = {
            "pnl_rank": sorted(pnls, key=pnls.get, reverse=True),
            "dd_rank": sorted(dds, key=dds.get),  # 小さい順
            "bust_rank": sorted(busts, key=busts.get),  # 少ない順
            "pnls": pnls,
            "dds": dds,
            "busts": busts,
        }
    return rankings


def render_html(results, rankings):
    def color_pnl(pnl):
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    rows_by_cond = ""
    for b in B_RATES:
        for tg in PROFIT_TARGETS:
            r = rankings[(b, tg)]
            rank_list = ""
            for i, sk in enumerate(r["pnl_rank"]):
                seq = SEQS[sk]
                agg = results[(sk, b, tg)][1]
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
                rank_list += f"""
<tr>
<td>{medal} {i+1}</td>
<td style="color:{seq['color']};font-weight:700">{sk}: {seq['label']}</td>
<td>{agg['bust_count']}/{N_TRIALS}</td>
<td style="color:{color_pnl(agg['avg_pnl'])}">${agg['avg_pnl']:+,.2f}</td>
<td style="color:{color_pnl(agg['median_pnl'])}">${agg['median_pnl']:+,.2f}</td>
<td style="color:{color_pnl(agg['min_pnl'])}">${agg['min_pnl']:+,.2f}</td>
<td style="color:{color_pnl(agg['max_pnl'])}">${agg['max_pnl']:+,.2f}</td>
<td>${agg['avg_dd']:,.2f}</td>
<td>${agg['max_dd_overall']:,.2f}</td>
<td>{agg['avg_resets']:,.0f}</td>
<td>[{agg['max_max_seq']}]</td>
</tr>
"""
            rows_by_cond += f"""
<h3>B={b*100:.2f}% / 利確 ${tg}</h3>
<table>
<tr><th>順位</th><th>SEQ</th><th>破綻</th><th>avgPNL</th><th>medPNL</th><th>minPNL</th><th>maxPNL</th><th>avgDD</th><th>maxDD</th><th>avgResets</th><th>最大到達SEQ</th></tr>
{rank_list}
</table>
"""

    # SEQ 一覧
    seq_list = ""
    for sk, s in SEQS.items():
        seq_str = ", ".join(str(v) for v in s["seq"])
        seq_list += f"""
<div style="margin:15px 0;padding:15px;background:rgba(255,255,255,0.04);border-left:4px solid {s['color']};border-radius:4px">
<b style="color:{s['color']}">{sk}: {s['label']}</b> ({s['desc']})<br>
<div style="font-family:monospace;font-size:12px;color:#a0a0c0;margin-top:6px;word-wrap:break-word">[{seq_str}]</div>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>SEQ 5種 公平比較 — B=51.05% vs 52% / 利確$3 vs $10 / 元本$5k</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
* {{ box-sizing:border-box;margin:0;padding:0 }}
body {{ font-family:'Noto Sans JP',sans-serif;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);color:white;min-height:100vh;padding:40px 20px }}
.container {{ max-width:1400px;margin:0 auto }}
h1 {{ font-size:32px;font-weight:900;background:linear-gradient(135deg,#00c8ff 0%,#6bcf8f 100%);-webkit-background-clip:text;background-clip:text;color:transparent;margin-bottom:8px }}
.sub {{ color:#a0a0c0;margin-bottom:30px }}
h2 {{ color:#00c8ff;font-size:22px;margin:30px 0 15px;border-left:4px solid #00c8ff;padding-left:12px }}
h3 {{ color:#fbbf24;font-size:18px;margin:25px 0 10px }}
table {{ width:100%;border-collapse:collapse;background:rgba(255,255,255,0.03);border-radius:8px;overflow:hidden;font-size:13px }}
th,td {{ padding:8px 10px;text-align:right;border-bottom:1px solid rgba(255,255,255,0.08) }}
th {{ background:rgba(0,200,255,0.1);color:#00c8ff;font-weight:700 }}
td:nth-child(1),td:nth-child(2),th:nth-child(1),th:nth-child(2) {{ text-align:left }}
.params {{ background:rgba(0,200,255,0.06);padding:15px;border-radius:8px;margin:15px 0;font-size:14px;line-height:1.7 }}
.back {{ display:inline-block;margin-bottom:20px;color:#00c8ff;text-decoration:none }}
.back:hover {{ text-decoration:underline }}
</style></head><body>
<div class="container">
<a href="index.html" class="back">← index に戻る</a>
<h1>SEQ 5種 公平比較</h1>
<div class="sub">base $1 統一 / 元本 $5,000 / 手数料補正なし (勝ち 0.95×) / B=51.05% vs 52% / 利確 $3 vs $10 / N_TRIALS={N_TRIALS} seed共有</div>

<div class="params">
<b>共通条件</b>:<br>
・7ターン制 (SET_SIZE=7)<br>
・BET = seq_val (UPSIZE なし)<br>
・勝ち delta = +0.95 × seq_val / 負け delta = -seq_val<br>
・EV/bet at B=52%: +1.40% / at B=51.05%: -0.46%<br>
・MC: Bernoulli × {N_HANDS:,} ハンド × {N_TRIALS} trial (全 SEQ 間 seed 共有で分散揃え)
</div>

<h2>📋 比較対象 SEQ 一覧 (base $1 正規化)</h2>
{seq_list}

<h2>🏆 結果ランキング (PNL 降順)</h2>
{rows_by_cond}

<div style="margin-top:30px;padding:20px;background:rgba(0,200,255,0.06);border-radius:8px;font-size:14px;line-height:1.7">
<b style="color:#00c8ff">読み方</b>:<br>
・<b>B=51.05%</b> は実データの Banker 勝率 (フィルタなしの基準)<br>
・<b>B=52%</b> は「狙い撃ちできた場合」の仮定値<br>
・B=51.05% で +PNL 出せる SEQ が本当に強い (実データ耐性)<br>
・B=52% での PNL は上振れ期待値<br>
・avgDD は平均ドローダウン、maxDD は全試行の最悪ケース
</div>

</div></body></html>"""


def main():
    print(f"=== SEQ 5種 公平比較 — 元本${BANKROLL:,} / base $1 / 手数料補正なし ===", flush=True)
    print(f"N_TRIALS={N_TRIALS} / N_HANDS={N_HANDS:,}", flush=True)
    print(f"20 条件 × {N_TRIALS} trial = {20*N_TRIALS} sims", flush=True)

    results = run_all()
    rankings = rank_seqs(results)

    print("\n\n=== 総合サマリ (B=52% / 利確$3) ===", flush=True)
    r = rankings[(0.52, 3)]
    for i, sk in enumerate(r["pnl_rank"]):
        agg = results[(sk, 0.52, 3)][1]
        print(f"  {i+1}. {sk}: avgPNL ${agg['avg_pnl']:+,.2f}, bust {agg['bust_count']}/{N_TRIALS}, DD ${agg['avg_dd']:,.2f}", flush=True)

    print("\n=== 総合サマリ (B=51.05% / 利確$3) ===", flush=True)
    r = rankings[(0.5105, 3)]
    for i, sk in enumerate(r["pnl_rank"]):
        agg = results[(sk, 0.5105, 3)][1]
        print(f"  {i+1}. {sk}: avgPNL ${agg['avg_pnl']:+,.2f}, bust {agg['bust_count']}/{N_TRIALS}, DD ${agg['avg_dd']:,.2f}", flush=True)

    html = render_html(results, rankings)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
