"""テーブル入場 + BET操作

Evolutionバカラテーブルへの入場、BET実行、結果確認、退出を管理する。
全操作にHumanizerを通して人間的な振る舞いを実現する。
"""
import time
import asyncio
import logging

from humanize import Humanizer

logger = logging.getLogger("baccarat.executor")


class BetExecutor:
    """ブラウザ操作でテーブル入場とBETを実行"""

    def __init__(self, page, humanizer: Humanizer, config: dict):
        self.page = page
        self.humanizer = humanizer
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
        self.demo_mode = config.get("demo_mode", True)
        self.max_shoes_per_table = config.get("max_shoes_per_table", 3)
        self.shoes_at_table = 0

    async def enter_table(self, table_id: str, table_name: str) -> bool:
        """ロビーからテーブルに入場"""
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル入場: {table_name} ({table_id})")
            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            return True

        try:
            logger.info(f"テーブル入場: {table_name} ({table_id})")

            # テーブルサムネイルをクリック
            selectors = [
                f'[data-table-id="{table_id}"]',
                f'[data-id="{table_id}"]',
                f'div:has-text("{table_name}")',
            ]

            entered = False
            for sel in selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        await self.humanizer.click_element(self.page, sel)
                        entered = True
                        break
                except Exception:
                    continue

            if not entered:
                logger.warning(f"テーブル要素が見つかりません: {table_id}")
                return False

            await self.humanizer.wait_human_like(3.0, 6.0)

            # テーブル画面がロードされたか確認
            bet_area = self.page.locator(
                '.bet-area, [class*="bet-spot"], [class*="BetSpot"], '
                '[class*="player-bet"], [class*="banker-bet"]'
            )
            for _ in range(10):
                if bet_area.count() > 0:
                    break
                await asyncio.sleep(1)

            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            logger.info(f"テーブル入場成功: {table_name}")
            return True

        except Exception as e:
            logger.error(f"テーブル入場エラー: {e}")
            return False

    async def place_bet(self, side: str, amount: float) -> bool:
        """BETを実行: side = 'player' or 'banker'"""
        if self.demo_mode:
            logger.info(f"[DEMO] BET: {side} ${amount:.2f}")
            return True

        try:
            logger.info(f"BET実行: {side} ${amount:.2f}")

            # 1. チップ額を選択
            chip_selected = await self._select_chip(amount)
            if not chip_selected:
                logger.warning("チップ選択失敗")
                return False

            await self.humanizer.wait_human_like(0.3, 0.8)

            # 2. BETエリアをクリック
            bet_selectors = {
                "player": [
                    '[class*="player" i][class*="bet" i]',
                    '[data-bet-spot="player"]',
                    '.player-bet-area',
                    'text=PLAYER',
                ],
                "banker": [
                    '[class*="banker" i][class*="bet" i]',
                    '[data-bet-spot="banker"]',
                    '.banker-bet-area',
                    'text=BANKER',
                ],
            }

            selectors = bet_selectors.get(side, [])
            bet_placed = False
            for sel in selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        await self.humanizer.click_element(self.page, sel)
                        bet_placed = True
                        break
                except Exception:
                    continue

            if not bet_placed:
                logger.warning(f"BETエリアが見つかりません: {side}")
                return False

            await self.humanizer.wait_human_like(0.3, 0.8)

            # 3. 確定ボタンをクリック（必要な場合）
            confirm_selectors = [
                'button:has-text("Confirm")',
                'button:has-text("確定")',
                '[class*="confirm" i]',
                '[class*="submit" i]',
            ]
            for sel in confirm_selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        await self.humanizer.click_element(self.page, sel)
                        break
                except Exception:
                    continue

            logger.info(f"BET完了: {side} ${amount:.2f}")
            return True

        except Exception as e:
            logger.error(f"BETエラー: {e}")
            return False

    async def _select_chip(self, amount: float) -> bool:
        """チップ額を選択"""
        try:
            chip_selectors = [
                f'[data-value="{amount}"]',
                f'[data-chip="{amount}"]',
                f'button:has-text("{amount}")',
                f'[class*="chip"]:has-text("{amount}")',
            ]

            for sel in chip_selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        await self.humanizer.click_element(self.page, sel)
                        return True
                except Exception:
                    continue

            # フォールバック: 最小チップを選択
            chip = self.page.locator('[class*="chip" i]').first
            if chip.is_visible():
                box = chip.bounding_box()
                if box:
                    await self.humanizer.click_with_offset(
                        self.page,
                        int(box["x"] + box["width"] / 2),
                        int(box["y"] + box["height"] / 2),
                    )
                    return True

            return False
        except Exception as e:
            logger.error(f"チップ選択エラー: {e}")
            return False

    async def wait_for_result(self, timeout: float = 60) -> str | None:
        """ラウンド結果を待機して返す (player/banker/tie/None)"""
        if self.demo_mode:
            return None

        try:
            result_selectors = [
                '[class*="result" i]',
                '[class*="winner" i]',
                '[class*="outcome" i]',
            ]

            deadline = time.time() + timeout
            while time.time() < deadline:
                for sel in result_selectors:
                    try:
                        locator = self.page.locator(sel)
                        if locator.count() > 0 and locator.first.is_visible():
                            text = locator.first.inner_text().lower()
                            for result in ("player", "banker", "tie"):
                                if result in text:
                                    return result
                    except Exception:
                        continue
                await asyncio.sleep(1)

            return None
        except Exception as e:
            logger.error(f"結果待機エラー: {e}")
            return None

    async def exit_table(self) -> bool:
        """テーブルを退出してロビーに戻る"""
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル退出: {self.current_table_name}")
            self.in_table = False
            self.current_table_id = ""
            self.current_table_name = ""
            return True

        try:
            logger.info(f"テーブル退出: {self.current_table_name}")

            back_selectors = [
                'button:has-text("Back")',
                'button:has-text("戻る")',
                '[class*="back" i]',
                '[class*="close" i]',
                '[class*="lobby" i]',
            ]

            exited = False
            for sel in back_selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        await self.humanizer.click_element(self.page, sel)
                        exited = True
                        break
                except Exception:
                    continue

            if not exited:
                # フォールバック: ロビーURLに直接遷移
                from config import BACCARAT_LOBBY_URL
                self.page.goto(BACCARAT_LOBBY_URL, wait_until="domcontentloaded", timeout=30000)

            await self.humanizer.wait_human_like(2.0, 4.0)

            self.in_table = False
            self.current_table_id = ""
            self.current_table_name = ""
            logger.info("テーブル退出完了")
            return True

        except Exception as e:
            logger.error(f"テーブル退出エラー: {e}")
            self.in_table = False
            return False

    def should_leave_table(self, shoe_count: int) -> bool:
        """テーブル退出判断 (最大シュー数チェック)"""
        return shoe_count >= self.max_shoes_per_table

    def increment_shoe(self):
        """テーブルでのシュー数をインクリメント"""
        self.shoes_at_table += 1
