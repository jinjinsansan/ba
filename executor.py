"""テーブル入場 + BET操作 (Evolution Gaming 実セレクタ)

Evolution iframe構造:
  Stake.com → iframe#game (evo-games.com/entry)
    → 内部iframe (evo-games.com/frontend/evo/r2/?iFrAmE=x)

ロビー:
  - テーブルカード: <ARTICLE class="Table--d130c">
  - クリック可能: class*="clickable--0e8a0" (サムネイル), class*="clickable--9bc55" (Info)
  - Native Dealerフィルタ: text="Native Dealer"

テーブル内:
  - BETスポット: data-betspot-destination="Player|Banker|Tie"
  - チップスタック: data-role="footer-perspective-chip-stack"
  - UNDO: data-role="undo-button"
  - DOUBLE: data-role="expanded-chip-stack-double-repeat-button-wrapper"
  - バランス: data-role="balance-label-value"
"""
import time
import asyncio
import logging

from humanize import Humanizer

logger = logging.getLogger("baccarat.executor")


class BetExecutor:
    """Evolution バカラテーブルでのBET操作"""

    def __init__(self, page, humanizer: Humanizer, config: dict):
        self.page = page
        self.humanizer = humanizer
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
        self.demo_mode = config.get("demo_mode", True)
        self.max_shoes_per_table = config.get("max_shoes_per_table", 3)
        self.shoes_at_table = 0
        self._evo_frame = None

    def _get_evo_inner_frame(self):
        """Evolution 最内部iframe (iFrAmE=x) を取得"""
        for frame in self.page.frames:
            url = frame.url or ""
            if "evo-games.com" in url and "iFrAmE" in url:
                return frame
        for frame in self.page.frames:
            url = frame.url or ""
            if "evo-games.com/frontend" in url and frame != self.page.main_frame:
                return frame
        return None

    def _get_evo_game_frame(self):
        """Evolution game frame (entry以外の最上位) を取得"""
        for frame in self.page.frames:
            url = frame.url or ""
            if "evo-games.com/frontend" in url and "iFrAmE" not in url:
                return frame
        return None

    async def enter_table(self, table_id: str, table_name: str) -> bool:
        """ロビーからテーブルに入場 (URL hash方式)"""
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル入場: {table_name} ({table_id})")
            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            return True

        try:
            logger.info(f"テーブル入場: {table_name} ({table_id})")

            # Step 1: Evolution iframe内で "Native Dealer" フィルタクリック
            inner = self._get_evo_inner_frame()
            if not inner:
                logger.warning("Evolution iframe未検出")
                return False

            try:
                inner.evaluate("""() => {
                    const els = Array.from(document.querySelectorAll('span, label, div'));
                    for (const el of els) {
                        if (el.textContent.trim() === 'Native Dealer') {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""")
                await self.humanizer.wait_human_like(3.0, 5.0)
            except Exception as e:
                logger.debug(f"Native Dealerクリック: {e}")

            # Step 2: テーブルカードをクリック
            try:
                clicked = inner.evaluate(f"""(tableName) => {{
                    const articles = Array.from(document.querySelectorAll('article'));
                    for (const art of articles) {{
                        const txt = (art.textContent || '').trim();
                        if (txt.includes(tableName)) {{
                            const tile = art.querySelector('[class*="clickable"]');
                            if (tile) {{ tile.click(); return true; }}
                            art.click();
                            return true;
                        }}
                    }}
                    return false;
                }}""", table_name)

                if not clicked:
                    # フォールバック: game frameのURL hashでテーブルID指定
                    game_frame = self._get_evo_game_frame()
                    if game_frame:
                        game_frame.evaluate(f"() => {{ window.location.hash = 'table_id={table_id}'; }}")
                        logger.info(f"URL hash方式でテーブル入場: {table_id}")
            except Exception as e:
                logger.warning(f"テーブルクリックエラー: {e}")
                # URL hash フォールバック
                game_frame = self._get_evo_game_frame()
                if game_frame:
                    game_frame.evaluate(f"() => {{ window.location.hash = 'table_id={table_id}'; }}")

            # Step 3: テーブルUIロード待機
            await self.humanizer.wait_human_like(8.0, 15.0)

            # BETスポットが表示されるまで待機
            self._evo_frame = self._get_evo_inner_frame()
            if self._evo_frame:
                for _ in range(20):
                    try:
                        has_bet = self._evo_frame.evaluate("""() => {
                            return document.querySelector('[data-betspot-destination]') !== null;
                        }""")
                        if has_bet:
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(2)

            # Step 4: スクリーンネームダイアログを閉じる (あれば)
            await self._dismiss_screen_name_dialog()

            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            logger.info(f"テーブル入場成功: {table_name}")
            return True

        except Exception as e:
            logger.error(f"テーブル入場エラー: {e}")
            return False

    async def _dismiss_screen_name_dialog(self):
        """'YOUR SCREEN NAME' ダイアログがあれば閉じる"""
        if not self._evo_frame:
            return
        try:
            self._evo_frame.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('button'));
                for (const el of els) {
                    const txt = (el.textContent || '').trim().toUpperCase();
                    if (txt === 'PLAY' || txt === 'OK' || txt === 'CLOSE' || txt === 'SKIP') {
                        el.click();
                        return true;
                    }
                }
                // Xボタンを探す
                const close = document.querySelector('[data-role="close-button"], [class*="close"]');
                if (close) { close.click(); return true; }
                return false;
            }""")
            await asyncio.sleep(1)
        except Exception:
            pass

    async def place_bet(self, side: str, amount: float) -> bool:
        """BETを実行: side = 'player' or 'banker'"""
        if self.demo_mode:
            logger.info(f"[DEMO] BET: {side} ${amount:.2f}")
            return True

        if not self._evo_frame:
            self._evo_frame = self._get_evo_inner_frame()
        if not self._evo_frame:
            logger.error("Evolution iframe未検出")
            return False

        try:
            logger.info(f"BET実行: {side} ${amount:.2f}")

            # 1. チップ選択 (data-role="chip-*" をクリック)
            chip_value = self._nearest_chip(amount)
            chip_selected = self._evo_frame.evaluate(f"""(chipVal) => {{
                // チップスタックを展開
                const stack = document.querySelector('[data-role="footer-perspective-chip-stack"]');
                if (stack && stack.classList.contains('collapsed')) {{
                    stack.click();
                }}
                // チップ額を探す
                const chips = document.querySelectorAll('[data-role*="chip"]');
                for (const chip of chips) {{
                    const txt = (chip.textContent || '').trim();
                    if (txt === String(chipVal) || txt === '$' + chipVal) {{
                        chip.click();
                        return true;
                    }}
                }}
                // フォールバック: denomination要素
                const denoms = document.querySelectorAll('[class*="denomination"], [class*="Denomination"]');
                for (const d of denoms) {{
                    const txt = (d.textContent || '').trim();
                    if (txt === String(chipVal)) {{
                        d.click();
                        return true;
                    }}
                }}
                return false;
            }}""", chip_value)

            if not chip_selected:
                logger.warning(f"チップ {chip_value} 選択失敗 — 最小チップを選択")
                self._evo_frame.evaluate("""() => {
                    const chips = document.querySelectorAll('[class*="denomination"], [data-role*="chip"]');
                    if (chips.length > 0) chips[0].click();
                }""")

            await self.humanizer.wait_human_like(0.3, 0.8)

            # 2. BETスポットをクリック
            dest = "Player" if side == "player" else "Banker"
            bet_placed = self._evo_frame.evaluate(f"""(dest) => {{
                const spot = document.querySelector('[data-betspot-destination="' + dest + '"]');
                if (spot) {{
                    spot.click();
                    return true;
                }}
                // フォールバック: data-role
                const spotByRole = document.querySelector('[data-role="bet-spot-' + dest + '"]');
                if (spotByRole) {{
                    spotByRole.click();
                    return true;
                }}
                return false;
            }}""", dest)

            if not bet_placed:
                logger.warning(f"BETスポット ({dest}) クリック失敗")
                return False

            logger.info(f"BET完了: {side} ${amount:.2f}")
            return True

        except Exception as e:
            logger.error(f"BETエラー: {e}")
            return False

    def _nearest_chip(self, amount: float) -> int:
        """金額に最も近いチップ額を返す"""
        chips = [1, 5, 25, 100, 500]
        return min(chips, key=lambda c: abs(c - amount))

    async def wait_for_result(self, timeout: float = 60) -> str | None:
        """ラウンド結果を待機 (WS経由で取得するため、ここではUI監視のフォールバック)"""
        if self.demo_mode:
            return None

        if not self._evo_frame:
            return None

        try:
            deadline = time.time() + timeout
            while time.time() < deadline:
                result = self._evo_frame.evaluate("""() => {
                    // 結果表示エリアを確認
                    const winnerEls = document.querySelectorAll('[data-role*="winner"], [class*="winner"]');
                    for (const el of winnerEls) {
                        const txt = (el.textContent || '').toLowerCase();
                        if (txt.includes('player wins')) return 'player';
                        if (txt.includes('banker wins')) return 'banker';
                        if (txt.includes('tie')) return 'tie';
                    }
                    return null;
                }""")
                if result:
                    return result
                await asyncio.sleep(2)
            return None
        except Exception as e:
            logger.error(f"結果待機エラー: {e}")
            return None

    async def undo_bet(self) -> bool:
        """直前のBETを取り消す"""
        if not self._evo_frame:
            return False
        try:
            return self._evo_frame.evaluate("""() => {
                const btn = document.querySelector('[data-role="undo-button"]');
                if (btn && !btn.classList.contains('Disabled')) {
                    btn.click();
                    return true;
                }
                return false;
            }""")
        except Exception:
            return False

    def get_balance(self) -> float | None:
        """現在の残高を取得"""
        if not self._evo_frame:
            self._evo_frame = self._get_evo_inner_frame()
        if not self._evo_frame:
            return None
        try:
            balance_text = self._evo_frame.evaluate("""() => {
                const el = document.querySelector('[data-role="balance-label-value"]');
                if (el) {
                    const val = el.getAttribute('data-balance-visible') || el.textContent || '';
                    return val.replace(/[^0-9.]/g, '');
                }
                return null;
            }""")
            if balance_text:
                return float(balance_text)
        except Exception:
            pass
        return None

    async def exit_table(self) -> bool:
        """テーブルを退出してロビーに戻る"""
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル退出: {self.current_table_name}")
            self.in_table = False
            self.current_table_id = ""
            self.current_table_name = ""
            self._evo_frame = None
            return True

        try:
            logger.info(f"テーブル退出: {self.current_table_name}")

            # Evolution iframe内の戻るボタン
            if self._evo_frame:
                self._evo_frame.evaluate("""() => {
                    const back = document.querySelector('[data-role="back-button"], [class*="backButton"]');
                    if (back) { back.click(); return true; }
                    // Xボタン
                    const close = document.querySelector('[data-role="close-button"]');
                    if (close) { close.click(); return true; }
                    return false;
                }""")

            await self.humanizer.wait_human_like(2.0, 4.0)

            # フォールバック: ロビーURLに直接遷移
            if self._evo_frame:
                game_frame = self._get_evo_game_frame()
                if game_frame:
                    current_url = game_frame.url
                    if "#" in current_url:
                        lobby_url = current_url.split("#")[0] + "#category=baccarat_sicbo"
                        game_frame.evaluate(f"() => {{ window.location.hash = 'category=baccarat_sicbo'; }}")

            self.in_table = False
            self.current_table_id = ""
            self.current_table_name = ""
            self._evo_frame = None
            logger.info("テーブル退出完了")
            return True

        except Exception as e:
            logger.error(f"テーブル退出エラー: {e}")
            self.in_table = False
            return False

    def should_leave_table(self, shoe_count: int) -> bool:
        return shoe_count >= self.max_shoes_per_table

    def increment_shoe(self):
        self.shoes_at_table += 1
