"""ba GUI v2 — ストラテジーエンジン

3分類 (直近10列ウィンドウで判定):
  縦流れ : 長い列が支配的 → MF 順張り (P 連続中なら P BET)
  横流れ : 短い列が支配的 → RF 逆張り (B 出現後に P BET)
  不規則 : どちらとも言えない → BET しない
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pattern_classifier import compute_big_road_columns

# ========== 定数 ==========
BIAS_THRESHOLD  = 10    # P-B 差がこれ以上 = 偏り (縦流れ扱い)
WINDOW_COLS     = 10    # 直近 N 列だけで判定
# 縦流れ閾値 (ウィンドウ内)
TATE_AVG_ENTRY  = 4.0   # エントリー基準: 平均列長 ≥ 4.0 (強い縦流れ)
TATE_AVG_SHOW   = 2.5   # 表示基準: 平均列長 ≥ 2.5 (縦流れと分類)
TATE_N5_ENTRY   = 2     # 5段以上の列 ≥ 2 でもエントリー (密集)
# 横流れ閾値 (ウィンドウ内)
YOKO_PCT_ENTRY  = 0.80  # エントリー基準: ≤2段の割合 ≥ 80% (強い横流れ)
YOKO_PCT_SHOW   = 0.65  # 表示基準: ≤2段の割合 ≥ 65% (横流れと分類)
YOKO_NLONG5_MAX = 0     # 5段以上なし

VALID_PATTERNS = {"縦流れ", "横流れ"}
EXIT_PATTERNS  = {"不規則"}


def _compute_features(col_lens: list[int]) -> dict:
    n = len(col_lens)
    if n == 0:
        return {"n": 0, "avg": 0, "n3": 0, "n4": 0, "n5": 0,
                "pct_le2": 0, "pct_1": 0, "pct_2": 0, "has_consec_2": False,
                "trailing_ones": 0}
    avg  = sum(col_lens) / n
    n3   = sum(1 for L in col_lens if L >= 3)
    n4   = sum(1 for L in col_lens if L >= 4)
    n5   = sum(1 for L in col_lens if L >= 5)
    p2   = sum(1 for L in col_lens if L <= 2) / n
    p1   = sum(1 for L in col_lens if L == 1) / n
    p22  = sum(1 for L in col_lens if L == 2) / n
    has_consec_2 = any(
        col_lens[i] == 2 and col_lens[i+1] == 2
        for i in range(n-1)
    )
    trailing_ones = 0
    for L in reversed(col_lens):
        if L == 1: trailing_ones += 1
        else: break
    return {
        "n": n, "avg": avg, "n3": n3, "n4": n4, "n5": n5,
        "pct_le2": round(p2 * 100, 1),
        "pct_1":   round(p1 * 100, 1),
        "pct_2":   round(p22 * 100, 1),
        "has_consec_2": has_consec_2,
        "trailing_ones": trailing_ones,
    }


def _sub_pattern(f: dict) -> str:
    if f["n5"] >= 2:         return "密集"
    if f["n5"] >= 1:         return "ドラゴン"
    if f["n4"] >= 2:         return "縦面4密集"
    if f["n4"] >= 1:         return "縦流れ"
    if f["pct_1"] >= 60:     return "テレコ"
    if f["has_consec_2"]:    return "ニコニコ"
    if f["pct_2"] >= 30:     return "ニコイチ"
    return "横流れ"


def classify_strict(seq: str) -> dict:
    """直近 WINDOW_COLS 列のみで 3 分類"""
    all_cols   = compute_big_road_columns(seq)
    all_lens   = [len(c) for c in all_cols]
    n_cols_all = len(all_cols)
    p_cnt      = seq.count('P')
    b_cnt      = seq.count('B')
    t_cnt      = seq.count('T')

    # 直近ウィンドウ
    win_lens = all_lens[-WINDOW_COLS:] if n_cols_all >= WINDOW_COLS else all_lens
    fw = _compute_features(win_lens)

    info = {
        "pattern":      "不明",
        "sub":          "",
        "reason":       "",
        "entry_ok_tate": False,
        "entry_ok_yoko": False,
        "n_cols":       n_cols_all,
        "n_hands_nont": p_cnt + b_cnt,
        "n_hands_total": len(seq),
        "p_cnt": p_cnt, "b_cnt": b_cnt, "t_cnt": t_cnt,
        "b_lead": b_cnt - p_cnt,
        "col_lens": all_lens,
        "win_lens": win_lens,
        "features": {
            "avg_col":       round(fw["avg"], 2),
            "n_long3":       fw["n3"],
            "n_long4":       fw["n4"],
            "n_long5":       fw["n5"],
            "pct_le2":       fw["pct_le2"],
            "pct_1":         fw["pct_1"],
            "pct_2":         fw["pct_2"],
            "has_consec_2":  fw["has_consec_2"],
            "trailing_ones": fw["trailing_ones"],
            "win_size":      fw["n"],
        },
    }

    if n_cols_all < 5:
        info["reason"] = f"列数不足 ({n_cols_all}<5)"
        return info

    # 偏り (シュー全体) → 縦流れ
    if abs(p_cnt - b_cnt) >= BIAS_THRESHOLD:
        info["pattern"]       = "縦流れ"
        info["sub"]           = "偏り"
        info["entry_ok_tate"] = True
        info["reason"] = f"P-B差={abs(p_cnt-b_cnt)} — {'P' if p_cnt>b_cnt else 'B'}側優勢"
        return info

    avg = fw["avg"]
    n4  = fw["n4"]
    n5  = fw["n5"]
    pct2 = fw["pct_le2"] / 100  # 0-1

    # 縦流れ判定 (ウィンドウ内)
    is_tate_show  = avg >= TATE_AVG_SHOW or n4 >= 1
    is_tate_entry = avg >= TATE_AVG_ENTRY or n5 >= TATE_N5_ENTRY or (n5 >= 1 and avg >= 3.5) or n4 >= 4

    # 横流れ判定 (ウィンドウ内)
    is_yoko_show  = pct2 >= YOKO_PCT_SHOW and n5 == 0 and n4 <= 1
    is_yoko_entry = pct2 >= YOKO_PCT_ENTRY and n5 == 0 and n4 == 0

    if is_tate_show and not is_yoko_show:
        info["pattern"]       = "縦流れ"
        info["sub"]           = _sub_pattern(fw)
        info["entry_ok_tate"] = is_tate_entry
        info["reason"]        = f"直近{fw['n']}列 平均{avg:.1f} / 4+連{n4}"
        return info

    if is_yoko_show and not is_tate_show:
        info["pattern"]       = "横流れ"
        info["sub"]           = _sub_pattern(fw)
        info["entry_ok_yoko"] = is_yoko_entry
        info["reason"]        = f"直近{fw['n']}列 ≤2段{fw['pct_le2']}%"
        return info

    if is_tate_show and is_yoko_show:
        # 両方 → 強い方を採用
        if avg >= 3.5 or n4 >= 2:
            info["pattern"]       = "縦流れ"
            info["sub"]           = _sub_pattern(fw)
            info["entry_ok_tate"] = is_tate_entry
            info["reason"]        = f"縦優位 (平均{avg:.1f}/≤2段{fw['pct_le2']}%)"
        else:
            info["pattern"]       = "横流れ"
            info["sub"]           = _sub_pattern(fw)
            info["entry_ok_yoko"] = is_yoko_entry
            info["reason"]        = f"横優位 (≤2段{fw['pct_le2']}%/平均{avg:.1f})"
        return info

    info["pattern"] = "不規則"
    info["reason"]  = f"直近{fw['n']}列 平均{avg:.1f} / ≤2段{fw['pct_le2']}%"
    return info


def check_entry(seq: str, info: dict) -> tuple[bool, str]:
    pat = info["pattern"]
    n   = info["n_cols"]
    if pat == "縦流れ":
        if n < 3:
            return False, f"列数不足 ({n}/3)"
        if info["entry_ok_tate"]:
            return True, f"縦流れ ({info['sub']}) 規則性確認"
        return False, f"縦流れだが規則性弱め (平均{info['features']['avg_col']})"
    if pat == "横流れ":
        if n < 5:
            return False, f"列数不足 ({n}/5)"
        if info["entry_ok_yoko"]:
            return True, f"横流れ ({info['sub']}) 規則性確認"
        return False, f"横流れだが規則性弱め (≤2段{info['features']['pct_le2']}%)"
    return False, f"判定不可 ({pat})"


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
    cols  = compute_big_road_columns(seq)
    depth = len(cols[-1]) if cols else 0
    prev  = _last_pb(seq)

    if entry_pattern == "縦流れ":
        if prev == 'P':
            return {"action": "BET", "side": "P",
                    "reason": f"MF 順張り (P 連続, depth={depth})"}
        return {"action": "LOOK", "side": None,
                "reason": f"LOOK (前手 {prev or '?'} — P 待ち)"}

    if entry_pattern == "横流れ":
        if prev == 'B':
            return {"action": "BET", "side": "P",
                    "reason": "RF 逆張り (B出現 → P BET)"}
        return {"action": "LOOK", "side": None,
                "reason": "LOOK (P出現 — B 待ち)"}

    return {"action": "LOOK", "side": None, "reason": f"pattern={entry_pattern}"}


def check_exit(info: dict, entry_pattern: str, losing_streak: int) -> tuple[bool, str]:
    if losing_streak >= 2:
        return True, "2連敗 → 退室"
    if info["pattern"] == "不規則":
        return True, "不規則化 → 退室"
    return False, ""


def forecast(seq: str, info: dict, entry_pattern: str | None,
             pending_bet: dict | None = None,
             enter_flag: bool = False, enter_reason: str = "") -> dict:
    pat   = info["pattern"]
    sub   = info.get("sub", "")
    n     = info["n_cols"]
    prev  = _last_pb(seq)
    cols  = compute_big_road_columns(seq)
    depth = len(cols[-1]) if cols else 0

    if pending_bet:
        return {
            "situation": f"💰 BET 実行中: {pending_bet['side']} ${pending_bet['unit']:.0f}",
            "next": "次ハンドで勝敗判定",
            "level": "pending", "confidence": None,
        }

    if not entry_pattern:
        if pat == "不明":
            return {
                "situation": f"判定待ち ({n}/5列)",
                "next": "手数が増えれば自動判定",
                "level": "waiting", "confidence": None,
            }
        if pat == "不規則":
            return {
                "situation": "❌ 不規則 — 見送り",
                "next": info["reason"],
                "level": "exit", "confidence": 10,
            }
        if enter_flag:
            return {
                "situation": f"✅ {pat} ({sub}) 規則性確認",
                "next": f"🎯 {enter_reason}",
                "level": "reach", "confidence": 65,
            }
        req = 3 if pat == "縦流れ" else 5
        return {
            "situation": f"⭐ {pat} ({sub}) 候補 ({n}列)",
            "next": info["reason"],
            "level": "watching", "confidence": 40,
        }

    if entry_pattern == "縦流れ":
        if prev == 'P':
            streak = _trailing_streak(seq, 'P')
            conf   = min(52 + streak * 2, 72)
            return {
                "situation": f"🔥 P {streak}連続中 — 縦流れ ({sub})",
                "next": "🟢 次ハンド P BET (MF 順張り)",
                "level": "imminent", "confidence": conf,
            }
        b_streak = _trailing_streak(seq, 'B')
        return {
            "situation": f"B {b_streak}連続中 — P 待機",
            "next": "⏳ P 出現したら次ハンドから BET",
            "level": "watching", "confidence": 30,
        }

    if entry_pattern == "横流れ":
        if prev == 'B':
            return {
                "situation": f"🎯 B 出現 — 横流れ ({sub}) 逆張りチャンス",
                "next": "🟢 次ハンド P BET (RF 逆張り)",
                "level": "imminent", "confidence": 55,
            }
        return {
            "situation": f"P 出現 — B 待機 (横流れ {sub})",
            "next": "⏳ B が出たら次ハンド P BET",
            "level": "reach", "confidence": 40,
        }

    return {
        "situation": f"pattern: {entry_pattern}",
        "next": "判定中",
        "level": "watching", "confidence": None,
    }
