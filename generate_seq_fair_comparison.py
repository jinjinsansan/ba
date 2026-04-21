"""SEQ 5種類の公平比較 — 同一条件 (base $1, 元本$5k, 手数料補正なし)

全 SEQ を base $1 起点で比較:
- A: 新SEQ (SEQ_COUNTER) — max $500, 43要素
- B: 旧SEQ — max $250, 48要素
- C: 指数1.30x — max $275, 20要素
- D: 指数1.44x — max $500, 17要素
- E: 新SEQ2 (user, $1 起点 / 30段 / max $2800)

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
        "label": "新SEQ2 (user, $1 起点)",
        "seq": [1, 5, 10, 20, 30, 40, 50, 70, 90, 110, 140, 170, 200, 250, 300, 350, 430, 510, 590, 700, 810, 940, 1090, 1260, 1440, 1640, 1870, 2150, 2450, 2800],
        "desc": "30要素 / max $2,800 / $1 起点",
        "color": "#f87171",
    },
}

B_RATES = [0.5105, 0.5200]
PROFIT_TARGETS = [30, 50, 100]
BANKROLL = 100000
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
        return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#8a96a8")

    # 全体 KPI (B=52% 前提の最優秀条件を提示)
    best_cond = max(
        [(b, t) for b in B_RATES for t in PROFIT_TARGETS],
        key=lambda ct: max(results[(sk, ct[0], ct[1])][1]["avg_pnl"] for sk in SEQS),
    )
    best_sk = max(SEQS, key=lambda sk: results[(sk, best_cond[0], best_cond[1])][1]["avg_pnl"])
    best_agg = results[(best_sk, best_cond[0], best_cond[1])][1]

    # B=51.05% での総破綻数 (実データでの生存性)
    busts_51 = sum(results[(sk, 0.5105, t)][1]["bust_count"] for sk in SEQS for t in PROFIT_TARGETS)
    total_51 = len(SEQS) * len(PROFIT_TARGETS) * N_TRIALS
    # B=52% での総破綻数
    busts_52 = sum(results[(sk, 0.52, t)][1]["bust_count"] for sk in SEQS for t in PROFIT_TARGETS)
    total_52 = len(SEQS) * len(PROFIT_TARGETS) * N_TRIALS

    # ランキング表
    rows_by_cond = ""
    for b in B_RATES:
        for tg in PROFIT_TARGETS:
            r = rankings[(b, tg)]
            rank_list = ""
            for i, sk in enumerate(r["pnl_rank"]):
                seq = SEQS[sk]
                agg = results[(sk, b, tg)][1]
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"  {i+1}"
                bust_cls = ' style="color:#f87171;font-weight:bold"' if agg["bust_count"] > 0 else ' style="color:#4ade80"'
                rank_list += f"""
<tr>
<td>{medal}</td>
<td style="color:{seq['color']};font-weight:bold">{sk}. {seq['label']}</td>
<td{bust_cls}>{agg['bust_count']} / {N_TRIALS}</td>
<td style="color:{color_pnl(agg['avg_pnl'])};font-weight:bold">${agg['avg_pnl']:+,.0f}</td>
<td style="color:{color_pnl(agg['median_pnl'])}">${agg['median_pnl']:+,.0f}</td>
<td style="color:{color_pnl(agg['min_pnl'])}">${agg['min_pnl']:+,.0f}</td>
<td style="color:{color_pnl(agg['max_pnl'])}">${agg['max_pnl']:+,.0f}</td>
<td>${agg['avg_dd']:,.0f}</td>
<td style="color:#fbbf24">${agg['max_dd_overall']:,.0f}</td>
<td>{agg['avg_resets']:,.0f}</td>
<td>[{agg['max_max_seq']}]</td>
</tr>
"""
            b_label = "実データ" if b == 0.5105 else "狙い打ち仮定"
            b_color = "#f87171" if b == 0.5105 else "#4ade80"
            rows_by_cond += f"""
<h3 style="color:{b_color}">B = {b*100:.2f}% ({b_label}) / 利確 ${tg}</h3>
<table>
<thead>
<tr><th>順位</th><th>SEQ</th><th>破綻</th><th>平均 PNL</th><th>中央値</th><th>最悪</th><th>最良</th><th>平均 DD</th><th>最大 DD</th><th>平均リセット</th><th>最大 SEQ</th></tr>
</thead>
<tbody>{rank_list}</tbody>
</table>
"""

    # SEQ 一覧
    seq_list = ""
    for sk, s in SEQS.items():
        seq_str = ", ".join(f"${v:,}" for v in s["seq"])
        seq_list += f"""
