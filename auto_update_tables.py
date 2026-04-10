"""VPS Auto Update Recommended Tables

毎日cron実行（例: AM 6:00）:
 1. analytics.sqlite3 を分析
 2. MaruBatsu シミュレーションで勝率・累計・最大DDを計算
 3. 条件を満たすテーブルを推奨リストに抽出
 4. Vercel API経由でSupabaseに保存

条件:
 - 最低30シュー以上
 - 勝率100% (0敗)
 - 累計プラス
 - 最大DD < $1500

使い方:
  python auto_update_tables.py
  # または
  python auto_update_tables.py --dry-run  # 保存なし
"""
import sqlite3
import json
import sys
import os
import argparse
import urllib.request
import urllib.error
from collections import defaultdict

DB_PATH = "/opt/laplace/analytics.sqlite3"
SITE_URL = os.getenv("LAPLACE_SITE_URL", "https://bafather.uk")
API_KEY = os.getenv("LAPLACE_API_KEY", "")
ADMIN_EMAIL = os.getenv("LAPLACE_ADMIN_EMAIL", "goldbenchan@gmail.com")

# 条件
MIN_SHOES = 30
MIN_HANDS_PER_SHOE = 50
MAX_DD_THRESHOLD = 2500
PROFIT_TARGET = 50
LOSS_CUT = 3000

# 手動除外テーブル（統計的に100%でもリスクが高いもの）
EXCLUDE_TABLES = {
    'Dynasty Speed Baccarat 5',  # Dynasty系は傾向不安定
}

SEQ = [1, 2, 3, 5, 7, 9, 11, 13, 16, 19, 22, 25, 28, 31, 35, 39, 43, 47, 51, 55,
       60, 65, 70, 75, 80, 85, 90, 95, 100, 106, 112, 118, 124, 130, 136, 142,
       148, 154, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250]


class MaruBatsuSim:
    def __init__(self, target=PROFIT_TARGET, lc=LOSS_CUT):
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
                if dd > 0 and dd < bad: bad = dd; ba = s['next']
                if dd < 0 and (-dd) < bbd: bbd = -dd; bb = s['next']
        if ba >= 0: return ba
        if bb >= 0: return min(bb + 1, len(SEQ) - 1)
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


def simulate_table(sequences):
    """テーブルのシュー列を連結してシミュ"""
    all_results = []
    for seq in sequences:
        all_results.extend([c for c in seq if c in ('P', 'B', 'T')])

    sessions = []
    sim = MaruBatsuSim()
    for r in all_results:
        o = sim.add(r)
        if o:
            sessions.append({
                'outcome': o,
                'profit': sim.cumulative,
                'hands': sim.hands,
                'max_dd': sim.max_dd,
            })
            sim.reset()

    profit_count = sum(1 for s in sessions if s['outcome'] == 'profit')
    loss_count = sum(1 for s in sessions if s['outcome'] == 'loss')
    total = profit_count + loss_count
    if total == 0:
        return None

    total_profit = sum(s['profit'] for s in sessions) + sim.cumulative
    max_dd = max((s['max_dd'] for s in sessions), default=0)
    win_rate = profit_count / total * 100

    return {
        'sessions': total,
        'profit_sessions': profit_count,
        'loss_sessions': loss_count,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'max_dd': max_dd,
    }


def analyze_all_tables():
    """全テーブルを分析して推奨リストを作成"""
    print(f"Loading {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT table_name, result_sequence, started_at FROM shoes_analytics "
        "WHERE hand_count >= ? ORDER BY started_at",
        (MIN_HANDS_PER_SHOE,)
    )
    shoes_by_table = defaultdict(list)
    for row in cur.fetchall():
        shoes_by_table[row[0]].append(row[1])
    conn.close()

    print(f"Total {sum(len(v) for v in shoes_by_table.values())} shoes across {len(shoes_by_table)} tables\n")

    results = []
    for table_name, sequences in shoes_by_table.items():
        if len(sequences) < MIN_SHOES:
            continue
        stats = simulate_table(sequences)
        if stats is None:
            continue
        results.append({
            'name': table_name,
            'shoes': len(sequences),
            **stats,
        })

    # 条件フィルター
    qualified = [
        r for r in results
        if r['win_rate'] >= 100
        and r['total_profit'] > 0
        and r['max_dd'] <= MAX_DD_THRESHOLD
        and r['name'] not in EXCLUDE_TABLES
    ]

    # 信頼度順にソート（total_profit 大 + max_dd 小）
    qualified.sort(key=lambda x: (x['total_profit'] / max(x['max_dd'], 1)), reverse=True)

    return results, qualified


def post_to_supabase(tables):
    """Vercel API経由でSupabaseに保存"""
    if not API_KEY:
        print("LAPLACE_API_KEY not set — skipping upload")
        return False

    payload = json.dumps({
        'email': ADMIN_EMAIL,
        'api_key': API_KEY,
        'tables': tables,
    }).encode('utf-8')

    url = f"{SITE_URL}/api/recommended-tables"
    # HTTPリダイレクトを許可するため手動で2段階
    for _attempt in range(3):
        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'LAPLACE-cron/1.0'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                print(f"Supabase upload: {data}")
                return True
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                new_url = e.headers.get('Location')
                if new_url:
                    print(f"Redirect {e.code} -> {new_url}")
                    url = new_url if new_url.startswith('http') else f"{SITE_URL}{new_url}"
                    continue
            body = e.read().decode(errors='replace')[:200]
            print(f"HTTP error: {e.code} {body}")
            return False
        except Exception as e:
            print(f"Upload failed: {e}")
            return False
    print("Too many redirects")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--max', type=int, default=10, help='Max tables to recommend')
    args = parser.parse_args()

    all_results, qualified = analyze_all_tables()

    print("=" * 70)
    print(f"Analysis complete: {len(all_results)} tables analyzed, {len(qualified)} qualified")
    print("=" * 70)

    print(f"\nTop {min(args.max, len(qualified))} recommended tables:")
    for i, t in enumerate(qualified[:args.max]):
        print(f"  {i+1}. {t['name']}: {t['profit_sessions']}/{t['sessions']}={t['win_rate']:.1f}% "
              f"profit=+{t['total_profit']} DD={t['max_dd']} shoes={t['shoes']}")

    # Supabase payload
    tables_payload = []
    for i, t in enumerate(qualified[:args.max]):
        tables_payload.append({
            'name': t['name'],
            'enabled': True,
            'priority': i + 1,
            'win_rate': round(t['win_rate'], 1),
            'sessions': t['sessions'],
            'total_profit': t['total_profit'],
            'max_dd': t['max_dd'],
            'shoes': t['shoes'],
        })

    if args.dry_run:
        print("\n[DRY RUN] Would upload:")
        print(json.dumps(tables_payload, indent=2, ensure_ascii=False))
    else:
        print("\nUploading to Supabase...")
        post_to_supabase(tables_payload)


if __name__ == '__main__':
    main()
