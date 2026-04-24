"""ba GUI v2 — ストラテジーエンジン

リアルタイム pattern 判定 + エントリー条件チェック + BET 推奨 + エグジット判定。
友人戦略 (2026-04-24 統合版) を厳格 classifier で実装。
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pattern_classifier import compute_big_road_columns

BIAS_THRESHOLD = 10


def max_consecutive(col_lens, target=1):
    mx = run = 0
    for L in col_lens:
        if L == target:
            run += 1
            mx = max(mx, run)
        else:
            run = 0
    return mx


def trailing_ones(col_lens):
    n = 0
    for L in reversed(col_lens):
        if L == 1:
            n += 1
        else:
            break
    return n


def classify_strict(seq: str) -> dict:
    """bead road seq を pattern 分類、詳細指標付き"""
    cols = compute_big_road_columns(seq)
    col_lens = [len(c) for c in cols]
    n = len(col_lens)
    p_cnt = seq.count('P')
    b_cnt = seq.count('B')
    t_cnt = seq.count('T')

    info = {
        "pattern": "不明",
        "reason": "",
        "n_cols": n,
        "n_hands_nont": p_cnt + b_cnt,
        "n_hands_total": len(seq),
        "p_cnt": p_cnt,
        "b_cnt": b_cnt,
        "t_cnt": t_cnt,
        "b_lead": b_cnt - p_cnt,
        "col_lens": col_lens,
        "features": {},
    }

    if n < 5:
        info["pattern"] = "不明"
        info["reason"] = f"列数不足 ({n}<5)"
        return info

    if abs(p_cnt - b_cnt) >= BIAS_THRESHOLD:
        info["pattern"] = "偏り"
        info["reason"] = f"P-B差={abs(p_cnt-b_cnt)} ≥ {BIAS_THRESHOLD}"
        return info

    n_long5 = sum(1 for L in col_lens if L >= 5)
    n_long4 = sum(1 for L in col_lens if L >= 4)
    pct_le2 = sum(1 for L in col_lens if L <= 2) / n
    pct_le3 = sum(1 for L in col_lens if L <= 3) / n
    pct_1   = sum(1 for L in col_lens if L == 1) / n
    pct_2   = sum(1 for L in col_lens if L == 2) / n
    single_run = max_consecutive(col_lens, 1)
    is_dense_strict = single_run == 0
    is_dense_loose = single_run <= 1

    info["features"] = {
        "n_long5": n_long5,
        "n_long4": n_long4,
        "pct_le2": round(pct_le2 * 100, 1),
        "pct_le3": round(pct_le3 * 100, 1),
        "pct_1":   round(pct_1 * 100, 1),
        "pct_2":   round(pct_2 * 100, 1),
        "single_run": single_run,
        "is_dense_strict": is_dense_strict,
        "is_dense_loose": is_dense_loose,
        "trailing_ones": trailing_ones(col_lens),
    }

    if n_long5 >= 2 and is_dense_loose:
        info["pattern"] = "縦面5+密集"
        info["reason"] = f"5+連 {n_long5}個 + 横空き ≤1"
    elif n_long5 == 0 and n_long4 >= 1 and is_dense_strict:
        info["pattern"] = "縦面4以下密集"
        info["reason"] = f"5+連なし + 4段 {n_long4}個 + 横空き 0"
    elif n_long4 == 0 and pct_le2 >= 0.85:
        # テレコ: 1落が支配的 (≥65%)
        if pct_1 >= 0.65:
            info["pattern"] = "テレコ"
            info["reason"] = f"1落 {pct_1*100:.0f}% — 交互パターン (逆張り)"
        else:
            has_consec_2 = any(
                i + 1 < len(col_lens) and col_lens[i] == 2 and col_lens[i + 1] == 2
                for i in range(len(col_lens))
            )
            has_mix = pct_2 >= 0.20 and pct_1 >= 0.20  # ニコイチ: 2落と1落が混在
            if has_consec_2 or has_mix:
                info["pattern"] = "ニコニコ・ニコイチ"
                sub = "ニコニコ" if has_consec_2 else "ニコイチ"
                info["reason"] = f"4+連なし + ≤2段 {pct_le2*100:.0f}% ({sub})"
            else:
                info["pattern"] = "不規則"
                info["reason"] = "短列中心だが規則性なし"
    elif n_long5 >= 1 and pct_le2 >= 0.40:
        info["pattern"] = "ブリッジ"
        info["reason"] = f"5+連 {n_long5}個 + ≤2段 {pct_le2*100:.0f}%"
    else:
        info["pattern"] = "不規則"
        info["reason"] = "どの pattern にも該当せず"

    return info


def check_entry(seq: str, info: dict) -> tuple[bool, str]:
    """エントリー条件チェック"""
    pattern = info["pattern"]
    n_cols = info["n_cols"]
    col_lens = info["col_lens"]

    if pattern in ("縦面5+密集", "縦面4以下密集") and n_cols >= 3:
        return True, f"{pattern} 確認 (3列目以降で即エントリー)"

    if pattern == "テレコ" and n_cols >= 5:
        return True, f"テレコ確認 (5列以上、逆張り戦略)"

    if pattern == "ニコニコ・ニコイチ" and n_cols >= 5:
        first5 = col_lens[:5]
        has_4p = any(L >= 4 for L in first5)
        has_c2 = any(
            i + 1 < len(first5) and first5[i] == 2 and first5[i + 1] == 2
            for i in range(len(first5))
        )
        if not has_4p and has_c2:
            return True, "5列目までに 4段なし + 2落連続あり"
        if info["n_hands_nont"] >= 20:
            first20_seq = []
            count = 0
            for ch in seq:
                if ch in ('P', 'B'):
                    first20_seq.append(ch)
                    count += 1
                    if count == 20:
                        break
            lens20 = [len(c) for c in compute_big_road_columns("".join(first20_seq))]
            ge3 = sum(1 for L in lens20 if L >= 3)
            le2 = sum(1 for L in lens20 if L <= 2)
            if le2 + ge3 > 0 and le2 / (le2 + ge3) >= 0.70:
                return True, f"20目 短列率 {le2/(le2+ge3)*100:.0f}% ≥ 70%"
        return False, "5列目までに 2落連続なし & 20目条件未達"

    if pattern == "不明":
        return False, f"判定中 ({n_cols}/5 列)"
    if pattern in ("ブリッジ", "不規則", "偏り"):
        return False, f"{pattern} は BET 対象外"
    return False, f"{pattern} はエントリー条件未定義"


def decide_bet(seq: str, entry_pattern: str) -> dict:
    """現在の seq と 固定された entry_pattern から BET 推奨を返す"""
    cols = compute_big_road_columns(seq)
    depth = len(cols[-1]) if cols else 0
    prev = None
    for ch in reversed(seq):
        if ch in ('P', 'B'):
            prev = ch
            break

    action = "LOOK"
    side = None
    reason = ""
    amount_hint = 0  # $ hint (placeholder, SEQ tracker が正式)

    if entry_pattern == "テレコ":
        if prev == 'B':
            action, side, reason = "BET", "P", "テレコ逆張り (B出現 → P BET)"
        else:
            reason = f"LOOK (P出現 → B期待だが P only のため見送り)"
    elif entry_pattern == "縦面5+密集":
        if prev == 'P':
            action, side, reason = "BET", "P", "MF (縦面5+, 前手 P)"
        else:
            reason = f"LOOK (前手 {prev or 'なし'}, P 連続待ち)"
    elif entry_pattern == "縦面4以下密集":
        if depth == 1 and prev == 'P':
            action, side, reason = "BET", "P", "MF 2落狙い (新列1段目 P)"
        else:
            reason = "LOOK (新列1段目 P でない)"
    elif entry_pattern == "ニコニコ・ニコイチ":
        if depth == 1 and prev == 'B':
            if len(cols) >= 2 and len(cols[-2]) == 2:
                action, side, reason = "BET", "P", "2落後 1落狙い (直前列2落, 新列1段目 B)"
            else:
                reason = "LOOK (直前列が 2落 でない)"
        else:
            reason = "LOOK (新列1段目 B 待ち)"
    else:
        reason = f"pattern={entry_pattern} は未対応"

    return {"action": action, "side": side, "reason": reason}


VALID_PATTERNS = {"縦面5+密集", "縦面4以下密集", "ニコニコ・ニコイチ", "テレコ"}
EXIT_PATTERNS  = {"不規則", "偏り", "ブリッジ"}


def check_exit(info: dict, entry_pattern: str, losing_streak: int) -> tuple[bool, str]:
    """エグジット判定。退室は不規則/偏り/ブリッジ or 2連敗のみ。
    有効パターンへの変化はパターン切替で継続 (呼び出し元が entry_pattern を更新する)。
    """
    if losing_streak >= 2:
        return True, "2連敗 → 退室"
    if info["pattern"] in EXIT_PATTERNS:
        return True, f"パターン崩れ ({info['pattern']}) → 退室"
    return False, ""


# =================================================================
# 予告 (リーチ前リーチ) + 確信度
# =================================================================

def _count_trailing(seq: str, ch: str) -> int:
    n = 0
    for c in reversed(seq):
        if c == ch:
            n += 1
        elif c == 'T':
            continue
        else:
            break
    return n


def forecast(seq: str, info: dict, entry_pattern: str | None, pending_bet: dict | None = None,
             enter_flag: bool = False, enter_reason: str = "") -> dict:
    """現状 + 次手予告 + 確信度

    返却: {
      "situation": 今テーブルはどういう状態か,
      "next": 次に何が起きれば BET 可能か (リーチ前リーチ含む),
      "level": "imminent" | "reach" | "watching" | "waiting" | "exit" | "pending",
      "confidence": 0-100 | None
    }
    """
    cols = compute_big_road_columns(seq)
    col_lens = [len(c) for c in cols]
    n_cols = len(cols)
    depth = col_lens[-1] if col_lens else 0
    prev = None
    for c in reversed(seq):
        if c in ('P', 'B'):
            prev = c
            break

    # ① BET 実行中 (結果待ち)
    if pending_bet:
        return {
            "situation": f"💰 BET 実行中: {pending_bet['side']} ${pending_bet['unit']:.0f}",
            "next": "次ハンドで勝敗が自動判定されます",
            "level": "pending",
            "confidence": None,
        }

    pat = info["pattern"]

    # ② 未入室 — どういう状態か + いつエントリー可能か
    if not entry_pattern:
        if pat == "不明":
            return {
                "situation": f"判定待ち ({n_cols}/5 列必要)",
                "next": "もう少し hand が溜まれば判定開始",
                "level": "waiting",
                "confidence": None,
            }
        if pat in ("ブリッジ", "不規則", "偏り"):
            return {
                "situation": f"❌ {pat} — 友人戦略対象外",
                "next": f"このテーブルは見送り ({info['reason']})",
                "level": "exit",
                "confidence": 10,
            }
        if enter_flag:
            return {
                "situation": f"✅ {pat} 検知済み",
                "next": f"🎯 エントリー条件成立: {enter_reason}",
                "level": "reach",
                "confidence": 65,
            }
        # エントリー対象パターンだけど条件未達
        if pat == "テレコ":
            return {
                "situation": f"⭐ テレコ候補 ({n_cols}/5 列)",
                "next": "5 列以上でエントリー可能 (B出現時に P BET)",
                "level": "watching",
                "confidence": 40,
            }
        if pat == "ニコニコ・ニコイチ":
            if n_cols < 5:
                return {
                    "situation": f"⭐ {pat} 候補 ({n_cols}/5 列)",
                    "next": f"5 列目までに 2 落連続が出ればエントリー可能",
                    "level": "watching",
                    "confidence": 40,
                }
            return {
                "situation": f"⭐ {pat} 候補",
                "next": "5 列目までの条件未達。20 目の 3:7 ルールを待つ",
                "level": "watching",
                "confidence": 30,
            }
        return {
            "situation": f"{pat} 候補",
            "next": "3 列目以降の判定待ち",
            "level": "watching",
            "confidence": 30,
        }

    # ③ 入室中 — pattern 別の予告
    if entry_pattern == "テレコ":
        if prev == 'B':
            return {
                "situation": "🎯 B 出現 — テレコ逆張りチャンス",
                "next": "🟢 次ハンドに P BET (逆張り)",
                "level": "imminent",
                "confidence": 55,
            }
        else:
            return {
                "situation": "⏳ P 出現 — B 出現待ち",
                "next": "B が出たら次ハンド P BET",
                "level": "reach",
                "confidence": 40,
            }

    if entry_pattern == "縦面5+密集":
        if prev == 'P':
            streak = _count_trailing(seq, 'P')
            conf = min(51 + streak * 3, 75)  # streak=3→60, streak=8→75
            return {
                "situation": f"🔥 P {streak} 連続中 — 縦流れ支配",
                "next": f"🟢 次ハンドが P なら BET 継続 (MF)",
                "level": "imminent",
                "confidence": conf,
            }
        else:
            b_streak = _count_trailing(seq, 'B')
            return {
                "situation": f"B {b_streak} 連続中 — Player only のため見送り",
                "next": f"⏳ P 出現待ち。P が出たら次から BET 開始",
                "level": "watching",
                "confidence": 30,
            }

    if entry_pattern == "縦面4以下密集":
        if depth == 1 and prev == 'P':
            return {
                "situation": "🎯 新列 P 1 段目 — 2 落狙いチャンス",
                "next": "🟢 次ハンド P なら BET 成功 (MF 2 落狙い)",
                "level": "imminent",
                "confidence": 55,
            }
        if depth == 1 and prev == 'B':
            return {
                "situation": "新列 B 1 段目 — Player only のため見送り",
                "next": "⏳ 次列が P で始まれば 2 落狙い発動",
                "level": "reach",
                "confidence": 40,
            }
        if depth >= 2:
            return {
                "situation": f"現列 {prev} depth={depth} — 伸び切り中",
                "next": f"新列遷移待ち ({prev} が終われば仕切り直し)",
                "level": "watching",
                "confidence": 25,
            }
        return {
            "situation": "状態判定中",
            "next": "次手待ち",
            "level": "watching",
            "confidence": 20,
        }

    if entry_pattern == "ニコニコ・ニコイチ":
        prev_col_len = col_lens[-2] if len(col_lens) >= 2 else 0
        if depth == 1 and prev == 'B' and prev_col_len == 2:
            return {
                "situation": "🎯 直前列 2 段 + 新列 B 1 段目 — 理想形",
                "next": "🟢 次ハンド P なら BET 成功 (2 落後 1 落狙い)",
                "level": "imminent",
                "confidence": 60,
            }
        if depth == 1 and prev == 'B':
            return {
                "situation": f"新列 B 1 段目 / 直前列 {prev_col_len} 段",
                "next": "⏳ 直前列が 2 段である必要あり。条件不一致",
                "level": "watching",
                "confidence": 25,
            }
        if depth == 2 and col_lens[-1] == 2:
            # 現列 2 段完成目前
            return {
                "situation": f"📢 現列 {prev} 2 段目 (2 落完成直前)",
                "next": f"🎯 リーチ前リーチ: この列が 2 段で終われば、次列 B で BET チャンス",
                "level": "reach",
                "confidence": 55,
            }
        if depth == 1 and prev == 'P':
            return {
                "situation": "新列 P 1 段目 — P only 戦略のため待機",
                "next": "新列 P 伸び切り後、次の B 列を狙う",
                "level": "watching",
                "confidence": 30,
            }
        return {
            "situation": f"現列 {prev} depth={depth}",
            "next": "新列遷移待ち",
            "level": "watching",
            "confidence": 25,
        }

    return {
        "situation": f"pattern: {entry_pattern}",
        "next": "判定ロジック未実装",
        "level": "watching",
        "confidence": None,
    }
