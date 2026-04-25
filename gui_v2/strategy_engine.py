"""ba GUI v2 — ストラテジーエンジン v3 (友人記事準拠 6 分類)

分類:
  ① 強い横流れ (テレコ)              → RF (前手 B → P BET)
  ② 横流れ (ニコニコ・ニコイチ)       → RF
  ③ 縦流れ (5+連 ≥ 3 / 5+連 2+密集)   → MF (前手 P → P BET)
  ④ 縦横流れ (4落止まり / サンイチ)    → 退室 (判断不可)
  ⑤ ブリッジ (テレコ → 縦面 5+ 遷移)  → 退室
  ⑥ 不規則 (シュー全体で切替 ≥ 3 回)  → 退室

閾値 (2026-04-25 user 確認済):
  - ① テレコ:    1段比率 ≥ 70%
  - ② 横流れ:    ≤2段比率 ≥ 70%
  - ③ 縦流れ:    5+連 ≥ 3  OR  (5+連 ≥ 2 AND 横空き ≤1)
  - ⑤ ブリッジ:  シュー列数の前半 50% / 後半 50%
  - ⑥ 不規則:    pattern 切替 ≥ 3 回 (5列窓 sliding)
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pattern_classifier import compute_big_road_columns

# ========== 閾値 ==========
TEREKO_PCT_1     = 0.70   # ① 強い横流れ (テレコ)
YOKO_PCT_LE2     = 0.70   # ② 横流れ
TATE_N5_STRICT   = 3      # ③ 縦流れ (絶対条件)
TATE_N5_DENSE    = 2      # ③ 縦流れ密集
DENSE_MAX_GAP    = 1      # 密集: 1段の連続 ≤ 1
BRIDGE_HALF_PCT  = 0.50   # ⑤ ブリッジ前後分割比
IRREGULAR_TRANS  = 3      # ⑥ 不規則
WINDOW_TRANS     = 5      # 切替検出窓
BIAS_THRESHOLD   = 10     # 偏り (display only)

VALID_PATTERNS = {"縦流れ", "横流れ", "強い横流れ"}
EXIT_PATTERNS  = {"縦横流れ", "ブリッジ", "不規則"}


# ========== 補助関数 ==========

def max_consecutive(col_lens: list[int], target: int = 1) -> int:
    """連続する target 長の列の最大連続数"""
    mx = run = 0
    for L in col_lens:
        if L == target:
            run += 1; mx = max(mx, run)
        else:
            run = 0
    return mx


def trailing_ones(col_lens: list[int]) -> int:
    n = 0
    for L in reversed(col_lens):
        if L == 1: n += 1
        else: break
    return n


def _has_nikoniko(col_lens: list[int]) -> bool:
    """ニコニコ: 2段が 2 列以上連続 (BB,PP,BB のような)"""
    return max_consecutive(col_lens, 2) >= 2


def _has_nikoichi(col_lens: list[int]) -> bool:
    """ニコイチ: (2,1) or (1,2) のペアが 3 ペア以上連続"""
    if len(col_lens) < 4:
        return False
    pairs = 0
    for i in range(len(col_lens) - 1):
        a, b = col_lens[i], col_lens[i + 1]
        if (a == 2 and b == 1) or (a == 1 and b == 2):
            pairs += 1
            if pairs >= 3:
                return True
        else:
            pairs = 0
    return False


def _has_sanichi(col_lens: list[int]) -> bool:
    """サンイチ: (3,1) or (1,3) のペアが 3 ペア以上連続"""
    if len(col_lens) < 6:
        return False
    pairs = 0
    for i in range(len(col_lens) - 1):
        a, b = col_lens[i], col_lens[i + 1]
        if (a == 3 and b == 1) or (a == 1 and b == 3):
            pairs += 1
            if pairs >= 3:
                return True
        else:
            pairs = 0
    return False


def _classify_segment(col_lens: list[int]) -> str:
    """セグメント (5列窓) 簡易分類 — 切替検出用"""
    n = len(col_lens)
    if n < 3:
        return "?"
    n5 = sum(1 for L in col_lens if L >= 5)
    n4 = sum(1 for L in col_lens if L >= 4)
    p_le2 = sum(1 for L in col_lens if L <= 2) / n
    p_1 = sum(1 for L in col_lens if L == 1) / n
    if n5 >= 2:
        return "縦"
    if n5 == 0 and n4 == 0 and p_1 >= 0.70:
        return "強横"
    if n5 == 0 and n4 == 0 and p_le2 >= 0.70:
        return "横"
    if n5 == 0 and n4 >= 1:
        return "縦横"
    return "不"


def _count_pattern_changes(col_lens: list[int]) -> int:
    """シュー全体を 5 列窓で sliding して pattern 切替回数を数える"""
    if len(col_lens) < 10:
        return 0
    changes = 0
    prev = None
    step = 5
    for i in range(0, len(col_lens) - WINDOW_TRANS + 1, step):
        win = col_lens[i:i + WINDOW_TRANS]
        cat = _classify_segment(win)
        if cat == "?":
            continue
        if prev and cat != prev:
            changes += 1
        prev = cat
    return changes


# ========== メイン分類 ==========

def classify_strict(seq: str) -> dict:
    """6 分類 (友人記事準拠)"""
    cols = compute_big_road_columns(seq)
    col_lens = [len(c) for c in cols]
    n_cols = len(col_lens)
    p_cnt = seq.count('P')
    b_cnt = seq.count('B')
    t_cnt = seq.count('T')

    # 特徴量計算
    n3 = sum(1 for L in col_lens if L >= 3)
    n4 = sum(1 for L in col_lens if L >= 4)
    n5 = sum(1 for L in col_lens if L >= 5)
    pct_1 = (sum(1 for L in col_lens if L == 1) / n_cols) if n_cols else 0
    pct_le2 = (sum(1 for L in col_lens if L <= 2) / n_cols) if n_cols else 0
    single_run = max_consecutive(col_lens, 1)
    has_nikoniko = _has_nikoniko(col_lens)
    has_nikoichi = _has_nikoichi(col_lens)
    has_sanichi = _has_sanichi(col_lens)
    n_changes = _count_pattern_changes(col_lens)

    info = {
        "pattern": "不明",
        "sub": "",
        "reason": "",
        "n_cols": n_cols,
        "n_hands_nont": p_cnt + b_cnt,
        "n_hands_total": len(seq),
        "p_cnt": p_cnt, "b_cnt": b_cnt, "t_cnt": t_cnt,
        "b_lead": b_cnt - p_cnt,
        "col_lens": col_lens,
        "features": {
            "n3": n3, "n4": n4, "n5": n5,
            "pct_1":   round(pct_1 * 100, 1),
            "pct_le2": round(pct_le2 * 100, 1),
            "single_run": single_run,
            "has_nikoniko": has_nikoniko,
            "has_nikoichi": has_nikoichi,
            "has_sanichi":  has_sanichi,
            "trailing_ones": trailing_ones(col_lens),
            "n_changes": n_changes,
            "is_dense":  single_run <= DENSE_MAX_GAP,
        },
    }

    if n_cols < 5:
        info["reason"] = f"列数不足 ({n_cols}/5)"
        return info

    # ⑥ 不規則: シュー全体で 3 回以上切替 (最優先)
    if n_changes >= IRREGULAR_TRANS:
        info["pattern"] = "不規則"
        info["reason"] = f"パターン切替 {n_changes} 回 (高速回収シュー疑い)"
        return info

    # ⑤ ブリッジ: 前半テレコ系 → 後半 5+連 出現
    half = max(int(n_cols * BRIDGE_HALF_PCT), 3)
    front = col_lens[:half]
    back = col_lens[half:]
    front_short = bool(front) and all(L <= 2 for L in front) and len(front) >= 3
    back_has_5 = bool(back) and any(L >= 5 for L in back)
    if front_short and back_has_5:
        info["pattern"] = "ブリッジ"
        info["reason"] = f"前半 {half}列テレコ → 後半 5+連 出現 ({sum(1 for L in back if L>=5)}個)"
        return info

    # ③ 縦流れ
    if n5 >= TATE_N5_STRICT:
        info["pattern"] = "縦流れ"
        info["sub"] = "5+連3回以上"
        info["reason"] = f"5+連 {n5} 回 (記事原文の縦流れ確定)"
        return info
    if n5 >= TATE_N5_DENSE and single_run <= DENSE_MAX_GAP:
        info["pattern"] = "縦流れ"
        info["sub"] = "5+連2回 + 密集"
        info["reason"] = f"5+連 {n5} 回 + 横空き ≤{DENSE_MAX_GAP} (密集型)"
        return info

    # ① 強い横流れ (テレコ)
    if n4 == 0 and n5 == 0 and pct_1 >= TEREKO_PCT_1:
        info["pattern"] = "強い横流れ"
        info["sub"] = "テレコ"
        info["reason"] = f"1段比率 {pct_1*100:.0f}% (≥{TEREKO_PCT_1*100:.0f}%) + 4+連なし"
        return info

    # ② 横流れ (ニコニコ・ニコイチ)
    if n4 == 0 and n5 == 0 and pct_le2 >= YOKO_PCT_LE2:
        info["pattern"] = "横流れ"
        if has_nikoniko:
            info["sub"] = "ニコニコ"
        elif has_nikoichi:
            info["sub"] = "ニコイチ"
        else:
            info["sub"] = "短列混在"
        info["reason"] = f"≤2段比率 {pct_le2*100:.0f}% ({info['sub']})"
        return info

    # ④ 縦横流れ (4落止まり / サンイチ)
    if n5 == 0 and n4 >= 1:
        info["pattern"] = "縦横流れ"
        info["sub"] = "4落止まり"
        info["reason"] = f"4+連 {n4} 個あるが 5+連=0 (4落で止まる)"
        return info
    if has_sanichi:
        info["pattern"] = "縦横流れ"
        info["sub"] = "サンイチ"
        info["reason"] = "3段と1段の交互パターン (3 ペア+) 検出"
        return info

    # ⑥ 不規則 (どれにも該当しない混在)
    info["pattern"] = "不規則"
    info["reason"] = (f"分類条件外 — 5+連{n5}, 4+連{n4}, "
                     f"≤2段{pct_le2*100:.0f}%, 1段{pct_1*100:.0f}%")
    return info


# ========== エントリー / BET / 退室 ==========

def check_entry(seq: str, info: dict) -> tuple[bool, str]:
    pat = info["pattern"]
    n = info["n_cols"]
    sub = info.get("sub", "")
    if pat in VALID_PATTERNS:
        return True, f"{pat}{f' ({sub})' if sub else ''} 確定"
    if pat == "不明":
        return False, f"判定中 ({n}/5列)"
    return False, f"{pat} は退室対象"


def _last_pb(seq: str) -> str | None:
    for c in reversed(seq):
        if c in ('P', 'B'): return c
    return None


def _trailing_streak(seq: str, ch: str) -> int:
    n = 0
    for c in reversed(seq):
        if c == ch: n += 1
        elif c == 'T': continue
        else: break
    return n


def decide_bet(seq: str, entry_pattern: str) -> dict:
    """BET 判断: 縦=MF, 横/強い横=RF, それ以外=LOOK"""
    prev = _last_pb(seq)

    if entry_pattern == "縦流れ":
        if prev == 'P':
            return {"action": "BET", "side": "P", "reason": "MF (前手 P → P 連続狙い)"}
        return {"action": "LOOK", "side": None,
                "reason": f"LOOK (前手 {prev or '?'} → P 出現待ち)"}

    if entry_pattern in ("横流れ", "強い横流れ"):
        if prev == 'B':
            return {"action": "BET", "side": "P", "reason": "RF (前手 B → P 逆張り)"}
        return {"action": "LOOK", "side": None,
                "reason": f"LOOK (前手 {prev or '?'} → B 出現待ち)"}

    return {"action": "LOOK", "side": None, "reason": f"pattern={entry_pattern} は対象外"}


def check_exit(info: dict, entry_pattern: str, losing_streak: int) -> tuple[bool, str]:
    """退室判定 — pattern が ④⑤⑥ (縦横流れ/ブリッジ/不規則) に変化した時のみ自動退室

    user の指示 (2026-04-25):
      - 連敗による自動退室は不要 (user 自身で判断)
      - 横空き等による自動退室も不要 (user 自身で判断)
      - 「エントリーの光が消えた = 不規則・ブリッジ・縦横流れに変化」の時だけ退室ボタンを光らせる
    """
    pat = info["pattern"]
    if pat in EXIT_PATTERNS:
        return True, f"{pat} 化 → 退室推奨"
    return False, ""


# ========== 予告 (リーチ前リーチ) ==========

def forecast(seq: str, info: dict, entry_pattern: str | None,
             pending_bet: dict | None = None,
             enter_flag: bool = False, enter_reason: str = "") -> dict:
    pat = info["pattern"]
    sub = info.get("sub", "")
    n = info["n_cols"]
    prev = _last_pb(seq)

    if pending_bet:
        return {
            "situation": f"💰 BET 実行中: {pending_bet['side']} ${pending_bet['unit']:.0f}",
            "next": "次ハンドで勝敗判定",
            "level": "pending", "confidence": None,
        }

    # 未入室時の表示
    if not entry_pattern:
        if pat == "不明":
            return {
                "situation": f"⏳ 判定待ち ({n}/5列)",
                "next": "手数が増えれば判定開始",
                "level": "waiting", "confidence": None,
            }
        if pat == "縦流れ":
            return {
                "situation": f"✅ 縦流れ ({sub})",
                "next": f"🎯 MF 入室 OK — {info['reason']}",
                "level": "reach", "confidence": 65,
            }
        if pat == "横流れ":
            return {
                "situation": f"✅ 横流れ ({sub})",
                "next": f"🎯 RF 入室 OK — {info['reason']}",
                "level": "reach", "confidence": 60,
            }
        if pat == "強い横流れ":
            return {
                "situation": f"✅ 強い横流れ ({sub})",
                "next": f"🎯 RF 入室 OK — {info['reason']}",
                "level": "reach", "confidence": 65,
            }
        # 退室カテゴリ ④⑤⑥
        return {
            "situation": f"❌ {pat}{f' ({sub})' if sub else ''}",
            "next": f"🚪 退室推奨 — {info['reason']}",
            "level": "exit", "confidence": 15,
        }

    # 入室中の予告
    if entry_pattern == "縦流れ":
        if prev == 'P':
            streak = _trailing_streak(seq, 'P')
            return {
                "situation": f"🔥 P {streak}連続中 — 縦流れ ({sub})",
                "next": "🟢 次ハンド P → P BET (MF)",
                "level": "imminent", "confidence": min(55 + streak * 2, 75),
            }
        b_streak = _trailing_streak(seq, 'B')
        return {
            "situation": f"B {b_streak}連続中 — 縦流れだが見送り中",
            "next": "⏳ P 出現したら次ハンドから MF BET",
            "level": "watching", "confidence": 35,
        }

    if entry_pattern in ("横流れ", "強い横流れ"):
        if prev == 'B':
            return {
                "situation": f"🎯 B 出現 — {entry_pattern} ({sub}) RF チャンス",
                "next": "🟢 次ハンド P → P BET (RF 逆張り)",
                "level": "imminent",
                "confidence": 60 if entry_pattern == "強い横流れ" else 55,
            }
        return {
            "situation": f"P 出現 — B 待ち ({sub})",
            "next": "⏳ B が出たら RF BET",
            "level": "reach", "confidence": 40,
        }

    return {
        "situation": f"pattern: {entry_pattern}",
        "next": "判定中",
        "level": "watching", "confidence": None,
    }
