"""Generate equity-curve / session ledger HTML report.

Starts with $10,000, +$50 per profit session, -$3000 per loss session.
Walks all qualified tables chronologically across analytics.sqlite3.

Usage: python generate_equity_report.py
Output: report/equity_ledger.html
"""
import sqlite3
import json
import os
from collections import defaultdict
from datetime import datetime

DB_PATH = "analytics.sqlite3"
START_CAPITAL = 10000
PROFIT_PER_WIN = 50
LOSS_PER_LOSS = 3000

MIN_HANDS_PER_SHOE = 50
MIN_SHOES = 5  # ローカルDBに合わせて緩和（VPSは30）
MAX_DD_THRESHOLD = 2500
EXCLUDE_TABLES = {'Dynasty Speed Baccarat 5'}

SEQ = [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55,
       60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142,
       148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250]


class MaruBatsuSim:
    def __init__(self, target=PROFIT_PER_WIN, lc=LOSS_PER_LOSS):
        self.target = target
        self.lc = lc
        self.reset()

    def reset(self):
        self.cumulative = 0
        self.unit_idx = 0
        self.prev_os = 0
        self.sets = 0
        self.hands = 0
        self.turns = []
        self.max_dd = 0
        self.peak = 0
        self.history = []

    def _next_idx(self, used_idx, diff, new_os):
        if diff < 0:
            return min(used_idx + 1, len(SEQ) - 1)
        for fi in range(len(self.history) - 1, -1, -1):
            s = self.history[fi]
            if not s['slashed'] and s['os'] == new_os:
                return s['next']
        ba, bad = -1, float("inf")
        bb, bbd = -1, float("inf")
        for fk in range(len(self.history)):
            s = self.history[fk]
            if not s['slashed']:
                dd = s['os'] - new_os
                if dd > 0 and dd < bad:
                    bad = dd
                    ba = s['next']
                if dd < 0 and (-dd) < bbd:
                    bbd = -dd
                    bb = s['next']
        if ba >= 0:
            return ba
        if bb >= 0:
            return min(bb + 1, len(SEQ) - 1)
        return 0

    def _complete(self):
        wins = self.turns.count('O')
        diff = wins - (7 - wins)
        unit = SEQ[self.unit_idx] if self.unit_idx < len(SEQ) else SEQ[-1]
        self.cumulative += unit * diff
        self.sets += 1
        new_os = max(self.prev_os - diff, 0)
        if diff > 0:
            for s in self.history:
                if not s['slashed'] and s['os'] > new_os:
                    s['slashed'] = True
        next_idx = self._next_idx(self.unit_idx, diff, new_os)
        self.history.append({'os': new_os, 'slashed': False, 'next': next_idx})
        self.prev_os = new_os
        self.unit_idx = next_idx
        self.turns = []
        if self.cumulative > self.peak:
            self.peak = self.cumulative
        self.max_dd = max(self.max_dd, self.peak - self.cumulative)

    def add(self, r):
        if r == 'T':
            return None
        self.hands += 1
        self.turns.append('O' if r == 'P' else 'X')
        if len(self.turns) == 7:
            self._complete()
        if self.cumulative >= self.target:
            return 'profit'
        if self.cumulative <= -self.lc:
            return 'loss'
        return None


def simulate_table_sessions(table_name, shoes):
    """Run sim and return list of sessions with timestamps."""
    sessions = []
    sim = MaruBatsuSim()
    cur_ts = shoes[0][1] if shoes else None

    for seq, started_at in shoes:
        for r in seq:
            if r not in ('P', 'B', 'T'):
                continue
            o = sim.add(r)
            if o:
                sessions.append({
                    'table': table_name,
                    'started_at': started_at,
                    'outcome': o,
                    'profit': sim.cumulative,
                    'hands': sim.hands,
                    'max_dd': sim.max_dd,
                })
                sim.reset()
                cur_ts = started_at
    return sessions


