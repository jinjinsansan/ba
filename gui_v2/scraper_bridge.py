"""BaccaratScraper ブリッジ (Flask バックエンドから既存 scraper.py を利用)

既存 ba/scraper.py の BaccaratScraper を background thread で起動し、
Flask から安全にアクセスできるよう getter を提供する。

スレッド設計:
  - bg thread: Camoufox + Playwright 操作すべて (start, is_alive, stop)
  - Flask thread: Python dict の getter だけ読む (scraper 内の _lock で保護済)

getter が安全なのは:
  scraper.get_all_table_configs() / get_raw_history() / get_players_count() が
  Python-native dict を lock 下でコピー返却するだけで、Playwright オブジェクトを触らないため。
"""
from __future__ import annotations
import sys
import threading
import time
import traceback
from pathlib import Path

# ba/ ディレクトリを import path に追加
BA_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BA_DIR))


def _raw_to_pb_sequence(raw_entries: list) -> str:
    """Evolution Big Road raw entries → P/B 文字列 (T は無視)

    raw_entries: [{"pos":[col,row], "c":"B"/"R", "s":score, "ties":n, "pp":bool, "bp":bool}, ...]
    c="B" (Blue) = Player, c="R" (Red) = Banker
    """
    seq = []
    for e in raw_entries:
        if isinstance(e, dict):
            c = e.get("c", "")
            if c == "B":
                seq.append("P")
            elif c == "R":
                seq.append("B")
    return "".join(seq)


