"""テーブル入場 + BET操作 — frame_locator + クリック&チェック方式

実績:
  - frame_locator .click() はEvolution iframe内で正常動作
  - BETフェーズ検出不要: Playerクリック → TOTAL BET変化で成功判定
  - AI Vision はロビーゲームカード検出にのみ使用
"""
import re
import time
import logging

logger = logging.getLogger("baccarat.executor")


class BetExecutor:
    """Evolution バカラテーブルでのBET操作 (同期API)"""

    def __init__(self, page, config: dict):
        self.page = page
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
        self.demo_mode = config.get("demo_mode", True)
        self.max_shoes_per_table = config.get("max_shoes_per_table", 3)
        self.shoes_at_table = 0

    # === iframe取得 ===

    def _get_evo_frames(self):
        frames = []
        for frame in self.page.frames:
            url = frame.url or ""
            if "evo-games.com" in url and "/frontend/" in url:
                frames.append(frame)
        return frames

    def _get_evo_inner(self):
        """BETスポットがあるEvolutionフレーム"""
        frames = self._get_evo_frames()
        for frame in frames:
            try:
                if frame.evaluate("() => document.querySelectorAll('[data-betspot-destination]').length > 0"):
                    return frame
            except Exception:
                pass
        return frames[-1] if len(frames) >= 2 else (frames[0] if frames else None)

    def _get_evo_game(self):
        """Evolution外側iframe (hash設定用)"""
        frames = self._get_evo_frames()
        return frames[0] if frames else None

    def _get_evo_locator(self):
        """Playwright frame_locator チェーン"""
        outer = self.page.frame_locator('iframe[src*="evo-games.com"]').first
        inner = outer.frame_locator('iframe').first
        return inner

    # === テーブル入場 ===

    def enter_table(self, table_id: str, table_name: str) -> bool:
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル入場: {table_name} ({table_id})")
            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            return True

        try:
            logger.info(f"テーブル入場: {table_name} ({table_id})")

            game = self._get_evo_game()
            if not game:
                logger.warning("Evolution iframe未検出")
                return False

            game.evaluate(f"() => {{ window.location.hash = 'table_id={table_id}'; }}")
            time.sleep(25)

            # BETスポット待機
            inner = self._get_evo_inner()
            if inner:
                for _ in range(10):
                    if inner.evaluate("() => document.querySelectorAll('[data-betspot-destination]').length > 0"):
                        break
                    time.sleep(3)

            # スクリーンネームダイアログ処理
            self._dismiss_screen_name()

            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            self.shoes_at_table = 0
            logger.info(f"テーブル入場成功: {table_name}")
            return True

        except Exception as e:
            logger.error(f"テーブル入場エラー: {e}")
            return False

    def _dismiss_screen_name(self):
        """スクリーンネームダイアログ処理"""
        inner = self._get_evo_inner()
        if not inner:
            return
        try:
            has_dialog = inner.evaluate("() => document.body.innerText.toUpperCase().includes('SCREEN NAME')")
            if not has_dialog:
                return

            evo = self._get_evo_locator()
            inp = evo.locator('input[type="text"]').first
            inp.click(timeout=5000)
            inp.fill("BacPlayer1", timeout=5000)
            time.sleep(1)
            evo.locator('button:has-text("PLAY"), button:has-text("Play")').first.click(timeout=5000)
            time.sleep(3)
            logger.info("スクリーンネーム設定完了")
        except Exception as e:
            logger.debug(f"スクリーンネーム処理: {e}")

    # === BET実行 ===

    def place_bet(self, side: str, amount: float) -> bool:
        """BET実行: side='player'/'banker', amount=BET額

        方式: frame_locator .click() + クリック&チェックループ
        """
        if self.demo_mode:
            logger.info(f"[DEMO] BET: {side} ${amount:.2f}")
            return True

        try:
            logger.info(f"BET実行: {side} ${amount:.2f}")

            inner = self._get_evo_inner()
            evo = self._get_evo_locator()

            if not inner:
                logger.error("Evolution iframe未検出")
                return False

            # 1. チップスタック展開 + チップ選択 (force=True: 可視性チェックスキップ)
            try:
                evo.locator('[data-role="footer-perspective-chip-stack"]').first.click(timeout=5000, force=True)
                time.sleep(2)
            except Exception:
                pass

            chip_value = self._select_chip_value(amount)
            try:
                chip = evo.locator(f'[data-role="chip"][data-value="{chip_value}"]').first
                chip.click(timeout=5000, force=True)
                logger.info(f"チップ ${chip_value} 選択OK")
            except Exception as e:
                logger.warning(f"チップ選択失敗: {e}")
                try:
                    evo.locator('[data-role="chip"][data-value="1"]').first.click(timeout=5000, force=True)
                except Exception:
                    return False
            time.sleep(0.3)

            # 2. BETスポット クリック&チェック ループ (最大60秒)
            dest = "Player" if side == "player" else "Banker"
            player_loc = evo.locator(f'[data-betspot-destination="{dest}"]').first

            for i in range(60):
                total = self._get_total_bet(inner)
                if total > 0:
                    logger.info(f"BET成功! TOTAL BET = ${total:.2f}")
                    return True

                try:
                    player_loc.click(timeout=2000, force=True)
                except Exception:
                    evo = self._get_evo_locator()
                    player_loc = evo.locator(f'[data-betspot-destination="{dest}"]').first
                    try:
                        player_loc.click(timeout=2000, force=True)
                    except Exception:
                        pass

                if i % 10 == 0:
                    logger.info(f"  [{i}秒] クリック中... TOTAL BET=${total:.2f}")
                time.sleep(1)

            logger.warning("60秒経過 — BET配置できず")
            return False

        except Exception as e:
            logger.error(f"BETエラー: {e}")
            return False

    def _select_chip_value(self, amount: float) -> int:
        """金額に適したチップ値を返す"""
        chips = [1, 2, 5, 25, 100, 500]
        for c in chips:
            if c >= amount:
                return c
        return chips[-1]

    def _get_total_bet(self, inner) -> float:
        try:
            text = inner.evaluate("() => { const e = document.querySelector('[data-role=\"total-bet-label-value\"]'); return e ? e.textContent : ''; }")
            nums = re.findall(r'[\d.]+', text)
            return float(nums[0]) if nums else 0.0
        except Exception:
            return 0.0

    # === 結果待ち ===

    def wait_for_result(self, timeout: float = 60) -> str | None:
        """ラウンド結果を待機"""
        if self.demo_mode:
            return None

        inner = self._get_evo_inner()
        if not inner:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = inner.evaluate("""() => {
                    const t = document.body.innerText.toUpperCase();
                    if (t.includes('PLAYER WINS')) return 'player';
                    if (t.includes('BANKER WINS')) return 'banker';
                    if (t.includes('TIE')) return 'tie';
                    return null;
                }""")
                if r:
                    return r
            except Exception:
                inner = self._get_evo_inner()
            time.sleep(2)
        return None

    # === 残高 ===

    def get_balance(self) -> float | None:
        inner = self._get_evo_inner()
        if not inner:
            return None
        try:
            text = inner.evaluate("() => { const e = document.querySelector('[data-role=\"balance-label-value\"]'); return e ? e.textContent : ''; }")
            nums = re.findall(r'[\d.]+', text)
            return float(nums[0]) if nums else None
        except Exception:
            return None

    # === テーブル退出 ===

    def exit_table(self) -> bool:
        if self.demo_mode:
            logger.info(f"[DEMO] テーブル退出: {self.current_table_name}")
            self._reset_state()
            return True

        try:
            logger.info(f"テーブル退出: {self.current_table_name}")
            evo = self._get_evo_locator()
            try:
                evo.locator('[data-role="lobby-button"]').first.click(timeout=5000)
            except Exception:
                game = self._get_evo_game()
                if game:
                    game.evaluate("() => { window.location.hash = 'category=baccarat_sicbo'; }")
            time.sleep(5)
            self._reset_state()
            logger.info("テーブル退出完了")
            return True
        except Exception as e:
            logger.error(f"テーブル退出エラー: {e}")
            self._reset_state()
            return False

    def _reset_state(self):
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""

    def should_leave_table(self, shoe_count: int) -> bool:
        return shoe_count >= self.max_shoes_per_table

    def increment_shoe(self):
        self.shoes_at_table += 1
