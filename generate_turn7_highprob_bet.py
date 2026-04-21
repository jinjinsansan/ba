"""ターン6終了時に「確率が高い方」へBETする戦略 — 7ターン目のみBET

ユーザー理論:
  7ターン制の最終分布 (山型) を基に、ターン6時点の状態から
  Player勝で遷移する最終状態の base rate > Banker勝で遷移する最終状態の base rate
  なら Player が「確率が高い方」。Playerが高ければBET、BankerならLOOK。

計算結果:
  wins_at_turn6 <= 2  → Player予測 → BET Player
  wins_at_turn6 >= 3  → Banker予測 → LOOK (負けない)

対象: analytics_vps_latest.sqlite3, Evolution 62テーブル, 2026-04-06〜2026-04-19
前提: Tie はスキップ (BET/ターン数に数えない)
"""
from __future__ import annotations
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "analytics_vps_latest.sqlite3"
OUT_HTML = Path(__file__).parent / "report" / "turn7_highprob_bet.html"
CUTOFF = "2026-04-06"
SET_SIZE = 7

# 先ほどのバックテスト結果 (観測 final distribution)
OBSERVED_FINAL_DIST = {
    7: 1700, 6: 12449, 5: 38263, 4: 65751,
    3: 68191, 2: 42588, 1: 15005, 0: 2244,
}

def decide_bet(wins_at_t6: int) -> str:
    """ターン6終了時の勝数から、7ターン目の判断を返す。
       Player予測なら 'P', Banker予測なら 'LOOK'。"""
    next_if_p = wins_at_t6 + 1
    next_if_b = wins_at_t6
    p_base = OBSERVED_FINAL_DIST.get(next_if_p, 0)
    b_base = OBSERVED_FINAL_DIST.get(next_if_b, 0)
    if p_base > b_base:
        return "P"
    return "LOOK"


def fetch_hands(conn: sqlite3.Connection):
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

    # 各状態(wins at T6)ごとの統計
    # state_bets[w] = BET数 (ターン6時点で勝数=w の全セット内、ルールでBETしたもの)
    # state_wins[w] = BET勝数 (7ターン目がP)
    # state_losses[w] = BET負数 (7ターン目がB)
    # state_looks[w] = LOOK数 (BETしなかった)
    # state_look_p[w] = LOOK時の7ターン目がP (= 逃した勝)
    # state_look_b[w] = LOOK時の7ターン目がB (= 回避した負)
    state_total = Counter()
    state_bets = Counter()
    state_wins = Counter()
    state_losses = Counter()
    state_looks = Counter()
    state_look_p = Counter()  # LOOK中の7ターン目P (見送った勝ち)
    state_look_b = Counter()  # LOOK中の7ターン目B (回避した負け)

    current_turns = []  # 現セット内の mark ('O'=P, 'X'=B) 非Tie のみ
    ties = 0
    p_cnt = 0
    b_cnt = 0

    for (res,) in fetch_hands(conn):
        r = (res or "").strip().upper()
        if r in ("T", "TIE"):
            ties += 1
            continue
        if r in ("P", "PLAYER"):
            mark = "O"
            p_cnt += 1
        elif r in ("B", "BANKER"):
            mark = "X"
            b_cnt += 1
        else:
            continue

        current_turns.append(mark)

        if len(current_turns) == SET_SIZE:
            # ターン6時点の勝数
            wins_at_t6 = sum(1 for x in current_turns[:6] if x == "O")
            t7 = current_turns[6]  # 7ターン目
            t7_is_p = (t7 == "O")

            state_total[wins_at_t6] += 1
            decision = decide_bet(wins_at_t6)
            if decision == "P":
                state_bets[wins_at_t6] += 1
                if t7_is_p:
                    state_wins[wins_at_t6] += 1
                else:
                    state_losses[wins_at_t6] += 1
            else:
                state_looks[wins_at_t6] += 1
                if t7_is_p:
                    state_look_p[wins_at_t6] += 1
                else:
                    state_look_b[wins_at_t6] += 1

            current_turns.clear()

    conn.close()

    total_sets = sum(state_total.values())
    total_bets = sum(state_bets.values())
    total_wins = sum(state_wins.values())
    total_losses = sum(state_losses.values())
    total_looks = sum(state_looks.values())
    total_look_p = sum(state_look_p.values())  # 見送った勝ち
    total_look_b = sum(state_look_b.values())  # 回避した負け

    summary = {
        "cutoff": CUTOFF,
        "shoe_min": meta[0],
        "shoe_max": meta[1],
        "shoe_count": meta[2],
        "table_count": meta[3],
        "ties": ties,
        "p_cnt": p_cnt,
        "b_cnt": b_cnt,
        "total_sets": total_sets,
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_looks": total_looks,
        "total_look_p": total_look_p,
        "total_look_b": total_look_b,
        "state_total": dict(state_total),
        "state_bets": dict(state_bets),
        "state_wins": dict(state_wins),
        "state_losses": dict(state_losses),
        "state_looks": dict(state_looks),
        "state_look_p": dict(state_look_p),
        "state_look_b": dict(state_look_b),
    }
    return summary


