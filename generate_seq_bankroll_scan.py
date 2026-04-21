"""SEQ × 利確額スキャン — $100k 元本固定で 5 SEQ × 3 利確額 × 2 B_rate 測定

5 SEQ × 3 profit_targets × 2 B_rates × 20 trial = 600 sims
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
        "label": "新SEQ2 (user, $1 起点)",
        "seq": [1, 5, 10, 20, 30, 40, 50, 70, 90, 110, 140, 170, 200, 250, 300, 350, 430, 510, 590, 700, 810, 940, 1090, 1260, 1440, 1640, 1870, 2150, 2450, 2800],
        "color": "#f87171",
    },
}

BANKROLL = 100_000
B_RATES = [0.5105, 0.5200]
PROFIT_TARGETS = [30, 50, 100]
N_HANDS = 1_723_343
N_TRIALS = 20
COMMISSION = 0.05
WIN_FACTOR = 1.0 - COMMISSION
SET_SIZE = 7


def simulate(seq, target, b_rate, seed):
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
    resets = 0

    for i in range(N_HANDS):
        seq_val = seq[seq_idx if seq_idx < seq_len else seq_len - 1]
        if seq_val > balance:
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
                seq_idx = min(seq_idx + 1, seq_len - 1)
            else:
                seq_idx = max(seq_idx - diff, 0)
            if seq_idx > max_seq:
                max_seq = seq_idx
            overshoot = new_overshoot
            turn_in_set = 0
            wins_in_set = 0

    return {
        "bets": bets,
        "wins": wins,
        "win_rate": wins / bets if bets else 0,
        "resets": resets,
        "max_seq": max_seq,
        "max_seq_val": seq[min(max_seq, seq_len - 1)],
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
    resets = [t["resets"] for t in trials]
    return {
        "bust_count": sum(busts),
        "bust_rate": sum(busts) / len(trials),
        "avg_pnl": sum(pnls) / len(pnls),
        "min_pnl": min(pnls),
        "max_pnl": max(pnls),
        "avg_dd": sum(dds) / len(dds),
        "max_dd_overall": max(dds),
        "avg_resets": sum(resets) / len(resets),
    }


def run_all():
    results = {}
    conditions = [(sk, t, b) for sk in SEQS for t in PROFIT_TARGETS for b in B_RATES]
    total = len(conditions)
    for idx, (sk, t, b) in enumerate(conditions, 1):
        trials = [
            simulate(SEQS[sk]["seq"], target=t, b_rate=b, seed=3000 + trial)
            for trial in range(N_TRIALS)
        ]
        agg = aggregate(trials)
        results[(sk, t, b)] = (trials, agg)
        print(
            f"[{idx:3d}/{total}] SEQ={sk} TG=${t} B={b*100:.2f}% | "
            f"bust {agg['bust_count']:2d}/{N_TRIALS} | "
            f"avgPNL ${agg['avg_pnl']:+,.0f} | "
            f"avgDD ${agg['avg_dd']:,.0f}",
            flush=True,
        )
    return results


def color_pnl(pnl):
    return "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#8a96a8")


def render_html(results):
    # 全体 KPI
    all_aggs = list(results.values())
    b52_aggs = [(sk, t, results[(sk, t, 0.52)][1]) for sk in SEQS for t in PROFIT_TARGETS]
    b51_aggs = [(sk, t, results[(sk, t, 0.5105)][1]) for sk in SEQS for t in PROFIT_TARGETS]

    busts_51 = sum(a["bust_count"] for _, _, a in b51_aggs)
    busts_52 = sum(a["bust_count"] for _, _, a in b52_aggs)
    total_trials = N_TRIALS * len(SEQS) * len(PROFIT_TARGETS)

    # 最良条件 (B=52% の中で)
    best_sk, best_t, best_a = max(b52_aggs, key=lambda x: x[2]["avg_pnl"])

    def render_table(b_rate, b_label, b_color):
        """B_rate 固定で SEQ × 利確 を一表に"""
        rows = ""
        for sk in SEQS:
            s = SEQS[sk]
            cells = f'<td style="color:{s["color"]};font-weight:bold">{sk}. {s["label"]}</td>'
            for t in PROFIT_TARGETS:
                agg = results[(sk, t, b_rate)][1]
                pnl_col = color_pnl(agg["avg_pnl"])
                bust_badge = ""
                if agg["bust_count"] > 0:
                    bust_badge = f' <span style="color:#f87171;font-size:11px">⚠{agg["bust_count"]}/20</span>'
                cells += (
                    f'<td style="color:{pnl_col};font-weight:bold">${agg["avg_pnl"]:+,.0f}{bust_badge}</td>'
                    f'<td style="color:#8a96a8;font-size:12px">DD ${agg["avg_dd"]:,.0f}</td>'
                )
            rows += f"<tr>{cells}</tr>\n"

        header = "<th>SEQ</th>"
        for t in PROFIT_TARGETS:
            header += f'<th colspan="2" style="text-align:center">利確 ${t}</th>'
        sub = "<th></th>"
        for _ in PROFIT_TARGETS:
            sub += '<th>avg PNL</th><th>avg DD</th>'
        return f"""
