"""Stake.com Evolution バカラ スクレイパー

2つの方式を併用:
  1. WebSocket傍受: Evolutionのiframe内WSメッセージから結果を取得（高精度）
  2. DOMポーリング: 罫線(Road)のDOM要素から結果を読み取る（フォールバック）
"""
import json
import re
import time
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

from playwright.sync_api import (
    sync_playwright,
    Page,
    BrowserContext,
    Playwright,
    WebSocket,
)

import config
from db import insert_round

logger = logging.getLogger("baccarat.scraper")

JST = timezone(timedelta(hours=9))

# Evolution WSメッセージから結果を抽出するパターン
# Evolutionは結果をJSON形式でWebSocket経由で送信する
RESULT_PATTERNS = [
    # gameResult系
    r'"gameResult"',
    r'"result"',
    r'"outcome"',
    # バカラ固有
    r'"winner"',
    r'"playerScore"',
    r'"bankerScore"',
]


class BaccaratScraper:
    """Stake.com経由でEvolutionバカラの結果を監視"""

    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.table_name = config.TARGET_TABLE or ""
        self.round_count = 0
        self.last_round_id = ""
        self._ws_results: list[dict] = []

    def start(self):
        """ブラウザ起動 → ログイン → テーブル接続"""
        logger.info("Playwright起動中...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        # 認証状態の復元を試みる
        state_path = config.AUTH_STATE_DIR / "stake_auth.json"
        if state_path.exists():
            logger.info("認証状態を復元中...")
            self.context = self.browser.new_context(
                storage_state=str(state_path),
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self.page = self.context.new_page()
            self.page.goto(config.STAKE_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)

            # ログイン状態を確認
            if self._is_logged_in():
                logger.info("認証状態復元成功")
            else:
                logger.info("認証状態が期限切れ、再ログイン")
                self.context.close()
                self._fresh_login()
        else:
            self._fresh_login()

        # バカラテーブルに移動
        self._navigate_to_baccarat()

    def _fresh_login(self):
        """新規ログイン"""
        logger.info("Stakeにログイン中...")
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self.page = self.context.new_page()

        self.page.goto(config.STAKE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # ログインボタンをクリック
        try:
            # Stakeのログインボタン
            sign_in = self.page.locator(
                'button:has-text("Sign in"), '
                'a:has-text("Sign in"), '
                'button:has-text("Sign In"), '
                'a:has-text("Sign In"), '
                '[data-test="sign-in-button"]'
            )
            if sign_in.count() > 0:
                sign_in.first.click()
                time.sleep(2)
        except Exception as e:
            logger.warning(f"ログインボタン検索: {e}")

        # メールアドレス入力
        email_input = self.page.locator(
            'input[name="email"], '
            'input[type="email"], '
            'input[placeholder*="mail"], '
            'input[placeholder*="Email"]'
        )
        if email_input.count() > 0:
            email_input.first.fill(config.STAKE_USERNAME)
            time.sleep(0.5)
        else:
            # 別のフォーム構造を試す
            inputs = self.page.locator("input")
            for i in range(inputs.count()):
                inp = inputs.nth(i)
                input_type = inp.get_attribute("type") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                if input_type in ("email", "text") and i == 0:
                    inp.fill(config.STAKE_USERNAME)
                    break

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

        # スクリーンショット保存（デバッグ用）
        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "after_login.png"))

        if self._is_logged_in():
            logger.info("ログイン成功")
            # 認証状態を保存
            state_path = config.AUTH_STATE_DIR / "stake_auth.json"
            self.context.storage_state(path=str(state_path))
            logger.info("認証状態保存完了")
        else:
            logger.warning("ログイン状態が不明（続行を試みます）")

    def _is_logged_in(self) -> bool:
        """ログイン状態を確認"""
        try:
            # Stakeでログイン済みなら「Wallet」や残高表示がある
            indicators = self.page.locator(
                '[data-test="balance"], '
                'button:has-text("Wallet"), '
                '[class*="balance"], '
                '[class*="user-menu"]'
            )
            return indicators.count() > 0
        except Exception:
            return False

    def _navigate_to_baccarat(self):
        """バカラテーブルに移動"""
        logger.info("バカラロビーに移動中...")
        self.page.goto(
            config.BACCARAT_LOBBY_URL,
            wait_until="networkidle",
            timeout=60000,
        )
        time.sleep(5)

        self.page.screenshot(path=str(config.SCREENSHOTS_DIR / "baccarat_lobby.png"))
        logger.info("バカラロビー到着")

        # Evolution iframeを検出
        # Stakeはevolutionのゲームをiframeで埋め込む
        self._enter_evolution_iframe()

    def _enter_evolution_iframe(self):
        """Evolutionのiframeに入り、テーブルを選択"""
        time.sleep(5)

        # iframeの存在を確認
        iframes = self.page.frames
        logger.info(f"検出されたフレーム数: {len(iframes)}")
        for f in iframes:
            logger.info(f"  Frame: {f.name} URL: {f.url[:100]}")

        # Evolutionのフレームを見つける
        evo_frame = None
        for frame in iframes:
            url = frame.url.lower()
            if "evolution" in url or "evo" in url or "casino" in url:
                evo_frame = frame
                logger.info(f"Evolutionフレーム発見: {frame.url[:100]}")
                break

        if evo_frame:
            # フレーム内でバカラテーブルを選択
            self._select_table_in_frame(evo_frame)
        else:
            logger.info("Evolutionフレーム未検出 — ページ内直接検索を試みます")
            self._select_table_on_page()

    def _select_table_in_frame(self, frame):
        """Evolutionフレーム内でテーブルを選択"""
        time.sleep(3)

        # Speed Baccarat テーブルを探す
        target = self.table_name or "Speed Baccarat"
        try:
            table_elem = frame.locator(f'text="{target}"').first
            if table_elem.count() > 0:
                table_elem.click()
                self.table_name = target
                logger.info(f"テーブル選択: {target}")
                time.sleep(5)
                return
        except Exception:
            pass

        # フォールバック: 最初のバカラテーブルをクリック
        try:
            bac_tables = frame.locator('[class*="baccarat"], [class*="Baccarat"]')
            if bac_tables.count() > 0:
                bac_tables.first.click()
                self.table_name = "Baccarat (auto)"
                logger.info("最初のバカラテーブルを選択")
                time.sleep(5)
                return
        except Exception:
            pass

        logger.warning("テーブル自動選択に失敗 — 手動確認が必要かもしれません")

    def _select_table_on_page(self):
        """メインページ上でテーブルを選択"""
        # Stakeのバカラカードを直接クリック
        try:
            target = self.table_name or "Speed Baccarat"
            card = self.page.locator(f'text="{target}"').first
            if card.is_visible():
                card.click()
                self.table_name = target
                time.sleep(5)
                return
        except Exception:
            pass

        # Speed Baccarat A, B, C等
        for suffix in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", ""]:
            name = f"Speed Baccarat {suffix}".strip()
            try:
                elem = self.page.locator(f'text="{name}"').first
                if elem.is_visible():
                    elem.click()
                    self.table_name = name
                    logger.info(f"テーブル選択: {name}")
                    time.sleep(5)
                    return
            except Exception:
                continue

        # 最終手段: 何でもいいのでバカラテーブルを開く
        try:
            any_bac = self.page.locator(
                '[href*="baccarat"], '
                'a:has-text("Baccarat"), '
                'div:has-text("Baccarat")'
            ).first
            if any_bac.is_visible():
                any_bac.click()
                self.table_name = "Baccarat (fallback)"
                time.sleep(5)
        except Exception:
            logger.error("バカラテーブルが見つかりません")

    def setup_ws_intercept(self):
        """WebSocket通信の傍受を設定"""
        logger.info("WebSocket傍受を設定中...")

        def on_ws(ws: WebSocket):
            url = ws.url
            logger.info(f"WebSocket接続検出: {url[:100]}")

            def on_message(payload: str):
                self._handle_ws_message(payload)

            ws.on("framereceived", lambda payload: on_message(payload))

        self.page.on("websocket", on_ws)
        logger.info("WebSocket傍受設定完了")

    def _handle_ws_message(self, payload: str):
        """WebSocketメッセージを解析してバカラ結果を抽出"""
        try:
            # JSON形式のメッセージを解析
            if not isinstance(payload, str):
                return

            # Evolution固有のメッセージ形式を検出
            # 一般的なパターン: gameResult, roundResult, etc.
            data = None

            # 42["message", {...}] 形式 (Socket.IO)
            match = re.match(r'^\d+\["[^"]+",\s*(.+)\]$', payload, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except (json.JSONDecodeError, ValueError):
                    pass

            # 純粋なJSON
            if data is None:
                try:
                    data = json.loads(payload)
                except (json.JSONDecodeError, ValueError):
                    return

            # 結果データを探索
            result_info = self._extract_result(data)
            if result_info:
                self._ws_results.append(result_info)

        except Exception as e:
            # ノイズが多いのでdebugレベル
            logger.debug(f"WS解析エラー: {e}")

    def _extract_result(self, data: dict | list, depth: int = 0) -> dict | None:
        """再帰的にバカラ結果を探索"""
        if depth > 5:
            return None

        if isinstance(data, list):
            for item in data:
                result = self._extract_result(item, depth + 1)
                if result:
                    return result
            return None

        if not isinstance(data, dict):
            return None

        # Evolutionの典型的な結果フィールドを探す
        # パターン1: {"winner": "player"/"banker"/"tie"}
        winner = data.get("winner") or data.get("Winner")
        if winner and isinstance(winner, str) and winner.lower() in ("player", "banker", "tie"):
            return self._parse_evo_result(data, winner.lower())

        # パターン2: {"result": {"winner": ...}}
        result_obj = data.get("result") or data.get("gameResult") or data.get("roundResult")
        if isinstance(result_obj, dict):
            return self._extract_result(result_obj, depth + 1)

        # パターン3: {"outcome": "P"/"B"/"T"}
        outcome = data.get("outcome") or data.get("Outcome")
        if outcome and isinstance(outcome, str):
            mapping = {"p": "player", "b": "banker", "t": "tie",
                       "player": "player", "banker": "banker", "tie": "tie"}
            mapped = mapping.get(outcome.lower())
            if mapped:
                return self._parse_evo_result(data, mapped)

        # パターン4: playerScore / bankerScore の存在で判定
        ps = data.get("playerScore") or data.get("PlayerScore") or data.get("player_score")
        bs = data.get("bankerScore") or data.get("BankerScore") or data.get("banker_score")
        if ps is not None and bs is not None:
            try:
                p_score = int(ps)
                b_score = int(bs)
                if p_score > b_score:
                    winner = "player"
                elif b_score > p_score:
                    winner = "banker"
                else:
                    winner = "tie"
                return self._parse_evo_result(data, winner, p_score, b_score)
            except (ValueError, TypeError):
                pass

        # 再帰的に子オブジェクトを探索
        for key, val in data.items():
            if isinstance(val, (dict, list)):
                result = self._extract_result(val, depth + 1)
                if result:
                    return result

        return None

    def _parse_evo_result(
        self, data: dict, winner: str,
        p_score: int | None = None, b_score: int | None = None,
    ) -> dict:
        """Evolution結果データを統一フォーマットに変換"""
        if p_score is None:
            p_score = data.get("playerScore") or data.get("PlayerScore")
            if p_score is not None:
                p_score = int(p_score)
        if b_score is None:
            b_score = data.get("bankerScore") or data.get("BankerScore")
            if b_score is not None:
                b_score = int(b_score)

        round_id = (
            data.get("roundId") or data.get("RoundId")
            or data.get("gameId") or data.get("GameId")
            or data.get("id") or ""
        )

        player_pair = bool(
            data.get("playerPair") or data.get("PlayerPair")
            or data.get("isPlayerPair")
        )
        banker_pair = bool(
            data.get("bankerPair") or data.get("BankerPair")
            or data.get("isBankerPair")
        )

        return {
            "round_id": str(round_id),
            "result": winner,
            "player_score": p_score,
            "banker_score": b_score,
            "player_pair": player_pair,
            "banker_pair": banker_pair,
        }

    def poll_dom_results(self) -> list[dict]:
        """DOM上の罫線(Road)から結果を読み取る（フォールバック方式）"""
        results = []

        # Evolution iframeを探す
        for frame in self.page.frames:
            url = frame.url.lower()
            if "evolution" not in url and "evo" not in url:
                continue

            try:
                # Bead Road (珠盤路) のセルを読み取る
                # Evolutionは通常、赤=Banker、青=Player、緑=Tieで色分け
                cells = frame.locator(
                    '[class*="road"] [class*="cell"], '
                    '[class*="Road"] [class*="cell"], '
                    '[class*="bead"] [class*="item"], '
                    '[class*="history"] [class*="result"]'
                )

                for i in range(cells.count()):
                    cell = cells.nth(i)
                    classes = cell.get_attribute("class") or ""
                    text = cell.inner_text().strip().upper()

                    result = None
                    if "banker" in classes.lower() or "red" in classes.lower() or text == "B":
                        result = "banker"
                    elif "player" in classes.lower() or "blue" in classes.lower() or text == "P":
                        result = "player"
                    elif "tie" in classes.lower() or "green" in classes.lower() or text == "T":
                        result = "tie"

                    if result:
                        results.append({
                            "round_id": f"dom_{i}_{int(time.time())}",
                            "result": result,
                            "player_score": None,
                            "banker_score": None,
                            "player_pair": False,
                            "banker_pair": False,
                        })

            except Exception as e:
                logger.debug(f"DOM読み取りエラー: {e}")
                continue

        return results

    def get_ws_results(self) -> list[dict]:
        """WebSocket経由で受信した未処理の結果を取得"""
        results = list(self._ws_results)
        self._ws_results.clear()
        return results

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
            return True
        except Exception:
            return False

    def stop(self):
        """ブラウザを閉じる"""
        try:
            if self.context:
                # 認証状態を保存
                state_path = config.AUTH_STATE_DIR / "stake_auth.json"
                try:
                    self.context.storage_state(path=str(state_path))
                except Exception:
                    pass
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.error(f"停止エラー: {e}")
        logger.info("スクレイパー停止")