def render_html(s: dict) -> str:
    tb = s["total_bets"]
    tw = s["total_wins"]
    tl = s["total_losses"]
    wr = tw / tb * 100 if tb else 0
    pnl = tw - tl  # フラット$1 BET 想定
    roi = pnl / tb * 100 if tb else 0

    rows = ["<tr><th>T6 勝数</th><th>判断</th><th>該当セット</th><th>BET数</th><th>勝</th><th>負</th><th>勝率</th><th>LOOK数</th><th>LOOK中P(見送った勝)</th><th>LOOK中B(回避した負)</th></tr>"]
    for w in range(SET_SIZE):
        total = s["state_total"].get(w, 0)
        decision = decide_bet(w)
        bets = s["state_bets"].get(w, 0)
        wins = s["state_wins"].get(w, 0)
        losses = s["state_losses"].get(w, 0)
        looks = s["state_looks"].get(w, 0)
        look_p = s["state_look_p"].get(w, 0)
        look_b = s["state_look_b"].get(w, 0)
        wrate = wins / bets * 100 if bets else 0
        color = "#4ade80" if decision == "P" else "#94a3b8"
        rows.append(
            f"<tr><td><b>{w}勝{6-w}負</b></td>"
            f"<td style='color:{color}'><b>{decision}</b></td>"
            f"<td>{total:,}</td>"
            f"<td>{bets:,}</td>"
            f"<td class='pos'>{wins:,}</td>"
            f"<td class='neg'>{losses:,}</td>"
            f"<td>{'{:.3f}%'.format(wrate) if bets else '-'}</td>"
            f"<td>{looks:,}</td>"
            f"<td>{look_p:,}</td>"
            f"<td>{look_b:,}</td>"
            "</tr>"
        )

    color_pnl = "#4ade80" if pnl > 0 else ("#f87171" if pnl < 0 else "#cbd5e1")

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>ターン7 確率高方BET — 旧SEQ×7ターン</title>
<style>
body{{font-family:'Noto Sans JP',sans-serif;background:#0f172a;color:#e2e8f0;padding:40px 20px;margin:0}}
.container{{max-width:1100px;margin:0 auto}}
h1{{font-size:30px;background:linear-gradient(135deg,#fbbf24,#f87171);-webkit-background-clip:text;background-clip:text;color:transparent;margin:0 0 8px}}
.sub{{color:#94a3b8;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:20px 0}}
.card{{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:18px}}
.card .k{{font-size:12px;color:#94a3b8}}
.card .v{{font-size:22px;font-weight:700;margin-top:6px}}
table{{width:100%;border-collapse:collapse;margin:24px 0;background:rgba(255,255,255,0.03);border-radius:12px;overflow:hidden}}
th,td{{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.08);text-align:right;font-variant-numeric:tabular-nums}}
th{{background:rgba(251,191,36,0.15);color:#fbbf24;text-align:left}}
td:first-child,td:nth-child(2),th:first-child,th:nth-child(2){{text-align:left}}
.pos{{color:#4ade80}}
.neg{{color:#f87171}}
.note{{background:rgba(255,255,255,0.03);padding:16px 20px;border-left:3px solid #fbbf24;border-radius:6px;margin:20px 0;line-height:1.7;font-size:14px}}
.big{{font-size:28px;font-weight:700;color:{color_pnl}}}
</style></head><body>
<div class="container">
<h1>🎯 ターン7 確率高方BET 戦略</h1>
<div class="sub">7ターン制 / ターン6終了時に最終分布 base rate を比較 → 確率が高い方がPlayerならBET、BankerならLOOK</div>

<div class="note">
<b>ユーザー理論</b>: ターン6終了時の状態から、7ターン目の結果によって到達する最終状態の
「観測 base rate」を比較し、Player勝で行く先のほうがbase rateが高ければPlayer BET、
そうでなければLOOK。<br>
<b>結果ルール</b>: <code>wins_at_T6 ≤ 2 → BET Player</code> / <code>wins_at_T6 ≥ 3 → LOOK</code>
</div>

<div class="grid">
  <div class="card"><div class="k">対象期間</div><div class="v">{s['cutoff']} 〜 {s['shoe_max'][:10]}</div></div>
  <div class="card"><div class="k">総セット数</div><div class="v">{s['total_sets']:,}</div></div>
  <div class="card"><div class="k">BET数</div><div class="v">{s['total_bets']:,}</div></div>
  <div class="card"><div class="k">LOOK数</div><div class="v">{s['total_looks']:,}</div></div>
  <div class="card"><div class="k">BET率</div><div class="v">{s['total_bets']/s['total_sets']*100:.2f}%</div></div>
  <div class="card"><div class="k">Player勝ち (win)</div><div class="v pos">{s['total_wins']:,}</div></div>
  <div class="card"><div class="k">Player負け (loss)</div><div class="v neg">{s['total_losses']:,}</div></div>
  <div class="card"><div class="k"><b>勝率</b></div><div class="big">{wr:.3f}%</div></div>
  <div class="card"><div class="k">フラット$1 PNL</div><div class="big">${pnl:+,}</div></div>
  <div class="card"><div class="k">ROI</div><div class="big">{roi:+.3f}%</div></div>
</div>

<h2>📊 状態別内訳 (T6 勝数ごと)</h2>
<table>{''.join(rows)}</table>

<h2>LOOK の評価</h2>
<div class="grid">
  <div class="card"><div class="k">LOOKで見送った勝ち (T7=P)</div><div class="v pos">{s['total_look_p']:,}</div></div>
  <div class="card"><div class="k">LOOKで回避した負け (T7=B)</div><div class="v neg">{s['total_look_b']:,}</div></div>
  <div class="card"><div class="k">LOOK内 P率</div><div class="v">{s['total_look_p']/(s['total_look_p']+s['total_look_b'])*100 if (s['total_look_p']+s['total_look_b']) else 0:.3f}%</div></div>
</div>

<div class="note" style="border-left-color:#f87171">
<b>⚠️ 解釈の注意</b>: ユーザー理論は「最終分布 base rate」を根拠にしているが、
バカラの各ハンドはほぼIID (Player=49.07%)。ターン6の状態に関わらず ターン7 の結果は
独立に Player 49%, Banker 51%。base rate が高いのは組合せ数 C(7,k) の効果で、
条件付き確率とは別物。BET勝率は状態間でほぼ一定になるはず。
</div>

</div></body></html>
"""


if __name__ == "__main__":
    s = run_backtest()
    print(f"=== ターン7 確率高方BET 戦略 (4/6〜4/19 Evolution) ===")
    print(f"総セット: {s['total_sets']:,}")
    print(f"BET: {s['total_bets']:,} / LOOK: {s['total_looks']:,}")
    print(f"BET率: {s['total_bets']/s['total_sets']*100:.2f}%")
    print(f"勝: {s['total_wins']:,} / 負: {s['total_losses']:,}")
    wr = s['total_wins']/s['total_bets']*100 if s['total_bets'] else 0
    pnl = s['total_wins'] - s['total_losses']
    print(f"勝率: {wr:.3f}%")
    print(f"フラット$1 PNL: ${pnl:+,}")
    print()
    print(f"{'T6 勝':<10}{'判断':<8}{'該当':>10}{'BET':>10}{'勝':>10}{'負':>10}{'勝率':>10}{'LOOK':>10}")
    for w in range(SET_SIZE):
        total = s['state_total'].get(w,0)
        d = decide_bet(w)
        bets = s['state_bets'].get(w,0)
        wins = s['state_wins'].get(w,0)
        losses = s['state_losses'].get(w,0)
        looks = s['state_looks'].get(w,0)
        wrate = wins/bets*100 if bets else 0
        wr_s = f"{wrate:.3f}%" if bets else "-"
        print(f"{w}勝{6-w}負    {d:<8}{total:>10,}{bets:>10,}{wins:>10,}{losses:>10,}{wr_s:>10}{looks:>10,}")
    print()
    print(f"LOOK内 P={s['total_look_p']:,} / B={s['total_look_b']:,}")

    html = render_html(s)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"\nHTML: {OUT_HTML}")
