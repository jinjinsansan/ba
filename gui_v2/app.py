"""ba GUI v2 — Copilot 型 Flask バックエンド

役割:
  - user が手動で hand 結果 (P/B/T) を入力
  - pattern 判定・エントリー条件・BET 推奨を毎ハンドごとに計算
  - 旧 SEQ 7 ターン tracker の unit と overshoot を自動進行
  - セッションの勝率・PNL を可視化
  - 持続確定テーブル watchlist を表示

BET は一切自動化しない。全ての BET 行動は user が Camoufox で手動で実行。
"""
from __future__ import annotations
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from marubatsu_strategy import MaruBatsuTracker, SEQ as OLD_SEQ

from strategy_engine import (
    classify_strict,
    check_entry,
    check_exit,
    decide_bet,
    forecast,
    VALID_PATTERNS,
)
from pragmatic_bridge import get_pragmatic_bridge
import learning

# scraper_bridge は後方互換で残すが、Pragmatic モードでは使わない
def get_bridge():
    return get_pragmatic_bridge()

app = Flask(__name__)
# 開発中のブラウザキャッシュ抑止 (static ファイル含む)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
# テンプレート変更を即反映
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ホワイトリスト (Pragmatic Play — 標準テーブル優先)
WATCHLIST_CONFIRMED = [
    {"name": "Baccarat 5",                   "oos_win": 0, "oos_roi": 0},
    {"name": "Baccarat 9",                   "oos_win": 0, "oos_roi": 0},
    {"name": "Speed Baccarat 9",             "oos_win": 0, "oos_roi": 0},
    {"name": "Speed Baccarat 11",            "oos_win": 0, "oos_roi": 0},
    {"name": "Speed Baccarat 18",            "oos_win": 0, "oos_roi": 0},
    {"name": "Korean Speed Baccarat 1",      "oos_win": 0, "oos_roi": 0},
    {"name": "Korean Speed Baccarat 3",      "oos_win": 0, "oos_roi": 0},
    {"name": "Vietnamese Speed Baccarat 1",  "oos_win": 0, "oos_roi": 0},
    {"name": "Vietnamese Speed Baccarat 3",  "oos_win": 0, "oos_roi": 0},
    {"name": "Chinese Speed Baccarat 1",     "oos_win": 0, "oos_roi": 0},
]
WATCHLIST_EXPECTED = [
    {"name": "Speed Baccarat 3",             "oos_win": 0, "oos_roi": 0},
    {"name": "Speed Baccarat 10",            "oos_win": 0, "oos_roi": 0},
    {"name": "Speed Baccarat 16",            "oos_win": 0, "oos_roi": 0},
    {"name": "Korean Turbo Baccarat 1",      "oos_win": 0, "oos_roi": 0},
    {"name": "Thai Speed Baccarat 1",        "oos_win": 0, "oos_roi": 0},
]
WATCHLIST_BLACKLIST = [
    "Privé Lounge Baccarat 1", "Privé Lounge Baccarat 2", "Privé Lounge Baccarat 3",
    "Privé Lounge Baccarat 5", "Privé Lounge Baccarat 6", "Privé Lounge Baccarat 7",
    "Privé Lounge Baccarat 8", "Korean Privé Lounge Baccarat 1",
    "Privé Lounge Baccarat Squeeze 1", "Privé Lounge Baccarat Squeeze 2",
    "Fortune 6 Baccarat", "Super 8 Baccarat", "MEGA BACCARAT",
    "BACCARAT_MULTIPLAY", "Mega Sic Bac",
]