<div style="margin: 10px 0; padding: 12px 15px; background: #1a2332; border-left: 4px solid {s['color']}; border-radius: 4px">
<b style="color:{s['color']}">{sk}. {s['label']}</b> <span style="color:#8a96a8; font-size:12px">— {s['desc']}</span>
<div class="seq-box">[{seq_str}]</div>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>AJ. SEQ 5種 公平比較 — 元本 $100k / 利確 $30·$50·$100</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Segoe UI", "Noto Sans JP", sans-serif; background: #0f1419; color: #e0e6ed; margin: 0; padding: 24px; line-height: 1.5; }}
.container {{ max-width: 1300px; margin: 0 auto; }}
h1 {{ color: #ffd700; font-size: 28px; border-bottom: 2px solid #ffd700; padding-bottom: 8px; }}
h2 {{ color: #c084fc; margin-top: 32px; font-size: 20px; }}
h3 {{ color: #fbbf24; margin-top: 24px; font-size: 16px; }}
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
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 12px 0; background: #1a2332; border-radius: 4px; overflow: hidden; }}
table th {{ background: #0f1419; color: #c084fc; padding: 10px 8px; text-align: right; border-bottom: 2px solid #2a3441; font-weight: 600; }}
table th:nth-child(1), table th:nth-child(2), table td:nth-child(1), table td:nth-child(2) {{ text-align: left; }}
table td {{ padding: 8px; text-align: right; border-bottom: 1px solid #2a3441; }}
.seq-box {{ background: #0f1419; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 11px; color: #6dd5ed; word-wrap: break-word; margin: 6px 0; }}
.note {{ background: #1a2332; border-left: 4px solid #6dd5ed; padding: 12px 16px; margin: 20px 0; font-size: 13px; color: #b8c5d6; border-radius: 4px; line-height: 1.7; }}
.note b {{ color: #6dd5ed; }}
</style></head><body>
<div class="container">
<h1>AJ. SEQ 5種 公平比較 — 元本 $100,000</h1>

<div class="nav">
<a href="index.html">← レポートTOP</a>
<a href="seq2_banker_52pct_30k.html">AI. 新SEQ2 単独</a>
<a href="seq_bankroll_scan.html">AK. 利確額スキャン</a>
</div>

<div class="banner">
<strong>📊 SEQ 5 種を同条件で公平比較</strong><br>
全 SEQ とも base $1 (先頭ベット $1) / 元本 $100k / 利確 $30 vs $50 vs $100 / B=51.05% (実データ) vs B=52% (狙い打ち仮定)。<br>
<strong>実データで生き残れるか? 狙い打ちできた時はどの SEQ が最強か?</strong>
</div>

<h2>🎯 全体サマリー</h2>
<div class="summary">
  <div class="card profit"><div class="label">最優秀 avg PNL</div><div class="value">${best_agg['avg_pnl']:+,.0f}</div><div class="sub">{best_sk} @ B={best_cond[0]*100:.1f}% / ${best_cond[1]} 利確</div></div>
  <div class="card bankrupt"><div class="label">B=51.05% 破綻</div><div class="value">{busts_51} / {total_51}</div><div class="sub">実データ勝率 ({busts_51/total_51*100:.0f}% 破綻)</div></div>
  <div class="card profit"><div class="label">B=52% 破綻</div><div class="value">{busts_52} / {total_52}</div><div class="sub">狙い打ち仮定 ({busts_52/total_52*100:.0f}% 破綻)</div></div>
  <div class="card"><div class="label">MC 試行</div><div class="value">{N_TRIALS}</div><div class="sub">seed 共有 / 全 SEQ 同条件</div></div>
</div>

<h2>📋 比較対象 SEQ (先頭ベット $1 統一)</h2>
{seq_list}

<h2>📐 共通条件</h2>
<div class="note">
<b>元本</b>: ${BANKROLL:,} / <b>ハンド数</b>: {N_HANDS:,} / <b>試行</b>: {N_TRIALS} (seed 共有で分散揃え)<br>
<b>ルール</b>: 7 ターン制 / BET = seq_val (手数料補正なし) / 勝ち ×0.95 / 負け ×(−1) / 利確でリセット / 損切なし<br>
<b>EV/bet</b>: B=52% で +1.40% / B=51.05% で −0.46%
</div>

<h2>🏆 ランキング (avg PNL 降順)</h2>
{rows_by_cond}

<div class="note">
<b>📖 読み方</b><br>
・<b>B=51.05%</b> は Evolution 全ハンドの実データ Banker 勝率 — ここで +PNL 出せれば「実データ耐性」あり<br>
・<b>B=52%</b> は「Banker 出やすい局面をフィルタで狙い撃ちできた場合」の仮定値 — 上振れ期待<br>
・<b>平均 PNL</b> は {N_TRIALS} 試行の平均 / <b>中央値</b> は外れ値に強い指標<br>
・<b>最大 DD</b> は全試行中の最悪ドローダウン
</div>
</div></body></html>"""


def main():
    total_cond = len(B_RATES) * len(PROFIT_TARGETS) * len(SEQS)
    print(f"=== SEQ 5種 公平比較 — 元本${BANKROLL:,} / base $1 / 手数料補正なし ===", flush=True)
    print(f"N_TRIALS={N_TRIALS} / N_HANDS={N_HANDS:,}", flush=True)
    print(f"{total_cond} 条件 × {N_TRIALS} trial = {total_cond*N_TRIALS} sims", flush=True)

    results = run_all()
    rankings = rank_seqs(results)

    for b in B_RATES:
        b_label = "狙い打ち" if b == 0.52 else "実データ"
        for tg in PROFIT_TARGETS:
            print(f"\n=== 総合サマリ (B={b*100:.2f}% {b_label} / 利確 ${tg}) ===", flush=True)
            r = rankings[(b, tg)]
            for i, sk in enumerate(r["pnl_rank"]):
                agg = results[(sk, b, tg)][1]
                print(f"  {i+1}. {sk}: avgPNL ${agg['avg_pnl']:+,.0f}, bust {agg['bust_count']}/{N_TRIALS}, DD ${agg['avg_dd']:,.0f}", flush=True)

    html = render_html(results, rankings)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
