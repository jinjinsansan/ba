"""LAPLACE 日次学習バッチ

毎日 JST 0:05 に VPS で cron 実行。
過去24時間の analytics.sqlite3 を分析し、環境指標を計算。
Supabase に記録 + 異常検知時に Telegram アラート。

Usage:
  python daily_learning.py                    # 本日分を計算
  python daily_learning.py --date 2026-04-13  # 特定日を計算

Cron:
  5 15 * * * cd /opt/laplace && venv/bin/python daily_learning.py
"""
import sqlite3
import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from pattern_classifier import classify_pattern

DB_PATH = os.environ.get("ANALYTICS_DB", "analytics.sqlite3")
JST = timezone(timedelta(hours=9))

# Supabase
SITE_URL = os.environ.get("LAPLACE_SITE_URL", "https://bafather.uk").rstrip("/")
API_KEY = os.environ.get("LAPLACE_API_KEY", "")

# Telegram alert
ALERT_BOT_TOKEN = os.environ.get("ADMIN_TELEGRAM_BOT_TOKEN", "")
ALERT_CHAT_ID = os.environ.get("ADMIN_TELEGRAM_CHAT_ID", "")

# 閾値
WARN_AVG_DURATION = 10.0   # 平均寿命がこれ以下で警戒
WARN_WIN_RATE = 51.0       # 勝率がこれ以下で警戒
DANGER_AVG_DURATION = 7.0  # 危険
DANGER_WIN_RATE = 50.0     # 危険
CONSECUTIVE_WARN_DAYS = 3  # N日連続で警戒→アラート

TEREKO_WINDOW = 10
TEREKO_THRESH = 0.80
MIN_HANDS = 50
STATIC_WARMUP = 30


def get_target_date():
    for i, a in enumerate(sys.argv):
        if a == "--date" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return datetime.now(JST).strftime("%Y-%m-%d")