<h3 style="color:{b_color}">B = {b_rate*100:.2f}% ({b_label})</h3>
<table>
<thead>
<tr>{header}</tr>
<tr style="font-size:11px">{sub}</tr>
</thead>
<tbody>{rows}</tbody>
</table>
"""

    # 破綻率ヒートマップ (SEQ × 利確) × B_rate
    def render_bust_heatmap(b_rate, b_label, b_color):
        rows = ""
        for sk in SEQS:
            s = SEQS[sk]
            cells = f'<td style="color:{s["color"]};font-weight:bold">{sk}. {s["label"]}</td>'
            for t in PROFIT_TARGETS:
                agg = results[(sk, t, b_rate)][1]
                count = agg["bust_count"]
                if count == 0:
                    cell_color = "#4ade80"
                    bg = "#1a3a2a"
                elif count <= 5:
                    cell_color = "#fbbf24"
                    bg = "#3a2a1a"
                else:
                    cell_color = "#f87171"
                    bg = "#3a1a1a"
                cells += f'<td style="background:{bg};color:{cell_color};font-weight:bold;text-align:center">{count}/{N_TRIALS}</td>'
            rows += f"<tr>{cells}</tr>\n"

        header = "<th>SEQ</th>"
        for t in PROFIT_TARGETS:
            header += f"<th>${t} 利確</th>"
        return f"""
<h3 style="color:{b_color}">B = {b_rate*100:.2f}% ({b_label})</h3>
<table>
<thead><tr>{header}</tr></thead>
<tbody>{rows}</tbody>
</table>
"""

    table_52 = render_table(0.52, "狙い打ち仮定", "#4ade80")
    table_51 = render_table(0.5105, "実データ", "#f87171")
    heat_52 = render_bust_heatmap(0.52, "狙い打ち仮定", "#4ade80")
    heat_51 = render_bust_heatmap(0.5105, "実データ", "#f87171")

    # SEQ 一覧
    seq_list = ""
    for sk, s in SEQS.items():
        seq_str = ", ".join(f"${v:,}" for v in s["seq"])
        seq_list += f"""
