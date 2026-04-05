"""テーブル選定ロジック (6つの条件を実装)

⚠️  SERVER-ONLY — DO NOT SHIP TO CLIENT ⚠️
このモジュールは compute_score スコアリング式、PLAYERS_PRIMARY /
PLAYERS_RELAXED / MIN_HANDS / MAX_HANDS / DRAGON_LIMIT 等の機密閾値、
および EXCLUDE_TITLE_KEYWORDS ブラックリストを含みます。VPS の
laplace_api (/api/select-table) からのみ import され、client
distribution には含めてはいけません (.dist_excludes 参照)。

条件:
  ① 除外テーブル: Always9, Lightning, XXXtreme, Golden Wealth, Prosperity, Peek,
                    No Commission, Salon Prive, Elite VIP, Stake Exclusive(0.1$)
  ② 参加者数: 50人優先 → 30人緩和 → 30人未満は打たない
  ③ バンカー5連続(ドラゴン)回避: 直近5ハンドがバンカー連続なら入らない
  ⑥ ゲーム進行度: 20~40ハンド進行中かつプレイヤー数 > バンカー数

条件④(ユーザー分散)と⑤(ボット検出)はhumanize/agent側で対応。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# === 除外ルール ===

EXCLUDE_FRONTEND_APPS = {
    "baccarat.alwaysCard",                         # Always 9
    "baccarat.lightning,baccarat.v1.lightning",    # Lightning
    "baccarat.xtreme",                              # XXXtreme Lightning
    "baccarat.goldenWealth,baccarat.v0,baccarat",   # Golden Wealth
    "baccarat.prosperity",                          # Prosperity Tree
    "baccarat.peek,baccarat.v0,baccarat",           # Peek
    "baccarat.regular",                             # No Commission (regular のみ)
}

# 候補となる frontendApp
ALLOWED_FRONTEND_APPS = {
    "baccarat.regular,baccarat.v1.regular",
}

# 除外するタイトルキーワード (保険)
EXCLUDE_TITLE_KEYWORDS = [
    "always 9", "lightning", "prosperity", "golden wealth",
    "peek", "control squeeze", "no commission", "xtreme",
    "salon", "prive", "elite vip", "stake exclusive",
    "squeeze", "insurance",
]

# BET制限 (bl.min=1 のみ許可)
REQUIRED_MIN_BET = 1

# 参加者数しきい値
PLAYERS_PRIMARY = 10
PLAYERS_RELAXED = 1

# 待機時間 (primary閾値が見つからない場合、relaxedに緩和するまでの待機秒数)
RELAX_WAIT_SECONDS = 60

# ゲーム進行度
MIN_HANDS = 20
MAX_HANDS = 40

# ドラゴン回避
DRAGON_LIMIT = 5  # バンカー5連続で回避


@dataclass
class TableCandidate:
    table_id: str
    title: str
    players: int
    hands: int      # 履歴の有効ハンド数 (tie除く)
    p_count: int    # Player 勝ち数
    b_count: int    # Banker 勝ち数
    tie_count: int
    last_5: list[str]  # 直近5ハンドの "P"/"B"/"T"
    score: float = 0.0

    def __str__(self):
        return (f"{self.title} p={self.players} hands={self.hands} "
                f"P={self.p_count} B={self.b_count} T={self.tie_count}")


# === ① 除外判定 ===

def is_excluded(cfg: dict) -> str | None:
    """除外理由を返す。除外対象でなければNone。"""
    title = cfg.get("title", "")
    title_l = title.lower()
    fe = cfg.get("frontendApp", "")
    minbet = cfg.get("bl", {}).get("min", 0)

    if cfg.get("gt") != "baccarat":
        return "not-baccarat-gt"
    if not cfg.get("published", True):
        return "unpublished"
    if minbet != REQUIRED_MIN_BET:
        return f"min=${minbet}"
    if fe not in ALLOWED_FRONTEND_APPS:
        return f"fe={fe}"
    for kw in EXCLUDE_TITLE_KEYWORDS:
        if kw in title_l:
            return f"kw={kw}"
    return None


# === ③ ドラゴン判定 ===

def has_banker_dragon(raw_history: list) -> bool:
    """直近5ハンド以上が連続バンカーか判定。

    raw_history: [{c: "B"/"R", ties: N, ...}] — "B"=Banker, "R"=Player(Red)
    Evolution履歴は新しい順ではなく bead plate position順なので、末尾が最新。
    ties はセル内の引き分けカウントで、結果自体ではない。
    """
    if len(raw_history) < DRAGON_LIMIT:
        return False

    # 末尾から DRAGON_LIMIT 件を取得
    last_entries = raw_history[-DRAGON_LIMIT:]
    for e in last_entries:
        if e.get("c") != "B":
            return False
    return True


# === ⑥ 履歴分析 ===

def analyze_history(raw_history: list) -> tuple[int, int, int, int, list[str]]:
    """履歴から P/B/Tカウントと直近5手を返す。

    Returns: (total_hands, p_count, b_count, tie_count, last_5_list)
    """
    p = 0
    b = 0
    ties = 0
    hands_seq: list[str] = []

    for entry in raw_history:
        c = entry.get("c", "")
        tie_cnt = entry.get("ties", 0) or 0

        if c == "R":
            p += 1
            hands_seq.append("P")
        elif c == "B":
            b += 1
            hands_seq.append("B")
        # tie は別カウント
        ties += tie_cnt

    total_hands = p + b
    last_5 = hands_seq[-5:]
    return total_hands, p, b, ties, last_5


# === スコアリング ===

def compute_score(c: TableCandidate) -> float:
    """候補テーブルのスコア (高いほど良い)

    - 参加者数が多いほど良い (50人以上で大きく加点)
    - ハンド数が 20-40 の中央に近いほど良い
    - プレイヤー数 > バンカー数 ほど加点
    """
    score = 0.0

    # 参加者数
    if c.players >= PLAYERS_PRIMARY:
        score += 50 + min((c.players - PLAYERS_PRIMARY) * 0.5, 30)
    else:
        score += c.players  # 30-49は参加者数分

    # ハンド数 (中央が理想)
    mid = (MIN_HANDS + MAX_HANDS) / 2  # 30
    hand_dist = abs(c.hands - mid)
    score += max(20 - hand_dist, 0)

    # プレイヤー優位性
    if c.hands > 0:
        p_ratio = c.p_count / c.hands
        score += (p_ratio - 0.5) * 40  # プレイヤー率60%なら+4点

    return score


# === メイン選定ロジック ===

class TableSelector:
    def __init__(self, scraper):
        self.scraper = scraper
        self._last_primary_check_ts = 0.0
        self._primary_wait_start: float | None = None
        self.excluded_table_ids: set[str] = set()  # ユーザー分散TODO用

    def find_best_table(self, fixed_name: str = None) -> TableCandidate | None:
        """現在の状況で最適なテーブルを選ぶ。なければNone。

        fixed_name: 指定するとそのテーブル名を含むテーブルのみ候補にする (検証モード用)
        """
        configs = self.scraper.get_all_table_configs()
        players = self.scraper.get_players_count()

        candidates: list[TableCandidate] = []
        debug_stats = {"excluded": 0, "no_players_data": 0, "low_players": 0,
                       "dragon": 0, "bad_hands": 0, "bad_pb_ratio": 0}

        for tid, cfg in configs.items():
            if tid in self.excluded_table_ids:
                continue

            reason = is_excluded(cfg)
            if reason:
                debug_stats["excluded"] += 1
                continue

            title = cfg.get("title", tid)
            # Fixed table filter (verification mode)
            if fixed_name and fixed_name.lower() not in title.lower():
                continue
            p_count = players.get(tid, None)
            if p_count is None:
                debug_stats["no_players_data"] += 1
                continue

            # 履歴取得
            raw = self.scraper.get_raw_history(tid)
            hands, p, b, tie, last5 = analyze_history(raw)

            # Fixed table (verification) mode: bypass dragon / hands / pb filters
            # — we are locked to this specific table regardless of its stats.
            if not fixed_name:
                # ③ ドラゴン除外
                if has_banker_dragon(raw):
                    debug_stats["dragon"] += 1
                    continue

                # ⑥ ハンド進行度
                if hands < MIN_HANDS or hands > MAX_HANDS:
                    debug_stats["bad_hands"] += 1
                    continue

                # ⑥ プレイヤー > バンカー
                if p <= b:
                    debug_stats["bad_pb_ratio"] += 1
                    continue

            candidates.append(TableCandidate(
                table_id=tid,
                title=title,
                players=p_count,
                hands=hands,
                p_count=p,
                b_count=b,
                tie_count=tie,
                last_5=last5,
            ))

        # 参加者数しきい値で段階的フィルタ
        now = time.time()
        primary_cands = [c for c in candidates if c.players >= PLAYERS_PRIMARY]
        relaxed_cands = [c for c in candidates if c.players >= PLAYERS_RELAXED]

        logger.info(
            f"[selector] configs={len(configs)} candidates={len(candidates)} "
            f"primary(>={PLAYERS_PRIMARY}p)={len(primary_cands)} "
            f"relaxed(>={PLAYERS_RELAXED}p)={len(relaxed_cands)} "
            f"debug={debug_stats}"
        )

        chosen_list: list[TableCandidate] = []
        if primary_cands:
            chosen_list = primary_cands
            self._primary_wait_start = None
        else:
            # primaryがない → 1分待機ロジック
            if self._primary_wait_start is None:
                self._primary_wait_start = now
                logger.info(f"[selector] No primary(>={PLAYERS_PRIMARY}p) tables. Waiting {RELAX_WAIT_SECONDS}s...")
                return None
            elif now - self._primary_wait_start < RELAX_WAIT_SECONDS:
                remaining = RELAX_WAIT_SECONDS - (now - self._primary_wait_start)
                logger.info(f"[selector] Still waiting for primary ({remaining:.0f}s left)")
                return None
            else:
                logger.info("[selector] Relaxing to 30p threshold")
                if relaxed_cands:
                    chosen_list = relaxed_cands
                else:
                    logger.info("[selector] No relaxed candidates either. Skipping.")
                    return None

        # スコア計算 + 選択
        for c in chosen_list:
            c.score = compute_score(c)
        chosen_list.sort(key=lambda x: -x.score)

        best = chosen_list[0]
        logger.info(f"[selector] BEST: {best} score={best.score:.1f}")
        if len(chosen_list) > 1:
            logger.info("[selector] Top 5:")
            for i, c in enumerate(chosen_list[:5]):
                logger.info(f"  {i+1}. {c} score={c.score:.1f}")
        return best

    def should_exit_table(self, table_id: str) -> str | None:
        """入場後に条件が崩れたかチェック。退出すべき理由を返す (問題なければNone)"""
        players = self.scraper.get_players_count()
        p_count = players.get(table_id, 0)
        raw = self.scraper.get_raw_history(table_id)

        # 参加者数崩壊
        if p_count < PLAYERS_RELAXED:
            return f"players dropped to {p_count}"

        # ドラゴン発生
        if has_banker_dragon(raw):
            return "banker dragon detected"

        return None