class ScraperBridge:
    """BaccaratScraper を bg thread で管理"""

    def __init__(self):
        self.scraper = None  # BaccaratScraper インスタンス (bg thread で作成)
        self._thread: threading.Thread | None = None
        self._running = False
        self._stop_requested = False

        # 状態 (bg thread のみ書く, Flask thread は読むだけ)
        self._status = "stopped"
        self._last_error = ""
        self._last_heartbeat = 0.0
        self._ws_connected = False
        self._browser_alive = False
        self._boot_started_at = 0.0

    # ------ Public API ------

    def start(self) -> dict:
        """bg thread を起動して scraper を立ち上げる"""
        if self._running:
            return {"ok": False, "error": "既に起動中です"}
        self._stop_requested = False
        self._running = True
        self._status = "booting"
        self._last_error = ""
        self._boot_started_at = time.time()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ScraperBridge")
        self._thread.start()
        return {"ok": True}

    def stop(self) -> dict:
        """bg thread に停止要求 + プロファイル lock 解放 cooldown"""
        if not self._running:
            return {"ok": False, "error": "起動していません"}
        self._stop_requested = True
        # scraper.stop() は bg thread から呼ばせる (Playwright スレッド制約)
        if self._thread:
            self._thread.join(timeout=30)
        # Firefox プロファイルロック解放待ち (Windows: parent.lock が消えるまで)
        import time as _time
        for _ in range(10):  # 最大 5 秒
            try:
                from pathlib import Path as _P
                lock = _P(__file__).resolve().parent.parent / "auth_state" / "camoufox_profile" / "parent.lock"
                if not lock.exists():
                    break
            except Exception:
                break
            _time.sleep(0.5)
        return {"ok": True}

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "status": self._status,
            "ws_connected": self._ws_connected,
            "browser_alive": self._browser_alive,
            "last_heartbeat": self._last_heartbeat,
            "seconds_since_heartbeat": (time.time() - self._last_heartbeat) if self._last_heartbeat else None,
            "last_error": self._last_error,
            "boot_started_at": self._boot_started_at,
            "boot_elapsed_sec": (time.time() - self._boot_started_at) if self._boot_started_at else 0,
        }

    def get_lobby(self) -> dict:
        """全テーブルの現 bead road を P/B 文字列で返す"""
        if not self.scraper:
            return {"source": "scraper", "ok": False, "status": self._status, "tables": []}

        try:
            configs = self.scraper.get_all_table_configs()
            players = self.scraper.get_players_count()
            tables = []
            for tid, cfg in configs.items():
                raw = self.scraper.get_raw_history(tid)
                seq = _raw_to_pb_sequence(raw)
                tables.append({
                    "table_id": tid,
                    "table_name": cfg.get("title", "?"),
                    "gt": cfg.get("gt", ""),
                    "seq": seq,
                    "n_raw": len(raw),
                    "players": players.get(tid, 0) if isinstance(players, dict) else 0,
                })
        except Exception as e:
            return {"source": "scraper", "ok": False, "error": str(e), "tables": []}

        return {
            "source": "scraper",
            "ok": True,
            "status": self._status,
            "ws_connected": self._ws_connected,
            "tables": tables,
        }

    def get_table_bead_road(self, table_name: str) -> dict:
        """特定テーブル名の現 bead road を取得 (table_id でなく title マッチ)"""
        if not self.scraper:
            return {"ok": False, "status": self._status, "seq": ""}
        try:
            configs = self.scraper.get_all_table_configs()
            target_tid = None
            for tid, cfg in configs.items():
                if cfg.get("title", "").strip() == table_name.strip():
                    target_tid = tid
                    break
            if target_tid is None:
                return {"ok": False, "error": f"table '{table_name}' がロビーに見当たりません", "seq": ""}
            raw = self.scraper.get_raw_history(target_tid)
            seq = _raw_to_pb_sequence(raw)
            return {"ok": True, "table_id": target_tid, "seq": seq, "n_raw": len(raw)}
        except Exception as e:
            return {"ok": False, "error": str(e), "seq": ""}

    # ------ Background Loop ------

    def _run_loop(self):
        """bg thread: Camoufox launch + WS setup + keep-alive monitoring"""
        try:
            from scraper import BaccaratScraper
            self._status = "launching Camoufox"
            self.scraper = BaccaratScraper()
            # 全テーブル監視モード
            try:
                self.scraper.table_name = "all"
            except Exception:
                pass

            self.scraper.start()
            self._status = "setting up WS intercept"
            self.scraper.setup_ws_intercept()

            # 初期ロード待機
            self._status = "waiting initial lobby data (12s)"
            for _ in range(12):
                if self._stop_requested:
                    break
                time.sleep(1)

            self._status = "running"
            self._last_heartbeat = time.time()
            _loop_tick = 0
            _SUBSCRIBE_RETRY_INTERVAL = 30  # 秒ごとに histories 不足チェック

            # メインループ: WS 接続確認と再接続
            while self._running and not self._stop_requested:
                try:
                    self._browser_alive = self.scraper.is_alive()
                    self._ws_connected = bool(getattr(self.scraper, "_evo_ws_connected", False))
                    self._last_heartbeat = time.time()
                    _loop_tick += 1

                    # WS 沈黙監視
                    silence = 0
                    try:
                        silence = self.scraper.seconds_since_last_ws_message()
                    except Exception:
                        pass

                    if not self._browser_alive:
                        self._status = "browser dead — scraper を停止してください"
                        time.sleep(5)
                        continue

                    if silence and silence > 300:
                        self._status = f"WS silent {silence:.0f}s — reloading lobby"
                        try:
                            self.scraper.reload_lobby()
                        except Exception as e:
                            self._last_error = f"reload error: {e}"
                    else:
                        # histories 不足チェック: 30秒ごとに subscribe 再送
                        if _loop_tick % (_SUBSCRIBE_RETRY_INTERVAL // 5) == 0:
                            try:
                                self.scraper.retry_subscribe_if_needed(min_tables=40)
                            except Exception as _sub_e:
                                pass
                        with self.scraper._lock:
                            n_hist = sum(1 for h in self.scraper._evo_table_raw_histories.values() if h)
                        n_target = len(getattr(self.scraper, '_target_table_ids', set()))
                        self._status = (
                            f"running (WS={'OK' if self._ws_connected else '...'}"
                            f" hist={n_hist}/{n_target})"
                        )

                except Exception as e:
                    self._last_error = f"loop: {e}\n{traceback.format_exc()[:500]}"
                    self._status = f"loop error: {e}"

                time.sleep(5)

        except Exception as e:
            self._last_error = f"startup: {e}\n{traceback.format_exc()[:1000]}"
            self._status = f"failed: {e}"
        finally:
            if self.scraper:
                try:
                    self.scraper.stop()
                except Exception:
                    pass
            self.scraper = None
            self._running = False
            self._status = "stopped"
            self._ws_connected = False
            self._browser_alive = False


# ============================================================
# シングルトン (Flask app から参照)
# ============================================================
_BRIDGE = ScraperBridge()


def get_bridge() -> ScraperBridge:
    return _BRIDGE