<div style="margin: 8px 0; padding: 10px 14px; background: #1a2332; border-left: 4px solid {s['color']}; border-radius: 4px">
<b style="color:{s['color']}">{sk}. {s['label']}</b> <span style="color:#8a96a8; font-size:11px">({len(s['seq'])} 段 / max ${max(s['seq']):,})</span>
<div class="seq-box">[{seq_str}]</div>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>AK. SEQ × 利確額スキャン — 元本 $100k / 5 SEQ × 3 利確 × 2 勝率</title>
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
table th:first-child, table td:first-child {{ text-align: left; }}
table td {{ padding: 8px; text-align: right; border-bottom: 1px solid #2a3441; }}
.seq-box {{ background: #0f1419; padding: 8px; border-radius: 4px; font-family: monospace; font-size: 11px; color: #6dd5ed; word-wrap: break-word; margin: 4px 0; }}
.note {{ background: #1a2332; border-left: 4px solid #6dd5ed; padding: 12px 16px; margin: 20px 0; font-size: 13px; color: #b8c5d6; border-radius: 4px; line-height: 1.7; }}
.note b {{ color: #6dd5ed; }}
</style></head><body>
<div class="container">
<h1>AK. SEQ × 利確額スキャン — 元本 $100,000</h1>

<div class="nav">
<a href="index.html">← レポートTOP</a>
<a href="seq2_banker_52pct_30k.html">AI. 新SEQ2 単独</a>
<a href="seq_fair_comparison.html">AJ. 5 SEQ 公平比較</a>
</div>

<div class="banner">
<strong>🔬 $100k 元本固定で「どの利確額が最適か」を全 SEQ 比較</strong><br>
5 SEQ × 利確 $30 / $50 / $100 × B=51.05% (実データ) / B=52% (狙い打ち) × {N_TRIALS} trial = 600 sims。<br>
<strong>元本が十分ある前提で、どの SEQ × どの利確額が最も効率的か?</strong>
</div>

<h2>🎯 全体サマリー</h2>
<div class="summary">
  <div class="card profit"><div class="label">最優秀 条件</div><div class="value">{best_sk}. ${best_t} 利確</div><div class="sub">B=52%: avg ${best_a['avg_pnl']:+,.0f}</div></div>
  <div class="card bankrupt"><div class="label">B=51.05% 破綻</div><div class="value">{busts_51} / {total_trials}</div><div class="sub">{busts_51/total_trials*100:.0f}% 破綻</div></div>
  <div class="card profit"><div class="label">B=52% 破綻</div><div class="value">{busts_52} / {total_trials}</div><div class="sub">{busts_52/total_trials*100:.0f}% 破綻</div></div>
  <div class="card"><div class="label">試行数</div><div class="value">600</div><div class="sub">5 SEQ × 3 利確 × 2 勝率 × 20</div></div>
</div>

<h2>📋 対象 SEQ</h2>
{seq_list}

<h2>📐 共通条件</h2>
<div class="note">
<b>元本</b>: ${BANKROLL:,} / <b>ハンド数</b>: {N_HANDS:,} / <b>試行</b>: {N_TRIALS} / seed 共有<br>
<b>ルール</b>: 7 ターン制 / BET = seq_val (手数料補正なし) / 勝ち ×0.95 / 負け ×(−1) / 利確でリセット / 損切なし<br>
<b>EV/bet</b>: B=52% で +1.40% / B=51.05% で −0.46%
</div>

<h2>🟥 破綻ヒートマップ — B=51.05% (実データ)</h2>
{heat_51}

<h2>🟩 破綻ヒートマップ — B=52% (狙い打ち)</h2>
{heat_52}

<h2>📊 avg PNL 比較 — B=52% (狙い打ち仮定)</h2>
{table_52}

<h2>📉 avg PNL 比較 — B=51.05% (実データ)</h2>
{table_51}

<div class="note">
<b>📖 読み方</b><br>
・<b>破綻ヒートマップ</b>: 緑=破綻0 / 黄=1〜5 / 赤=6〜20<br>
・<b>avg PNL</b>: {N_TRIALS} 試行の平均損益 / <b>avg DD</b>: 平均ドローダウン<br>
・<b>⚠ N/20</b> 表示: そのセルで破綻した試行数<br>
・B=52% の avg PNL は「破綻しなかった試行」の期待値として強気に読める / B=51.05% は「損失はどこまで拡大するか」の目安
</div>
</div></body></html>"""


def main():
    print(f"=== SEQ × 利確額スキャン — 元本 ${BANKROLL:,} (手数料補正なし) ===", flush=True)
    print(f"SEQs={list(SEQS.keys())} / Targets={PROFIT_TARGETS} / B={B_RATES}", flush=True)
    total = len(SEQS) * len(PROFIT_TARGETS) * len(B_RATES)
    print(f"{total} 条件 × {N_TRIALS} trial = {total * N_TRIALS} sims", flush=True)
    print(f"N_HANDS={N_HANDS:,}", flush=True)

    results = run_all()

    print("\n=== サマリ: 破綻率 (B=51.05% / 実データ) ===", flush=True)
    for sk in SEQS:
        row = "  " + sk + ":"
        for t in PROFIT_TARGETS:
            agg = results[(sk, t, 0.5105)][1]
            row += f" ${t}→{agg['bust_count']}/{N_TRIALS}"
        print(row, flush=True)

    print("\n=== サマリ: 破綻率 (B=52% / 狙い打ち) ===", flush=True)
    for sk in SEQS:
        row = "  " + sk + ":"
        for t in PROFIT_TARGETS:
            agg = results[(sk, t, 0.52)][1]
            row += f" ${t}→{agg['bust_count']}/{N_TRIALS}"
        print(row, flush=True)

    html = render_html(results)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")


if __name__ == "__main__":
    main()