def main():
    print(f"Loading {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name, result_sequence, started_at FROM shoes_analytics "
        "WHERE hand_count >= ? ORDER BY started_at",
        (MIN_HANDS_PER_SHOE,)
    )
    shoes_by_table = defaultdict(list)
    total_hands = 0
    for tn, seq, ts in cur.fetchall():
        shoes_by_table[tn].append((seq, ts))
        total_hands += sum(1 for c in seq if c in ('P', 'B', 'T'))
    conn.close()

    print(f"Total {total_hands} hands across {len(shoes_by_table)} tables")

    # Step 1: identify qualified tables (same as auto_update_tables.py)
    table_stats = {}
    for tn, shoes in shoes_by_table.items():
        if len(shoes) < MIN_SHOES:
            continue
        if tn in EXCLUDE_TABLES:
            continue
        sessions = simulate_table_sessions(tn, shoes)
        if not sessions:
            continue
        wins = sum(1 for s in sessions if s['outcome'] == 'profit')
        losses = sum(1 for s in sessions if s['outcome'] == 'loss')
        if wins + losses == 0:
            continue
        win_rate = wins / (wins + losses) * 100
        max_dd = max(s['max_dd'] for s in sessions)
        table_stats[tn] = {
            'sessions': sessions,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'max_dd': max_dd,
        }

    # Qualified: 100% win, max_dd <= threshold
    qualified = {
        tn: st for tn, st in table_stats.items()
        if st['win_rate'] >= 100 and st['max_dd'] <= MAX_DD_THRESHOLD
    }
    print(f"Qualified tables: {len(qualified)}")
    for tn, st in qualified.items():
        try:
            print(f"  {tn}: {st['wins']}W / {st['losses']}L  DD={st['max_dd']}")
        except UnicodeEncodeError:
            print(f"  [name] {st['wins']}W / {st['losses']}L  DD={st['max_dd']}")

    # Step 2: collect ALL sessions from qualified tables, sort chronologically
    all_sessions = []
    for tn, st in qualified.items():
        all_sessions.extend(st['sessions'])
    all_sessions.sort(key=lambda s: s['started_at'])

    print(f"Total sessions in ledger: {len(all_sessions)}")

    # Step 3: build running balance
    balance = START_CAPITAL
    rows = []
    peak = balance
    max_dd_dollars = 0
    wins_running = 0
    losses_running = 0
    for i, s in enumerate(all_sessions, 1):
        if s['outcome'] == 'profit':
            delta = PROFIT_PER_WIN
            wins_running += 1
        else:
            delta = -LOSS_PER_LOSS
            losses_running += 1
        balance += delta
        if balance > peak:
            peak = balance
        dd = peak - balance
        if dd > max_dd_dollars:
            max_dd_dollars = dd
        rows.append({
            'turn': i,
            'started_at': s['started_at'],
            'table': s['table'],
            'outcome': s['outcome'],
            'delta': delta,
            'balance': balance,
            'hands': s['hands'],
        })

    # Step 4: write HTML
    final_balance = balance
    total_profit = final_balance - START_CAPITAL
    roi = total_profit / START_CAPITAL * 100

    # build qualified table summary html
    qualified_html = ""
    for tn, st in sorted(qualified.items(), key=lambda x: -len(x[1]['sessions'])):
        qualified_html += (
            f"<tr><td>{tn}</td><td>{st['wins']}</td><td>{st['losses']}</td>"
            f"<td>{st['win_rate']:.1f}%</td><td>${st['max_dd']}</td></tr>"
        )

    # build session rows
    rows_html = ""
    for r in rows:
        ts = r['started_at'][:16].replace('T', ' ') if r['started_at'] else '-'
        outcome_class = 'profit' if r['outcome'] == 'profit' else 'loss'
        outcome_label = 'WIN' if r['outcome'] == 'profit' else 'LOSS'
        delta_sign = '+' if r['delta'] >= 0 else ''
        rows_html += (
            f"<tr class='{outcome_class}'>"
            f"<td class='turn'>{r['turn']}</td>"
            f"<td class='ts'>{ts}</td>"
            f"<td class='tn'>{r['table']}</td>"
            f"<td class='oc'>{outcome_label}</td>"
            f"<td class='dl'>{delta_sign}${r['delta']:,}</td>"
            f"<td class='bl'>${r['balance']:,}</td>"
            f"<td class='hd'>{r['hands']}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>LAPLACE 通算セッション台帳 — $10,000スタート</title>
<style>
* {{ box-sizing: border-box; }}
body {{
  font-family: -apple-system, "Segoe UI", "Hiragino Sans", "Yu Gothic UI", sans-serif;
  background: #0f1419;
  color: #e0e6ed;
  margin: 0;
  padding: 24px;
  line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ color: #ffd700; font-size: 28px; border-bottom: 2px solid #ffd700; padding-bottom: 8px; }}
h2 {{ color: #6dd5ed; margin-top: 32px; }}
.summary {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin: 24px 0;
}}
.card {{
  background: #1a2332;
  border-left: 4px solid #6dd5ed;
  padding: 16px;
  border-radius: 4px;
}}
.card .label {{ font-size: 12px; color: #8a96a8; text-transform: uppercase; }}
.card .value {{ font-size: 24px; font-weight: bold; color: #ffd700; }}
.card.win {{ border-left-color: #4ade80; }}
.card.win .value {{ color: #4ade80; }}
.card.loss {{ border-left-color: #f87171; }}
.card.loss .value {{ color: #f87171; }}
table {{
  width: 100%;
  border-collapse: collapse;
  background: #1a2332;
  margin: 16px 0;
  font-size: 13px;
}}
th {{
  background: #0f1419;
  color: #ffd700;
  padding: 10px 8px;
  text-align: left;
  border-bottom: 2px solid #ffd700;
  position: sticky;
  top: 0;
}}
td {{ padding: 6px 8px; border-bottom: 1px solid #2a3441; }}
tr.profit td.oc {{ color: #4ade80; font-weight: bold; }}
tr.loss td.oc {{ color: #f87171; font-weight: bold; }}
tr.loss td.dl {{ color: #f87171; }}
tr.profit td.dl {{ color: #4ade80; }}
td.bl {{ font-weight: bold; color: #ffd700; }}
td.turn {{ text-align: right; color: #8a96a8; }}
td.ts {{ font-family: monospace; color: #8a96a8; font-size: 11px; }}
td.hd {{ text-align: right; color: #8a96a8; }}
.ledger-wrapper {{ max-height: 70vh; overflow-y: auto; border: 1px solid #2a3441; }}
.note {{ color: #8a96a8; font-size: 13px; margin: 8px 0; }}
.win-stat {{ color: #4ade80; }}
.loss-stat {{ color: #f87171; }}
</style>
</head>
<body>
<div class="container">
<h1>LAPLACE 通算セッション台帳</h1>
<p class="note">
  $10,000元本スタート → 1セッション利確$50 / 損切り-$3,000 を全{len(all_sessions)}セッションに通貫させたシミュレーション。<br>
  対象: 推奨条件（最低{MIN_SHOES}シュー・勝率100%・最大DD ≤ ${MAX_DD_THRESHOLD}）を満たす{len(qualified)}テーブル。<br>
  データ: analytics.sqlite3 全{total_hands:,}ハンド（{sum(len(s) for s in shoes_by_table.values())}シュー）から抽出。
</p>

<div class="summary">
  <div class="card">
    <div class="label">スタート資金</div>
    <div class="value">${START_CAPITAL:,}</div>
  </div>
  <div class="card win">
    <div class="label">最終資金</div>
    <div class="value">${final_balance:,}</div>
  </div>
  <div class="card win">
    <div class="label">通算利益</div>
    <div class="value">+${total_profit:,}</div>
  </div>
  <div class="card win">
    <div class="label">ROI</div>
    <div class="value">+{roi:.1f}%</div>
  </div>
  <div class="card">
    <div class="label">セッション数</div>
    <div class="value">{len(all_sessions)}</div>
  </div>
  <div class="card win">
    <div class="label">勝ちセッション</div>
    <div class="value">{wins_running}</div>
  </div>
  <div class="card loss">
    <div class="label">負けセッション</div>
    <div class="value">{losses_running}</div>
  </div>
  <div class="card">
    <div class="label">勝率</div>
    <div class="value">{(wins_running/(wins_running+losses_running)*100 if (wins_running+losses_running) else 0):.1f}%</div>
  </div>
  <div class="card loss">
    <div class="label">最大DD ($)</div>
    <div class="value">${max_dd_dollars:,}</div>
  </div>
</div>

<h2>対象テーブル一覧</h2>
<table>
<thead><tr><th>テーブル名</th><th>勝ち</th><th>負け</th><th>勝率</th><th>最大DD</th></tr></thead>
<tbody>{qualified_html}</tbody>
</table>

<h2>セッション台帳（時系列順）</h2>
<p class="note">時系列順にソート。各セッションの結果と残高推移を追えます。</p>
<div class="ledger-wrapper">
<table>
<thead>
<tr>
  <th>#</th><th>日時</th><th>テーブル</th><th>結果</th><th>増減</th><th>残高</th><th>消費ハンド</th>
</tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</div>

<p class="note" style="margin-top:32px;">
  生成元: <code>generate_equity_report.py</code> / 利確$50・損切り$3,000・MaruBatsuロジック適用
</p>

</div>
</body>
</html>
"""
    out_path = os.path.join("report", "equity_ledger.html")
    os.makedirs("report", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {out_path}")
    print(f"Final balance: ${final_balance:,} (start ${START_CAPITAL:,}, ROI +{roi:.1f}%)")
    print(f"Wins: {wins_running}  Losses: {losses_running}  Max DD: ${max_dd_dollars:,}")


if __name__ == "__main__":
    main()
