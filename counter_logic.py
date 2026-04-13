from __future__ import annotations

from typing import Iterable

# 入室条件
ENTRY_WINDOW = 15
ENTRY_THRESHOLD = 0.85  # 直近15列で 1落ち+2落ちが 85%以上

# 退室条件
EXIT_DROP3_LIMIT = 2  # 3落ち以上が2回で退室
EXIT_DROP5_IMMEDIATE = True  # 5落ちが1回で即退室

# BET
FLAT_BET_AMOUNT = 1.0

# テレコテーブル検索
SEARCH_INTERVAL = 30


def compute_column_lengths(bead_road: Iterable[str]) -> list[int]:
    """bead road (P/B/T) から大路の列長リストを返す。Tie(T)は無視。"""
    columns: list[int] = []
    current_len = 0
    last_side: str | None = None
    for ch in bead_road:
        if ch == "T":
            continue
        if ch not in ("P", "B"):
            continue
        if ch == last_side:
            current_len += 1
        else:
            if last_side is not None:
                columns.append(current_len)
            current_len = 1
            last_side = ch
    if current_len > 0:
        columns.append(current_len)
    return columns


def short_rate(column_lengths: list[int], window: int = ENTRY_WINDOW) -> float:
    if len(column_lengths) < window:
        return 0.0
    recent = column_lengths[-window:]
    short_count = sum(1 for L in recent if L <= 2)
    return short_count / len(recent)


def is_tereko_state(column_lengths: list[int]) -> bool:
    if len(column_lengths) < ENTRY_WINDOW:
        return False
    return short_rate(column_lengths, ENTRY_WINDOW) >= ENTRY_THRESHOLD


def should_exit(columns_since_entry: list[int], current_column_length: int) -> str | None:
    check = list(columns_since_entry)
    if current_column_length >= 3:
        check.append(current_column_length)

    if EXIT_DROP5_IMMEDIATE:
        if any(L >= 5 for L in check) or current_column_length >= 5:
            return "streak-5"

    drop3_count = sum(1 for L in check if L >= 3)
    if drop3_count >= EXIT_DROP3_LIMIT:
        return f"streak-3x{drop3_count}"

    return None


def decide_counter_bet(last_non_tie: str | None) -> str | None:
    """逆張りBET側を返す (player/banker)。last_non_tieは 'P' or 'B'。"""
    if last_non_tie is None:
        return None
    if last_non_tie == "P":
        return "banker"
    if last_non_tie == "B":
        return "player"
    return None
