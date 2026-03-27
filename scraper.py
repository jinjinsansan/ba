"""Stake.com Evolution バカラ スクレイパー (ロビーWS方式)

EvolutionロビーのWebSocketから全バカラテーブルの結果をリアルタイム監視。
テーブル個別ページに入る必要なし — ロビーに留まるだけで全テーブルのデータが取得可能。

データソース:
  - lobby.configs: テーブルID→テーブル名マッピング
  - lobby.histories: 初期履歴（全テーブル分）
  - lobby.historyUpdated: リアルタイム結果更新

Camoufoxを使用してCloudflare Turnstileを回避する。
"""
import json
import re
import time
import logging
import threading
from datetime import datetime, timezone, timedelta

from camoufox.sync_api import Camoufox
from playwright.sync_api import Page, WebSocket

import config
from db import insert_round
from telegram_auth import ask_email_code

logger = logging.getLogger("baccarat.scraper")

JST = timezone(timedelta(hours=9))

# Evolution Big Road の色マッピング
# B = Blue = Player, R = Red = Banker
EVO_COLOR_MAP = {"B": "player", "R": "banker"}


class BaccaratScraper:
    """Stake.com EvolutionロビーWSを経由してバカラ結果を監視"""

    def __init__(self):
        self._camoufox_ctx = None
        self.browser = None
        self.page: Page | None = None
        self.table_name = config.TARGET_TABLE or ""
        self.round_count = 0
        self.last_round_id = ""
        self._ws_results: list[dict] = []
        self._new_shoe_signal = False
        self._lock = threading.Lock()

        # Evolution テーブル管理
        self._evo_table_configs: dict[str, dict] = {}  # table_id → config
        self._evo_table_histories: dict[str, list] = {}  # table_id → last known history
        self._target_table_id: str = ""  # 監視対象のEvolutionテーブルID
        self._evo_ws_connected = False

    def start(self):
        """ブラウザ起動 → ログイン → WS傍受設定 → ロビーに移動"""
        logger.info("Camoufox起動中...")
        self._camoufox_ctx = Camoufox(headless=True)
        self.browser = self._camoufox_ctx.__enter__()
        self.page = self.browser.new_page()

        # Cookie復元
        self._restore_cookies()

        # ログイン
        self._login()

        # ★ ロビーナビゲーション前にWSリスナーを登録
        # ロビーページロード時にEvolution WSが接続されるため、先に登録する必要がある
        self._register_ws_listener()

        # バカラロビーに移動（テーブルに入らない）
        self._navigate_to_lobby()

    def _restore_cookies(self):
        """保存済みCookieを復元"""
        cookie_file = config.AUTH_STATE_DIR / "stake_cookies.json"
        if not cookie_file.exists():
            logger.info("保存済みCookieなし")
            return
        try:
            with open(cookie_file) as f:
                cookies = json.load(f)
            self.page.context.add_cookies(cookies)
            logger.info(f"Cookie復元: {len(cookies)}件")
        except Exception as e:
            logger.warning(f"Cookie復元失敗: {e}")

    def _login(self):
        """Stake.comにログイン"""
        logger.info("Stakeにアクセス中...")
        self.page.goto(config.STAKE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)

        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "after_goto.png"))
        logger.info(f"ページタイトル: {self.page.title()}")

        if self._is_logged_in():
            logger.info("すでにログイン済み")
            return

        # ログインフォームを開く
        logger.info("ログインフォームを開く...")
        try:
            login_link = self.page.locator(
                'a:has-text("Login"), '
                'button:has-text("Login"), '
                'a:has-text("Sign in"), '
                'button:has-text("Sign in"), '
                'a:has-text("Sign In"), '
                'button:has-text("Sign In")'
            )
            if login_link.count() > 0:
                login_link.first.click()
                time.sleep(3)
        except Exception as e:
            logger.warning(f"ログインリンク検索: {e}")

        # メールアドレス入力
        logger.info("認証情報を入力中...")
        email_input = self.page.locator(
            'input[name="email"], input[type="email"], '
            'input[placeholder*="mail" i], input[placeholder*="Email"]'
        )
        if email_input.count() > 0:
            email_input.first.fill(config.STAKE_USERNAME)
        else:
            inputs = self.page.locator('input[type="text"], input:not([type])')
            if inputs.count() > 0:
                inputs.first.fill(config.STAKE_USERNAME)
        time.sleep(0.5)

        # パスワード入力
        pw_input = self.page.locator('input[type="password"]')
        if pw_input.count() > 0:
            pw_input.first.fill(config.STAKE_PASSWORD)
        time.sleep(0.5)

        # ログインボタン送信
        submit = self.page.locator(
            'button[type="submit"], '
            'button:has-text("Sign in"), '
            'button:has-text("Log in"), '
            'button:has-text("Login")'
        )
        if submit.count() > 0:
            submit.first.click()
        time.sleep(5)

        # Email Code（2FA）
        if not self._is_logged_in():
            self._handle_email_code()

        if self._is_logged_in():
            logger.info("ログイン成功")
            self._save_cookies()
        else:
            logger.warning("ログイン状態が不明（続行を試みます）")

    def _handle_email_code(self):
        """Email Code（2FA）画面を検出し、Telegram経由でコードを取得して入力"""
        logger.info("Email Code画面を確認中...")
        code_input = self.page.locator(
            'input[placeholder*="Code" i], '
            'input[name*="code" i], '
            'input[placeholder*="code" i]'
        )
        if code_input.count() == 0:
            try:
                body_text = self.page.locator("body").inner_text()[:500]
                if "email code" in body_text.lower() or "verification" in body_text.lower():
                    code_input = self.page.locator('input[type="text"]:visible')
                else:
                    return
            except Exception:
                return

        if code_input.count() == 0:
            return

        logger.info("📱 Telegram Bot経由でメール認証コードを待機中...")
        email_code = ask_email_code(timeout=300)
        if not email_code:
            logger.error("認証コードが取得できませんでした")
            return

        code_input.first.fill(email_code)
        time.sleep(0.5)

        submit = self.page.locator(
            'button:has-text("Sign in"), '
            'button:has-text("Sign In"), '
            'button[type="submit"]'
        )
        if submit.count() > 0:
            submit.first.click()
        time.sleep(8)

    def _save_cookies(self):
        """現在のCookieを保存"""
        try:
            cookie_file = config.AUTH_STATE_DIR / "stake_cookies.json"
            cookies = self.page.context.cookies()
            with open(cookie_file, "w") as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Cookie保存: {len(cookies)}件 → {cookie_file}")
        except Exception as e:
            logger.warning(f"Cookie保存エラー: {e}")

    def _is_logged_in(self) -> bool:
        """ログイン状態を確認"""
        try:
            indicators = self.page.locator(
                '[data-test="balance"], '
                'button:has-text("Wallet"), '
                '[class*="balance"], '
                '[class*="user-menu"]'
            )
            return indicators.count() > 0
        except Exception:
            return False

    def _navigate_to_lobby(self):
        """バカラロビーに移動（テーブルに入らない）"""
        logger.info("バカラロビーに移動中...")
        self.page.goto(
            config.BACCARAT_LOBBY_URL,
            wait_until="domcontentloaded",
            timeout=90000,
        )
        time.sleep(8)

        # Cookieバナーがあれば閉じる
        try:
            accept_btn = self.page.locator('button:has-text("Accept")')
            if accept_btn.count() > 0 and accept_btn.first.is_visible():
                accept_btn.first.click()
                time.sleep(1)
        except Exception:
            pass

        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "baccarat_lobby.png"))
        logger.info(f"バカラロビー到着 — タイトル: {self.page.title()}")

    def _register_ws_listener(self):
        """WebSocketリスナーを登録（ナビゲーション前に呼ぶこと）"""
        logger.info("WebSocket傍受を設定中...")

        def on_ws(ws: WebSocket):
            url = ws.url
            logger.info(f"WebSocket接続検出: {url[:120]}")

            # EvolutionロビーWSのみ対象
            if "evo-games.com" in url or "evolution" in url.lower():
                logger.info(f"✅ EvolutionロビーWS検出: {url[:120]}")
                self._evo_ws_connected = True

                def on_message(payload: str):
                    self._handle_evo_lobby_message(payload)

                def on_close():
                    logger.warning("❌ EvolutionロビーWS切断")
                    self._evo_ws_connected = False

                ws.on("framereceived", on_message)
                ws.on("close", on_close)

        self.page.on("websocket", on_ws)
        logger.info("WebSocket傍受設定完了")

    def setup_ws_intercept(self):
        """EvolutionロビーWSの接続を待機する（後方互換性のため残す）

        start()内で _register_ws_listener() → _navigate_to_lobby() の順で
        呼ばれるため、ここでは接続待機のみ行う。
        """
        # ロビーWSが接続されるまで待つ（最大30秒）
        for _ in range(30):
            if self._evo_ws_connected:
                logger.info("EvolutionロビーWS接続確認 ✅")
                break
            time.sleep(1)
        else:
            logger.warning("EvolutionロビーWSが検出されませんでした — ページをリロードして再試行")
            self.page.reload(wait_until="domcontentloaded", timeout=60000)
            time.sleep(10)
            # リロード後にもう一度待機
            for _ in range(30):
                if self._evo_ws_connected:
                    logger.info("EvolutionロビーWS接続確認（リロード後）✅")
                    break
                time.sleep(1)
            else:
                logger.error("EvolutionロビーWSが接続できませんでした")

    def _handle_evo_lobby_message(self, payload: str):
        """EvolutionロビーWSメッセージを処理"""
        try:
            if not isinstance(payload, str) or len(payload) < 10:
                return

            data = json.loads(payload)
            msg_type = data.get("type", "")
            args = data.get("args", {})

            if msg_type == "lobby.configs":
                self._process_configs(args)
            elif msg_type == "lobby.histories":
                self._process_histories(args)
            elif msg_type == "lobby.historyUpdated":
                self._process_history_updated(args)
            elif msg_type == "lobby.configsUpdated":
                self._process_configs_updated(args)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"EvolutionロビーWS解析エラー: {e}")

    def _process_configs(self, args: dict):
        """lobby.configs → テーブルID→設定マッピングを構築"""
        configs = args.get("configs", {})
        baccarat_tables = []

        for table_id, cfg in configs.items():
            gt = cfg.get("gt", "")
            # バカラ系テーブルのみ記録
            if gt in ("baccarat",):
                self._evo_table_configs[table_id] = cfg
                title = cfg.get("title", table_id)
                baccarat_tables.append(f"{title} ({table_id})")

        logger.info(f"Evolutionバカラテーブル: {len(baccarat_tables)}件検出")
        for t in baccarat_tables[:20]:
            logger.debug(f"  {t}")

        # ターゲットテーブルIDを決定
        self._resolve_target_table()

    def _process_configs_updated(self, args: dict):
        """lobby.configsUpdated → テーブル設定の差分更新"""
        configs = args.get("configs", {})
        for table_id, cfg in configs.items():
            gt = cfg.get("gt", "")
            if gt in ("baccarat",):
                self._evo_table_configs[table_id] = cfg

    def _resolve_target_table(self):
        """ユーザーの指定テーブル名からEvolutionテーブルIDを特定"""
        target_name = self.table_name.lower().strip()

        if not target_name:
            # 未指定の場合はJapanese Baccaratを優先、なければ最初のバカラ
            for tid, cfg in self._evo_table_configs.items():
                title = cfg.get("title", "")
                if "japanese" in title.lower() and "baccarat" in title.lower():
                    self._target_table_id = tid
                    self.table_name = title
                    logger.info(f"ターゲットテーブル自動選択: {title} ({tid})")
                    return

            # Japanese Baccaratが見つからない場合は最初のバカラ
            for tid, cfg in self._evo_table_configs.items():
                title = cfg.get("title", "")
                if "baccarat" in title.lower() and "lobby" not in title.lower():
                    self._target_table_id = tid
                    self.table_name = title
                    logger.info(f"ターゲットテーブルフォールバック: {title} ({tid})")
                    return

        # テーブル名で検索
        for tid, cfg in self._evo_table_configs.items():
            title = cfg.get("title", "")
            if target_name in title.lower():
                self._target_table_id = tid
                self.table_name = title
                logger.info(f"ターゲットテーブル特定: {title} ({tid})")
                return

        # 部分一致
        for tid, cfg in self._evo_table_configs.items():
            title = cfg.get("title", "")
            # 各単語が含まれるかチェック
            words = target_name.split()
            if all(w in title.lower() for w in words):
                self._target_table_id = tid
                self.table_name = title
                logger.info(f"ターゲットテーブル部分一致: {title} ({tid})")
                return

        logger.warning(f"ターゲットテーブル '{self.table_name}' が見つかりません")
        # 利用可能なテーブル一覧をログ
        for tid, cfg in list(self._evo_table_configs.items())[:10]:
            logger.info(f"  利用可能: {cfg.get('title', tid)} ({tid})")

    def _process_histories(self, args: dict):
        """lobby.histories → 初期履歴データを保存"""
        histories = args.get("histories", {})
        for table_id, hist_data in histories.items():
            results = hist_data.get("results", [])
            self._evo_table_histories[table_id] = results

        if self._target_table_id:
            hist = self._evo_table_histories.get(self._target_table_id, [])
            logger.info(
                f"初期履歴ロード: {self.table_name} ({self._target_table_id}) "
                f"— {len(hist)}件"
            )

    def _process_history_updated(self, args: dict):
        """lobby.historyUpdated → リアルタイムの結果更新を処理"""
        for table_id, update_data in args.items():
            # ターゲットテーブル以外はスキップ
            if table_id != self._target_table_id:
                continue

            new_results = update_data.get("results", [])
            if not new_results:
                continue

            # 前回の履歴と比較して新しい結果を検出
            old_results = self._evo_table_histories.get(table_id, [])
            added = self._diff_results(old_results, new_results)

            # 履歴を更新
            self._evo_table_histories[table_id] = new_results

            if added:
                for entry in added:
                    result_info = self._parse_evo_bead_entry(entry, table_id)
                    if result_info:
                        with self._lock:
                            self._ws_results.append(result_info)

                logger.info(
                    f"新結果 {len(added)}件: {self.table_name} — "
                    + " ".join(
                        self._format_entry_short(e) for e in added
                    )
                )

    def _diff_results(self, old: list, new: list) -> list:
        """前回と今回の履歴を比較して新しいエントリを返す"""
        if not old:
            # 初回 — 全部新しいが、全件通知は不要なので空を返す
            return []

        if not new:
            return []

        # Big Road形式の場合: pos配列の最後のエントリを比較
        # 新しい結果はリストの末尾に追加される
        old_len = len(old)
        new_len = len(new)

        if new_len > old_len:
            return new[old_len:]

        # 長さが同じでも最後のエントリが変わっている場合（Tie追加など）
        if new_len == old_len and new_len > 0:
            last_old = old[-1]
            last_new = new[-1]
            if isinstance(last_old, dict) and isinstance(last_new, dict):
                # ties数やペア情報が変わっていたら更新
                old_ties = last_old.get("ties", 0)
                new_ties = last_new.get("ties", 0)
                if new_ties > old_ties:
                    # Tieが追加された
                    return [last_new]

        return []

    def _parse_evo_bead_entry(self, entry: dict | str, table_id: str) -> dict | None:
        """Evolution Big Road/BeadのエントリからResult情報を抽出"""
        # BacBo形式（文字列リスト）
        if isinstance(entry, str):
            mapping = {"player": "player", "banker": "banker", "tie": "tie"}
            result = mapping.get(entry.lower())
            if result:
                return {
                    "round_id": f"evo_{table_id}_{int(time.time()*1000)}",
                    "result": result,
                    "player_score": None,
                    "banker_score": None,
                    "player_pair": False,
                    "banker_pair": False,
                }
            return None

        if not isinstance(entry, dict):
            return None

        # Big Road形式: {"pos":[col,row], "s":score, "c":"B"/"R", ...}
        color = entry.get("c", "")
        result = EVO_COLOR_MAP.get(color)

        if not result:
            return None

        score = entry.get("s")
        pos = entry.get("pos", [0, 0])
        ties = entry.get("ties", 0)
        pp = bool(entry.get("pp"))
        bp = bool(entry.get("bp"))
        nat = bool(entry.get("nat"))

        # ラウンドIDを位置情報から生成（ユニーク性のため）
        round_id = f"evo_{table_id}_c{pos[0]}r{pos[1]}_{int(time.time())}"

        # Tie情報: tiesが0より大きい場合、元の結果に加えてTieも記録
        result_info = {
            "round_id": round_id,
            "result": result,
            "player_score": score if result == "player" else None,
            "banker_score": score if result == "banker" else None,
            "player_pair": pp,
            "banker_pair": bp,
            "natural": nat,
            "ties": ties,
        }

        return result_info

    def _format_entry_short(self, entry) -> str:
        """結果エントリを短い表示形式に変換"""
        if isinstance(entry, str):
            mapping = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}
            return mapping.get(entry.lower(), "?")

        if isinstance(entry, dict):
            color = entry.get("c", "")
            score = entry.get("s", "?")
            ties = entry.get("ties", 0)
            emoji = {"B": "🔵P", "R": "🔴B"}.get(color, "?")
            tie_str = f"+🟢T×{ties}" if ties else ""
            return f"{emoji}({score}){tie_str}"

        return "?"

    def get_ws_results(self) -> list[dict]:
        """WebSocket経由で受信した未処理の結果を取得"""
        with self._lock:
            results = list(self._ws_results)
            self._ws_results.clear()
        return results

    def has_new_shoe_signal(self) -> bool:
        """新シュー信号があるかチェックして消費する"""
        if self._new_shoe_signal:
            self._new_shoe_signal = False
            return True
        return False

    def process_results(self, results: list[dict]) -> int:
        """結果をDBに保存。新規挿入数を返す"""
        new_count = 0
        for r in results:
            round_id = r.get("round_id", "")
            if not round_id or round_id == self.last_round_id:
                continue

            inserted = insert_round(
                table_name=self.table_name,
                round_id=round_id,
                result=r["result"],
                player_pair=r.get("player_pair", False),
                banker_pair=r.get("banker_pair", False),
                player_score=r.get("player_score"),
                banker_score=r.get("banker_score"),
            )
            if inserted:
                new_count += 1
                self.last_round_id = round_id
                self.round_count += 1
                emoji = {"player": "🔵P", "banker": "🔴B", "tie": "🟢T"}.get(r["result"], "?")
                score_str = ""
                if r.get("player_score") is not None and r.get("banker_score") is not None:
                    score_str = f" ({r['player_score']}:{r['banker_score']})"
                logger.info(
                    f"Round #{self.round_count}: {emoji}{score_str} "
                    f"[{self.table_name}] id={round_id}"
                )

        return new_count

    def poll_dom_results(self) -> list[dict]:
        """DOM経由の結果取得（ロビーWS方式では不要だが互換性のため残す）"""
        return []

    def take_screenshot(self, name: str = "current"):
        """デバッグ用スクリーンショット"""
        try:
            path = config.SCREENSHOTS_DIR / f"{name}.png"
            self.page.screenshot(path=str(path))
            logger.debug(f"スクリーンショット: {path}")
        except Exception as e:
            logger.error(f"スクリーンショットエラー: {e}")

    def is_alive(self) -> bool:
        """ブラウザセッションが生きているか"""
        try:
            self.page.evaluate("1 + 1")
            return self._evo_ws_connected
        except Exception:
            return False

    def stop(self):
        """ブラウザを閉じる"""
        try:
            if self._camoufox_ctx:
                self._camoufox_ctx.__exit__(None, None, None)
                self._camoufox_ctx = None
        except Exception as e:
            logger.error(f"停止エラー: {e}")
        logger.info("スクレイパー停止")