class Session:
    """セッション 1 件分の状態を保持"""

    def __init__(self):
        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.active = False
        self.current_table: str = ""
        self.seq: list[str] = []  # bead road (P/B/T)
        self.entered = False
        self.entry_pattern: Optional[str] = None
        self.entry_hand_idx: Optional[int] = None
        self.losing_streak = 0

        # 全セッション通しで旧 SEQ tracker を継続
        self.tracker = MaruBatsuTracker(chip_base=1.0, seq=OLD_SEQ, set_size=7)

        # BET 履歴
        self.bet_history: list[dict] = []  # {side, result, won, unit, pnl, pattern, timestamp}
        self.hand_history: list[dict] = []  # {result, timestamp, bet_side (Nullable)}
        self.pending_bet: Optional[dict] = None  # 次ハンドで判定される予定の BET

        # ハンド判定ログ (GUI 表示用)
        self.action_log: list[dict] = []

        # スクレイパ自動追従: True なら scraper から seq を上書き
        self.auto_follow_scraper = False

    def reset(self):
        self.__init__()

    def start(self, table_name: str):
        self.reset()
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.active = True
        self.current_table = table_name
        self._log("START", f"セッション開始 (table={table_name})")

    def stop(self):
        self.stopped_at = datetime.now().isoformat(timespec="seconds")
        self.active = False
        self._log("STOP", "セッション終了")
        self._persist()

    def change_table(self, table_name: str):
        """テーブル切替: 現シューをリセットし、新テーブルへ"""
        self.current_table = table_name
        self.seq = []
        self.entered = False
        self.entry_pattern = None
        self.entry_hand_idx = None
        self.losing_streak = 0
        self.pending_bet = None
        self._log("TABLE", f"テーブル切替 → {table_name}")

    def reset_shoe(self):
        """新シュー (同テーブル): bead road のみリセット"""
        self.seq = []
        self.entered = False
        self.entry_pattern = None
        self.entry_hand_idx = None
        self.losing_streak = 0
        self.pending_bet = None
        self._log("SHOE", "新シュー (同テーブル)")

    def _log(self, kind: str, msg: str):
        self.action_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "kind": kind,
            "msg": msg,
        })
        if len(self.action_log) > 200:
            self.action_log = self.action_log[-200:]

    def _persist(self):
        """セッションログを JSONL 保存"""
        if not self.started_at:
            return
        name = self.started_at.replace(":", "-") + ".json"
        path = LOG_DIR / name
        path.write_text(json.dumps({
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "current_table": self.current_table,
            "seq": "".join(self.seq),
            "bet_history": self.bet_history,
            "hand_history": self.hand_history,
            "action_log": self.action_log,
            "bet_summary": self.summary(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_hand(self, result: str):
        """hand 結果 (P/B/T) を追加。pending_bet があれば判定"""
        result = result.upper()
        if result not in ("P", "B", "T"):
            return {"ok": False, "error": "invalid result"}

        timestamp = datetime.now().strftime("%H:%M:%S")
        # pending_bet の判定
        bet_resolved = None
        if self.pending_bet is not None and result in ("P", "B"):
            pb = self.pending_bet
            won = (result == pb["side"])
            bet_resolved = {
                "side": pb["side"], "result": result, "won": won,
                "unit": pb["unit"], "pnl": pb["unit"] if won else -pb["unit"],
                "pattern": pb["pattern"], "time": timestamp,
                "reason": pb["reason"],
            }
            self.bet_history.append(bet_resolved)
            self.losing_streak = 0 if won else self.losing_streak + 1
            # tracker 進行
            self.tracker.add_result("player" if won else "banker")
            self._log("BET_RESULT", f"{'WIN' if won else 'LOSE'} / ${pb['unit']:.0f} {pb['side']} (結果 {result})")
            # AI 学習データ蓄積
            learning.log_bet({
                "table": self.current_table,
                "entry_pattern": pb["pattern"],
                "bet_side": pb["side"],
                "result": result,
                "won": won,
                "unit": pb["unit"],
                "seq_len_at_bet": len(self.seq),  # BET 決定時点
                "reason": pb["reason"],
            })
            self.pending_bet = None

        # hand を seq に追加
        self.seq.append(result)
        self.hand_history.append({
            "result": result, "time": timestamp,
            "bet_resolved": bet_resolved,
        })

        # 新状態で pattern 判定 → エントリー / 退出判定 → 次 BET 推奨
        info = classify_strict("".join(self.seq))

        # 退出 / パターン切替判定 (entered 中なら)
        exit_reason = ""
        if self.entered:
            exit_flag, exit_reason = check_exit(info, self.entry_pattern, self.losing_streak)
            if exit_flag:
                self.entered = False
                self.entry_pattern = None
                self.entry_hand_idx = None
                self.losing_streak = 0
                self._log("EXIT", exit_reason)
            elif info["pattern"] != self.entry_pattern and info["pattern"] in VALID_PATTERNS:
                # 有効パターン間の切替 → 退室せず戦略を更新
                old_pat = self.entry_pattern
                self.entry_pattern = info["pattern"]
                self._log("SWITCH", f"パターン切替: {old_pat} → {self.entry_pattern} (継続)")

        # エントリー判定 (未入室の時)
        if not self.entered:
            enter_flag, enter_reason = check_entry("".join(self.seq), info)
            if enter_flag:
                self.entered = True
                self.entry_pattern = info["pattern"]
                self.entry_hand_idx = len(self.seq)
                self._log("ENTER", f"{info['pattern']} — {enter_reason}")

        # 次 BET 推奨
        bet_recommend = {"action": "LOOK", "side": None, "reason": "未入室"}
        next_unit = OLD_SEQ[min(self.tracker.current_unit_idx, len(OLD_SEQ) - 1)]
        if self.entered:
            bet_recommend = decide_bet("".join(self.seq), self.entry_pattern)
            if bet_recommend["action"] == "BET":
                # pending_bet を設定 (次 hand で判定される)
                self.pending_bet = {
                    "side": bet_recommend["side"],
                    "unit": next_unit,
                    "pattern": self.entry_pattern,
                    "reason": bet_recommend["reason"],
                }

        return {
            "ok": True,
            "bet_resolved": bet_resolved,
            "info": info,
            "entered": self.entered,
            "entry_pattern": self.entry_pattern,
            "exit_reason": exit_reason,
            "bet_recommend": bet_recommend,
            "pending_bet": self.pending_bet,
            "next_unit": next_unit,
            "summary": self.summary(),
        }

    def undo_hand(self):
        """直前の hand と (あれば) BET 判定を取り消す"""
        if not self.seq:
            return {"ok": False, "error": "no hand"}
        last_result = self.seq.pop()
        last_hand = self.hand_history.pop() if self.hand_history else None
        # BET 判定取り消し
        if last_hand and last_hand.get("bet_resolved"):
            # bet_history 末尾を pop
            popped_bet = self.bet_history.pop() if self.bet_history else None
            # tracker は簡易的に「最新セットだけクリア」はできないので、
            # 代わりに逆結果を push する (近似、完璧ではない)
            if popped_bet and len(self.tracker.sets) > 0:
                # セット未完成状態を 1 ターン戻す: current_turns を pop
                if self.tracker.current_turns:
                    self.tracker.current_turns.pop()
            self.losing_streak = max(0, self.losing_streak - (1 if popped_bet and not popped_bet["won"] else 0))
            # 学習 jsonl も undone マーカーを付ける
            try:
                learning.undo_last_bet()
            except Exception:
                pass
        # entered 状態の補正はシンプルに再評価
        self._log("UNDO", f"直前 hand 取消 ({last_result})")
        # 再評価: 現 seq で classify → entered 判定し直し
        if self.seq:
            info = classify_strict("".join(self.seq))
            enter_flag, _ = check_entry("".join(self.seq), info)
            self.entered = enter_flag
            self.entry_pattern = info["pattern"] if enter_flag else None
        else:
            self.entered = False
            self.entry_pattern = None
        self.pending_bet = None
        return {"ok": True}

    def summary(self) -> dict:
        bets = len(self.bet_history)
        wins = sum(1 for b in self.bet_history if b["won"])
        pnl = sum(b["pnl"] for b in self.bet_history)
        stake = sum(b["unit"] for b in self.bet_history)
        return {
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "active": self.active,
            "table": self.current_table,
            "hands": len(self.seq),
            "bets": bets,
            "wins": wins,
            "losses": bets - wins,
            "win_rate": (wins / bets * 100) if bets else 0,
            "pnl": pnl,
            "stake": stake,
            "roi": (pnl / stake * 100) if stake else 0,
            "current_unit_idx": self.tracker.current_unit_idx,
            "current_unit": OLD_SEQ[min(self.tracker.current_unit_idx, len(OLD_SEQ) - 1)],
            "overshoot": self.tracker.prev_overshoot,
            "cumulative_tracker_profit": self.tracker.cumulative_profit,
            "sets_completed": len(self.tracker.sets),
            "current_turn": len(self.tracker.current_turns),
        }


SESSION = Session()


# =================================================================
# Routes
# =================================================================

@app.route("/")
def index():
    return render_template("index.html")


def _auto_follow_sync():
    """auto_follow が ON なら scraper の bead road から末尾差分を自動追加"""
    if not (SESSION.active and SESSION.auto_follow_scraper and SESSION.current_table):
        return
    bridge = get_bridge()
    if not bridge._running:
        return
    try:
        r = bridge.get_table_bead_road(SESSION.current_table)
        if not r.get("ok"):
            return
        live_seq = r["seq"]  # P/B のみ (T 無視)
        # ローカル seq の P/B 部分
        local_pb = "".join(ch for ch in SESSION.seq if ch in ("P", "B"))
        if live_seq == local_pb:
            return
        if live_seq.startswith(local_pb):
            tail = live_seq[len(local_pb):]
            for ch in tail:
                SESSION.add_hand(ch)
        else:
            SESSION._log("FOLLOW_WARN", f"scraper seq 乖離 live={live_seq[-10:]!r} local={local_pb[-10:]!r} — ⚡ 同期ボタンで上書きを")
    except Exception as e:
        SESSION._log("FOLLOW_ERR", str(e)[:120])


@app.route("/api/status")
def api_status():
    _auto_follow_sync()
    info = classify_strict("".join(SESSION.seq)) if SESSION.seq else {
        "pattern": "不明", "reason": "シュー未開始", "n_cols": 0,
        "n_hands_nont": 0, "n_hands_total": 0,
        "p_cnt": 0, "b_cnt": 0, "t_cnt": 0, "b_lead": 0,
        "col_lens": [], "features": {},
    }
    enter_flag, enter_reason = (False, "未開始")
    if SESSION.seq:
        enter_flag, enter_reason = check_entry("".join(SESSION.seq), info)

    bet_recommend = {"action": "LOOK", "side": None, "reason": "未入室"}
    if SESSION.entered:
        bet_recommend = decide_bet("".join(SESSION.seq), SESSION.entry_pattern)

    next_unit = OLD_SEQ[min(SESSION.tracker.current_unit_idx, len(OLD_SEQ) - 1)]

    # 予告 (リーチ前リーチ + 確信度)
    fc = forecast(
        seq="".join(SESSION.seq),
        info=info,
        entry_pattern=SESSION.entry_pattern,
        pending_bet=SESSION.pending_bet,
        enter_flag=enter_flag,
        enter_reason=enter_reason,
    )
    # AI 学習による確信度調整
    if fc.get("confidence") is not None and SESSION.entry_pattern:
        blended, meta = learning.adjusted_confidence(
            fc["confidence"], SESSION.entry_pattern, SESSION.current_table
        )
        fc["confidence_rule"] = fc["confidence"]
        fc["confidence"] = blended
        fc["learning"] = meta

    return jsonify({
        "session": SESSION.summary(),
        "info": info,
        "enter_check": {"flag": enter_flag, "reason": enter_reason},
        "entered": SESSION.entered,
        "entry_pattern": SESSION.entry_pattern,
        "bet_recommend": bet_recommend,
        "pending_bet": SESSION.pending_bet,
        "next_unit": next_unit,
        "forecast": fc,
        "seq": "".join(SESSION.seq),
        "hand_history": SESSION.hand_history[-30:],
        "action_log": SESSION.action_log[-30:],
        "watchlist": {
            "confirmed": WATCHLIST_CONFIRMED,
            "expected": WATCHLIST_EXPECTED,
            "blacklist": WATCHLIST_BLACKLIST,
        },
    })


@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    tname = (request.json or {}).get("table_name", "").strip()
    SESSION.start(tname or "未指定")
    return jsonify({"ok": True})


@app.route("/api/session/stop", methods=["POST"])
def api_session_stop():
    SESSION.stop()
    return jsonify({"ok": True})


@app.route("/api/session/reset", methods=["POST"])
def api_session_reset():
    """セッションデータを完全リセット (手歴・KPI含む)"""
    SESSION.reset()
    return jsonify({"ok": True})


@app.route("/api/session/change_table", methods=["POST"])
def api_session_change_table():
    tname = (request.json or {}).get("table_name", "").strip()
    SESSION.change_table(tname or "未指定")
    return jsonify({"ok": True})


@app.route("/api/session/reset_shoe", methods=["POST"])
def api_session_reset_shoe():
    SESSION.reset_shoe()
    return jsonify({"ok": True})


@app.route("/api/hand", methods=["POST"])
def api_hand():
    if not SESSION.active:
        return jsonify({"ok": False, "error": "セッション未開始"}), 400
    result = (request.json or {}).get("result", "").upper()
    ret = SESSION.add_hand(result)
    return jsonify(ret)


@app.route("/api/hand/undo", methods=["POST"])
def api_hand_undo():
    ret = SESSION.undo_hand()
    return jsonify(ret)


@app.route("/api/bet/manual_resolve", methods=["POST"])
def api_bet_manual_resolve():
    """pending_bet を勝ち/負けで手動解決 (scraper 停滞時のフォールバック)

    body: {"outcome": "win" | "lose" | "tie"}
      - "win"  → pending_bet の side と同じ結果のハンドを追加 (WIN 判定される)
      - "lose" → pending_bet の side と逆の結果のハンドを追加 (LOSE 判定される)
      - "tie"  → T を追加 (BET はスキップ、pending は残る)
    """
    if not SESSION.active:
        return jsonify({"ok": False, "error": "セッション未開始"}), 400
    outcome = (request.json or {}).get("outcome", "")
    if outcome not in ("win", "lose", "tie"):
        return jsonify({"ok": False, "error": "outcome は win/lose/tie"}), 400
    if outcome == "tie":
        ret = SESSION.add_hand("T")
        return jsonify({"ok": True, **ret})
    if not SESSION.pending_bet:
        return jsonify({"ok": False, "error": "BET 待ちのハンドがありません"}), 400
    side = SESSION.pending_bet["side"]
    opposite = "B" if side == "P" else "P"
    hand_result = side if outcome == "win" else opposite
    ret = SESSION.add_hand(hand_result)
    return jsonify({"ok": True, **ret})


@app.route("/api/lobby")
def api_lobby():
    """ライブ scraper → lobby_state.json → DB の順で取得

    ?hours=N で DB 検索の lookback を拡大 (デフォルト 4 時間、最大 168 時間=1 週間)
    """
    try:
        # Pragmatic Play master API からリアルタイム取得
        bridge = get_bridge()
        if bridge._running:
            lobby_raw = bridge.get_lobby()
            if lobby_raw.get("ok"):
                from lobby_monitor import WHITELIST, BLACKLIST
                entries = []
                for t in lobby_raw["tables"]:
                    tn = t["table_name"]
                    seq = t["seq"]
                    info = classify_strict(seq)
                    enter_flag, enter_reason = check_entry(seq, info)
                    in_wl = tn in WHITELIST
                    in_bl = tn in BLACKLIST

                    score = 0
                    if in_wl: score += 100
                    if in_bl: score -= 100
                    if info["pattern"] == "縦流れ" and info.get("entry_ok_tate"): score += 60
                    if info["pattern"] == "横流れ" and info.get("entry_ok_yoko"): score += 50
                    if info["pattern"] in ("縦流れ", "横流れ") and not enter_flag: score += 20
                    if info["pattern"] == "不規則": score -= 30
                    if enter_flag: score += 30
                    score += min(info["n_cols"], 20)

                    entries.append({
                        "table": tn,
                        "in_whitelist": in_wl,
                        "in_blacklist": in_bl,
                        "pattern": info["pattern"],
                        "sub": info.get("sub", ""),
                        "pattern_reason": info["reason"],
                        "n_cols": info["n_cols"],
                        "n_hands": info["n_hands_nont"],
                        "p_cnt": info["p_cnt"],
                        "b_cnt": info["b_cnt"],
                        "t_cnt": info["t_cnt"],
                        "b_lead": info["b_lead"],
                        "entry_ok": enter_flag,
                        "entry_reason": enter_reason,
                        "features": info["features"],
                        "seq_tail": seq[-40:],
                        "players": t.get("players", 0),
                        "score": score,
                    })
                entries.sort(key=lambda x: -x["score"])
                return jsonify({
                    "source": "live",
                    "status": lobby_raw.get("status"),
                    "ws_connected": True,
                    "tables": entries,
                })
        # fallback: DB or lobby_state.json
        hours = int(request.args.get("hours", 4))
        hours = max(1, min(hours, 168))
        from lobby_monitor import lobby_from_db, lobby_from_scraper
        data = lobby_from_scraper()
        if data is None:
            data = lobby_from_db(lookback_hours=hours)
    except Exception as e:
        data = {"source": "error", "error": str(e), "tables": []}
    return jsonify(data)


# ============================================================
# Scraper 制御 (BaccaratScraper bg thread)
# ============================================================

@app.route("/api/scraper/start", methods=["POST"])
def api_scraper_start():
    ret = get_bridge().start()
    return jsonify(ret)


@app.route("/api/scraper/stop", methods=["POST"])
def api_scraper_stop():
    ret = get_bridge().stop()
    return jsonify(ret)


@app.route("/api/scraper/status")
def api_scraper_status():
    return jsonify(get_bridge().get_status())


@app.route("/api/session/focus_table", methods=["POST"])
def api_session_focus_table():
    """ロビーのカードクリックから呼ぶ総合エンドポイント

    - セッション未開始なら自動で開始
    - current_table を設定
    - auto_follow_scraper を ON
    - scraper のライブ seq で完全同期
    """
    data = request.json or {}
    tname = (data.get("table_name") or "").strip()
    if not tname:
        return jsonify({"ok": False, "error": "table_name 必須"}), 400

    bridge = get_bridge()
    if not bridge._running:
        return jsonify({"ok": False, "error": "scraper が起動していません。先に scraper を起動してください"}), 400

    # scraper からライブ seq を取得
    r = bridge.get_table_bead_road(tname)
    if not r.get("ok"):
        return jsonify({"ok": False, "error": r.get("error", "unknown")}), 400
    live_seq = r["seq"]

    # セッション開始 or テーブル切替
    if not SESSION.active:
        SESSION.start(tname)
        SESSION._log("AUTO", f"セッション自動開始: {tname}")
    else:
        SESSION.change_table(tname)

    # Seq を scraper のライブデータで初期化
    SESSION.seq = list(live_seq)
    SESSION.entered = False
    SESSION.entry_pattern = None
    SESSION.entry_hand_idx = None
    SESSION.losing_streak = 0
    SESSION.pending_bet = None

    # 全履歴で pattern 判定 → enter 判定
    info = classify_strict(live_seq)
    enter_flag, enter_reason = check_entry(live_seq, info)
    if enter_flag:
        SESSION.entered = True
        SESSION.entry_pattern = info["pattern"]
        SESSION.entry_hand_idx = len(SESSION.seq)
        SESSION._log("ENTER", f"{info['pattern']} — {enter_reason} (初期ロード)")

    SESSION.auto_follow_scraper = True
    SESSION._log("FOCUS", f"{tname} にフォーカス ({len(live_seq)} hand)")
    return jsonify({"ok": True, "seq_len": len(live_seq), "entered": SESSION.entered, "pattern": info["pattern"]})


@app.route("/api/session/exit_table", methods=["POST"])
def api_session_exit_table():
    """現テーブルから退室 (次のテーブルを選ぶ準備状態に)"""
    if not SESSION.active:
        return jsonify({"ok": False, "error": "セッション未開始"}), 400
    prev_table = SESSION.current_table
    # Shoe 状態リセット (ただし tracker / bet_history / action_log は保持)
    SESSION.current_table = ""
    SESSION.seq = []
    SESSION.entered = False
    SESSION.entry_pattern = None
    SESSION.entry_hand_idx = None
    SESSION.losing_streak = 0
    SESSION.pending_bet = None
    SESSION.auto_follow_scraper = False
    SESSION._log("EXIT_TABLE", f"{prev_table} 退室 — 次テーブル待機")
    return jsonify({"ok": True, "prev_table": prev_table})


@app.route("/api/scraper/sync_current_table", methods=["POST"])
def api_scraper_sync_current_table():
    """現セッションのテーブル名を scraper のライブ bead road と同期する"""
    if not SESSION.active:
        return jsonify({"ok": False, "error": "セッションが起動していません"}), 400
    bridge = get_bridge()
    if not bridge._running:
        return jsonify({"ok": False, "error": "scraper が起動していません"}), 400
    r = bridge.get_table_bead_road(SESSION.current_table)
    if not r.get("ok"):
        return jsonify(r), 400
    live_seq = r["seq"]
    # ローカル seq と突合: ライブが長ければ末尾差分を追加入力
    local_pb = "".join(ch for ch in SESSION.seq if ch in ("P", "B"))
    if not live_seq.startswith(local_pb):
        # 乖離している → 完全上書きモード
        SESSION.seq = list(live_seq)
        SESSION._log("SYNC", f"scraper と乖離を検知、ローカルを上書き (len={len(live_seq)})")
    else:
        # 末尾差分のみ追加
        tail = live_seq[len(local_pb):]
        for ch in tail:
            SESSION.add_hand(ch)
    SESSION.auto_follow_scraper = True
    return jsonify({"ok": True, "synced_len": len(live_seq), "new_hands": len(live_seq) - len(local_pb)})


@app.route("/api/scraper/set_follow", methods=["POST"])
def api_scraper_set_follow():
    """auto_follow_scraper フラグの切替"""
    flag = bool((request.json or {}).get("enabled", False))
    SESSION.auto_follow_scraper = flag
    SESSION._log("FOLLOW", f"auto_follow_scraper = {flag}")
    return jsonify({"ok": True, "auto_follow_scraper": flag})


@app.route("/api/scraper/manual_login", methods=["POST"])
def api_scraper_manual_login():
    """手動ログインヘルパーを別プロセスで起動

    scraper の自動ログインが失敗する時用。
    user が Camoufox で手動で Stake にログインし、Evolution ロビーに移動、
    プロファイルが保存されたらブラウザを閉じる。
    以降の scraper 起動が成功する。
    """
    import subprocess
    try:
        # scraper が動いていたら先に止める (プロファイル競合防止)
        bridge = get_bridge()
        if bridge._running:
            return jsonify({
                "ok": False,
                "error": "scraper 稼働中。先に scraper を停止してください",
            }), 400

        here = Path(__file__).parent
        script = here / "manual_login.py"
        if not script.exists():
            return jsonify({"ok": False, "error": f"{script} が見つかりません"}), 500

        # Windows: .bat をエクスプローラー経由で起動 (CREATE_NEW_CONSOLE より確実)
        if sys.platform == "win32":
            import os
            bat = here / "manual_login.bat"
            if bat.exists():
                os.startfile(str(bat))
                return jsonify({"ok": True, "method": "startfile_bat"})
            # .bat が無い場合は subprocess フォールバック
            proc = subprocess.Popen(
                [sys.executable, str(script)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=str(here),
            )
        else:
            proc = subprocess.Popen([sys.executable, str(script)], cwd=str(here))
        return jsonify({"ok": True, "pid": proc.pid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/session/chart_data")
def api_session_chart_data():
    """セッション内の equity / 勝率 curve 用データ"""
    equity_points = []
    wr_points = []
    cum_pnl = 0
    wins = 0
    for i, b in enumerate(SESSION.bet_history, start=1):
        cum_pnl += b["pnl"]
        if b["won"]:
            wins += 1
        equity_points.append({"i": i, "pnl": cum_pnl, "won": b["won"], "unit": b["unit"]})
        wr_points.append({"i": i, "wr": wins / i * 100})
    return jsonify({
        "equity": equity_points,
        "win_rate": wr_points,
        "summary": SESSION.summary(),
    })


@app.route("/api/debug/scraper_state")
def api_debug_scraper_state():
    """診断用: Pragmatic bridge の状態を dump"""
    bridge = get_bridge()
    st = bridge.get_status()
    lobby = bridge.get_lobby()
    tables_with_seq = [(t["table_name"], len(t["seq"])) for t in lobby.get("tables", []) if t["seq"]]
    tables_empty = [t["table_name"] for t in lobby.get("tables", []) if not t["seq"]]
    return jsonify({
        "ok": True,
        "bridge_status": st,
        "total_tables": len(lobby.get("tables", [])),
        "tables_with_seq": sorted(tables_with_seq, key=lambda x: -x[1])[:30],
        "tables_empty": tables_empty[:15],
    })


@app.route("/api/learning/stats")
def api_learning_stats():
    """AI 学習統計 (全体 / pattern別 / テーブル別)"""
    return jsonify(learning.overall_stats())


@app.route("/api/tracker/sets")
def api_tracker_sets():
    return jsonify({
        "sets": [
            {
                "idx": s.set_index,
                "results": s.results,
                "wins": s.wins,
                "losses": s.losses,
                "overshoot": s.overshoot,
                "slashed": s.slashed,
                "used_unit": OLD_SEQ[min(s.used_unit_idx, len(OLD_SEQ) - 1)],
                "set_profit": s.set_profit,
                "cumulative": s.cumulative_profit,
            }
            for s in SESSION.tracker.sets
        ],
        "current_turns": "".join(SESSION.tracker.current_turns),
        "current_unit": OLD_SEQ[min(SESSION.tracker.current_unit_idx, len(OLD_SEQ) - 1)],
    })


if __name__ == "__main__":
    # Windows 文字化け対策
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    # 起動時に前回のセッション・bridge 状態をクリア
    SESSION.reset()
    print("=" * 60)
    print("Laplace Copilot GUI v2 — ba (Pragmatic Play)")
    print("=" * 60)
    print("起動: http://127.0.0.1:5050")
    print("停止: Ctrl+C")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False, threaded=False)