def load_shoes(date_str):
    """指定日のシューを読み込み"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    next_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    cur.execute(
        "SELECT table_name, result_sequence, started_at FROM shoes_analytics "
        "WHERE hand_count >= ? AND started_at >= ? AND started_at < ? ORDER BY started_at",
        (MIN_HANDS, date_str, next_date)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def load_recent_metrics(days=7):
    """直近N日分のメトリクスを Supabase から取得 (閾値チェック用)"""
    if not API_KEY:
        return []
    try:
        url = f"{SITE_URL}/api/daily-metrics?days={days}&api_key={API_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "LAPLACE-learning/1.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8")).get("metrics", [])
    except Exception:
        return []


def strip_ties(seq):
    return ''.join(ch for ch in seq if ch in ('P', 'B'))


def compute_columns(seq):
    cols = []
    cur = 0
    last = None
    for ch in seq:
        if ch == 'T':
            continue
        if ch == last:
            cur += 1
        else:
            if last is not None:
                cols.append(cur)
            cur = 1
            last = ch
    if cur > 0:
        cols.append(cur)
    return cols


def analyze(shoes):
    """日次メトリクスを計算"""
    total_shoes = len(shoes)
    tereko_shoes = 0
    total_hands = 0
    counter_wins = 0
    counter_losses = 0
    tereko_durations = []
    hourly_wr = defaultdict(lambda: {'w': 0, 'l': 0})

    # パターン別勝率 (Top 100)
    pattern_stats = defaultdict(lambda: {'w': 0, 'l': 0})

    for table_name, seq, started_at in shoes:
        clean = strip_ties(seq)
        if len(clean) < STATIC_WARMUP:
            continue

        # JST hour
        try:
            hour = int(started_at.split('T')[1].split(':')[0]) if 'T' in started_at else int(started_at.split(' ')[1].split(':')[0])
        except Exception:
            hour = -1

        # テレコ判定
        warmup = clean[:STATIC_WARMUP]
        pattern = classify_pattern(warmup, min_cols=3)
        is_tereko = (pattern == "テレコ+ニコ混合")
        if is_tereko:
            tereko_shoes += 1

        # テレコ寿命
        cols = compute_columns(clean)
        if len(cols) >= TEREKO_WINDOW:
            in_t = False
            t_start = 0
            for ci in range(TEREKO_WINDOW, len(cols)):
                recent = cols[ci - TEREKO_WINDOW:ci]
                short = sum(1 for L in recent if L <= 2)
                is_t = (short / len(recent)) >= TEREKO_THRESH
                if is_t and not in_t:
                    in_t = True
                    t_start = ci
                elif not is_t and in_t:
                    tereko_durations.append(ci - t_start)
                    in_t = False
            if in_t:
                tereko_durations.append(len(cols) - t_start)

        # 逆張り勝率 (テレコシューのみ)
        if is_tereko:
            last_nt = None
            for ch in seq:
                if ch not in ('P', 'B'):
                    continue
                if last_nt is not None:
                    bet_side = 'P' if last_nt == 'B' else 'B'
                    won = (ch == bet_side)
                    total_hands += 1
                    if won:
                        counter_wins += 1
                    else:
                        counter_losses += 1
                    if hour >= 0:
                        if won:
                            hourly_wr[hour]['w'] += 1
                        else:
                            hourly_wr[hour]['l'] += 1

                    # パターン勝率 (10列窓)
                    if len(cols) >= 10:
                        p_key = tuple(cols[-10:])
                        if won:
                            pattern_stats[p_key]['w'] += 1
                        else:
                            pattern_stats[p_key]['l'] += 1

                last_nt = ch

    # 集計
    wr = counter_wins / total_hands * 100 if total_hands > 0 else 0
    tereko_rate = tereko_shoes / total_shoes * 100 if total_shoes > 0 else 0
    avg_duration = sum(tereko_durations) / len(tereko_durations) if tereko_durations else 0
    short5h_rate = sum(1 for d in tereko_durations if d <= 5) / len(tereko_durations) * 100 if tereko_durations else 0

    # 時間帯別ベスト/ワースト
    best_hour = -1
    worst_hour = -1
    best_wr = 0
    worst_wr = 100
    for h in range(24):
        d = hourly_wr[h]
        t = d['w'] + d['l']
        if t < 50:
            continue
        hr = d['w'] / t * 100
        if hr > best_wr:
            best_wr = hr
            best_hour = h
        if hr < worst_wr:
            worst_wr = hr
            worst_hour = h

    # パターン Top 100
    pattern_top = []
    for p_key, d in pattern_stats.items():
        t = d['w'] + d['l']
        if t < 30:
            continue
        pattern_top.append({
            'pattern': '-'.join(str(x) for x in p_key),
            'win_rate': d['w'] / t * 100,
            'samples': t,
        })
    pattern_top.sort(key=lambda x: -x['win_rate'])
    pattern_top = pattern_top[:100]

    return {
        'total_shoes': total_shoes,
        'tereko_shoes': tereko_shoes,
        'tereko_rate': round(tereko_rate, 2),
        'total_hands': total_hands,
        'counter_wr': round(wr, 2),
        'avg_duration': round(avg_duration, 1),
        'short5h_rate': round(short5h_rate, 1),
        'best_hour': best_hour,
        'worst_hour': worst_hour,
        'best_wr': round(best_wr, 2),
        'worst_wr': round(worst_wr, 2),
        'pattern_top': pattern_top,
    }


def post_to_supabase(date_str, metrics):
    """Supabase に日次メトリクスを送信"""
    if not API_KEY:
        print("  [skip] No API_KEY — Supabase upload skipped")
        return False
    payload = json.dumps({
        "api_key": API_KEY,
        "date": date_str,
        "metrics": metrics,
    }).encode("utf-8")
    url = f"{SITE_URL}/api/daily-metrics"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "LAPLACE-learning/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("  [ok] Supabase upload success")
            return True
    except Exception as e:
        print(f"  [err] Supabase upload failed: {e}")
        return False


def post_pattern_winrates(pattern_top):
    """パターン勝率 Top100 を Supabase に送信"""
    if not API_KEY or not pattern_top:
        return
    payload = json.dumps({
        "api_key": API_KEY,
        "patterns": pattern_top,
    }).encode("utf-8")
    url = f"{SITE_URL}/api/pattern-winrates"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "LAPLACE-learning/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("  [ok] Pattern winrates uploaded")
    except Exception as e:
        print(f"  [err] Pattern winrates upload failed: {e}")


def send_telegram_alert(message):
    if not ALERT_BOT_TOKEN or not ALERT_CHAT_ID:
        print(f"  [alert] {message}")
        return
    payload = json.dumps({
        "chat_id": ALERT_CHAT_ID,
        "text": message,
    }).encode("utf-8")
    url = f"https://api.telegram.org/bot{ALERT_BOT_TOKEN}/sendMessage"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("  [ok] Telegram alert sent")
    except Exception as e:
        print(f"  [err] Telegram alert failed: {e}")


def check_thresholds(metrics, recent_metrics):
    """閾値チェック → アラート"""
    alerts = []

    wr = metrics['counter_wr']
    dur = metrics['avg_duration']

    # 単日チェック
    if dur <= DANGER_AVG_DURATION:
        alerts.append(f"DANGER: Avg duration {dur}h (< {DANGER_AVG_DURATION}h)")
    elif dur <= WARN_AVG_DURATION:
        alerts.append(f"WARNING: Avg duration {dur}h (< {WARN_AVG_DURATION}h)")

    if wr <= DANGER_WIN_RATE:
        alerts.append(f"DANGER: Win rate {wr}% (< {DANGER_WIN_RATE}%)")
    elif wr <= WARN_WIN_RATE:
        alerts.append(f"WARNING: Win rate {wr}% (< {WARN_WIN_RATE}%)")

    # 連続日チェック
    if recent_metrics and len(recent_metrics) >= CONSECUTIVE_WARN_DAYS:
        recent_wrs = [m.get('counter_wr', 55) for m in recent_metrics[-CONSECUTIVE_WARN_DAYS:]]
        if all(w <= WARN_WIN_RATE for w in recent_wrs):
            alerts.append(f"CRITICAL: Win rate below {WARN_WIN_RATE}% for {CONSECUTIVE_WARN_DAYS} consecutive days: {recent_wrs}")

        recent_durs = [m.get('avg_duration', 20) for m in recent_metrics[-CONSECUTIVE_WARN_DAYS:]]
        if all(d <= WARN_AVG_DURATION for d in recent_durs):
            alerts.append(f"CRITICAL: Avg duration below {WARN_AVG_DURATION}h for {CONSECUTIVE_WARN_DAYS} consecutive days: {recent_durs}")

    return alerts


def main():
    date_str = get_target_date()
    print(f"LAPLACE Daily Learning — {date_str}")
    print(f"DB: {DB_PATH}")

    shoes = load_shoes(date_str)
    print(f"Loaded {len(shoes)} shoes for {date_str}")

    if not shoes:
        print("No data — skipping")
        return

    metrics = analyze(shoes)
    pattern_top = metrics.pop('pattern_top', [])

    print(f"\n=== Daily Metrics ===")
    print(f"  Shoes: {metrics['total_shoes']} (tereko: {metrics['tereko_shoes']}, {metrics['tereko_rate']}%)")
    print(f"  Counter WR: {metrics['counter_wr']}% ({metrics['total_hands']} hands)")
    print(f"  Avg Duration: {metrics['avg_duration']}h")
    print(f"  Short5h Rate: {metrics['short5h_rate']}%")
    print(f"  Best Hour: {metrics['best_hour']:02d}:00 ({metrics['best_wr']}%)")
    print(f"  Worst Hour: {metrics['worst_hour']:02d}:00 ({metrics['worst_wr']}%)")
    print(f"  Pattern Top: {len(pattern_top)} patterns")

    # Supabase に送信
    post_to_supabase(date_str, metrics)
    post_pattern_winrates(pattern_top)

    # 閾値チェック
    recent = load_recent_metrics(days=CONSECUTIVE_WARN_DAYS + 1)
    alerts = check_thresholds(metrics, recent)

    if alerts:
        msg = f"⚠ LAPLACE ENVIRONMENT ALERT — {date_str}\n\n"
        msg += "\n".join(alerts)
        msg += f"\n\nMetrics: WR={metrics['counter_wr']}% Dur={metrics['avg_duration']}h Tereko={metrics['tereko_rate']}%"
        send_telegram_alert(msg)
    else:
        print("\n  [ok] All thresholds normal")

    # パラメータ自動調整
    param_changes = auto_adjust_params(metrics, recent)

    # 日次サマリー通知 (常時)
    param_note = ""
    if param_changes:
        param_note = "\n" + " | ".join(param_changes)
    summary = (
        f"📊 LAPLACE Daily — {date_str}\n"
        f"WR: {metrics['counter_wr']}% | Dur: {metrics['avg_duration']}h | Tereko: {metrics['tereko_rate']}%\n"
        f"Best: {metrics['best_hour']:02d}:00 ({metrics['best_wr']}%) | Worst: {metrics['worst_hour']:02d}:00 ({metrics['worst_wr']}%)"
        f"{param_note}"
    )
    send_telegram_alert(summary)


# ============================================================
# パラメータ自動調整
# ============================================================

# デフォルト値
DEFAULT_PARAMS = {
    "entry_window": 15,
    "entry_threshold": 0.85,
    "exit_drop3_limit": 2,
    "exit_drop5_immediate": True,
    "profit_target": 30,
}

# 調整範囲
PARAM_LIMITS = {
    "entry_window": (8, 20),
    "entry_threshold": (0.70, 0.95),
    "exit_drop3_limit": (1, 4),
}


def load_current_params() -> dict:
    """Supabase から現在のパラメータを取得"""
    if not API_KEY:
        return dict(DEFAULT_PARAMS)
    try:
        url = f"{SITE_URL}/api/optimal-params?api_key={API_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "LAPLACE-learning/1.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
            params = data.get("params", {})
            if not params or params.get("status") == "default":
                return dict(DEFAULT_PARAMS)
            return params
    except Exception:
        return dict(DEFAULT_PARAMS)


def save_params(params: dict, reason: str):
    """Supabase にパラメータを保存"""
    if not API_KEY:
        print(f"  [skip] No API_KEY — param save skipped ({reason})")
        return
    payload = json.dumps({
        "api_key": API_KEY,
        "entry_window": params["entry_window"],
        "entry_threshold": params["entry_threshold"],
        "exit_drop3_limit": params["exit_drop3_limit"],
        "exit_drop5_immediate": params.get("exit_drop5_immediate", True),
        "profit_target": params.get("profit_target", 30),
        "status": "active",
        "reason": reason,
    }).encode("utf-8")
    url = f"{SITE_URL}/api/optimal-params"
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "LAPLACE-learning/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print(f"  [ok] Params saved: {reason}")
    except Exception as e:
        print(f"  [err] Param save failed: {e}")


def auto_adjust_params(today_metrics: dict, recent_metrics: list) -> list[str]:
    """過去7日のトレンドからパラメータを自動調整"""
    changes = []
    current = load_current_params()
    new_params = dict(current)
    adjusted = False

    if not recent_metrics or len(recent_metrics) < 3:
        print("  [params] Not enough history (< 3 days) — skip adjustment")
        return changes

    # 直近3日のトレンド
    recent_3 = recent_metrics[-3:] if len(recent_metrics) >= 3 else recent_metrics
    avg_wr_3d = sum(m.get('counter_wr', 53) for m in recent_3) / len(recent_3)
    avg_dur_3d = sum(m.get('avg_duration', 15) for m in recent_3) / len(recent_3)

    ew_min, ew_max = PARAM_LIMITS["entry_window"]
    et_min, et_max = PARAM_LIMITS["entry_threshold"]
    d3_min, d3_max = PARAM_LIMITS["exit_drop3_limit"]

    # ── 入室条件 (ENTRY_THRESHOLD) ──
    # テレコ寿命が短い → 厳しくする (もっと確実なテレコだけ入る)
    if avg_dur_3d < 8:
        new_et = min(current.get("entry_threshold", 0.85) + 0.05, et_max)
        if new_et != current.get("entry_threshold", 0.85):
            new_params["entry_threshold"] = round(new_et, 2)
            changes.append(f"ET {current.get('entry_threshold', 0.85)}→{new_et} (dur↓)")
            adjusted = True
    # テレコ寿命が長い → 緩める (もっと積極的に入る)
    elif avg_dur_3d > 18:
        new_et = max(current.get("entry_threshold", 0.85) - 0.05, et_min)
        if new_et != current.get("entry_threshold", 0.85):
            new_params["entry_threshold"] = round(new_et, 2)
            changes.append(f"ET {current.get('entry_threshold', 0.85)}→{new_et} (dur↑)")
            adjusted = True

    # ── 入室ウィンドウ (ENTRY_WINDOW) ──
    # 勝率が低い → ウィンドウを広げる (より多くの列で判定 = 慎重)
    if avg_wr_3d < 51:
        new_ew = min(current.get("entry_window", 15) + 2, ew_max)
        if new_ew != current.get("entry_window", 15):
            new_params["entry_window"] = new_ew
            changes.append(f"EW {current.get('entry_window', 15)}→{new_ew} (wr↓)")
            adjusted = True
    # 勝率が高い → ウィンドウを狭める (素早く入る)
    elif avg_wr_3d > 55:
        new_ew = max(current.get("entry_window", 15) - 2, ew_min)
        if new_ew != current.get("entry_window", 15):
            new_params["entry_window"] = new_ew
            changes.append(f"EW {current.get('entry_window', 15)}→{new_ew} (wr↑)")
            adjusted = True

    # ── 退室条件 (EXIT_DROP3_LIMIT) ──
    # テレコ寿命が短い → 退室を早める (1回で退室)
    if avg_dur_3d < 7:
        new_d3 = max(current.get("exit_drop3_limit", 2) - 1, d3_min)
        if new_d3 != current.get("exit_drop3_limit", 2):
            new_params["exit_drop3_limit"] = new_d3
            changes.append(f"D3 {current.get('exit_drop3_limit', 2)}→{new_d3} (dur↓↓)")
            adjusted = True
    # テレコ寿命が長い → もう少し粘る
    elif avg_dur_3d > 20:
        new_d3 = min(current.get("exit_drop3_limit", 2) + 1, d3_max)
        if new_d3 != current.get("exit_drop3_limit", 2):
            new_params["exit_drop3_limit"] = new_d3
            changes.append(f"D3 {current.get('exit_drop3_limit', 2)}→{new_d3} (dur↑↑)")
            adjusted = True

    # パラメータ変更があればSupabaseに保存
    if adjusted:
        reason = f"auto: wr3d={avg_wr_3d:.1f}% dur3d={avg_dur_3d:.1f}h"
        save_params(new_params, reason)
        print(f"  [params] Adjusted: {', '.join(changes)}")
    else:
        print(f"  [params] No adjustment needed (wr3d={avg_wr_3d:.1f}% dur3d={avg_dur_3d:.1f}h)")

    return changes


if __name__ == "__main__":
    main()
