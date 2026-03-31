"""テーブル入場 + BET操作 — ゲーム内WS状態ベース

設計:
  - ラウンド状態は GameWSMonitor (game_ws.py) が管理
  - executor は WS状態を基に「いつBETするか」「いつ結果を拾うか」を判断
  - DOM操作は最低限: チップ選択 + BETスポットクリック のみ
  - 結果検出・BETフェーズ検出は全てWS経由 (DOMポーリング廃止)
"""
import re
import time
import logging

logger = logging.getLogger("baccarat.executor")


class BetExecutor:
    def __init__(self, page, game_ws, config: dict):
        self.page = page
        self.game_ws = game_ws  # GameWSMonitor
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
        self.demo_mode = config.get("demo_mode", True)

    # ─── iframe取得 ───

    def _get_evo_frames(self):
        frames = []
        for frame in self.page.frames:
            url = frame.url or ""
            if "evo-games.com" in url and "/frontend/" in url:
                frames.append(frame)
        return frames

    def _get_evo_inner(self):
        frames = self._get_evo_frames()
        for frame in frames:
            try:
                if frame.evaluate("() => document.querySelectorAll('[data-betspot-destination]').length > 0"):
                    return frame
            except Exception:
                pass
        return frames[-1] if len(frames) >= 2 else (frames[0] if frames else None)

    def _get_evo_game(self):
        frames = self._get_evo_frames()
        return frames[0] if frames else None

    def _get_evo_locator(self):
        outer = self.page.frame_locator('iframe[src*="evo-games.com"]').first
        inner = outer.frame_locator('iframe').first
        return inner

    # ─── テーブル入場 ───

    def enter_table(self, table_id: str, table_name: str) -> bool:
        if self.demo_mode:
            logger.info(f"[DEMO] {table_name}に入ります")
            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            return True

        try:
            logger.info(f"{table_name}に入ります")
            self.game_ws.reset()

            game = self._get_evo_game()
            if not game:
                logger.error("Evolution iframe未検出")
                return False

            game.evaluate(f"() => {{ window.location.hash = 'table_id={table_id}'; }}")

            # BETスポットが出現するまで待機 (最大40秒)
            for i in range(20):
                time.sleep(2)
                inner = self._get_evo_inner()
                if inner:
                    try:
                        count = inner.evaluate("() => document.querySelectorAll('[data-betspot-destination]').length")
                        if count > 0:
                            logger.info(f"テーブル読込完了 ({(i+1)*2}秒)")
                            break
                    except Exception:
                        pass
            else:
                logger.error("テーブル読込タイムアウト (40秒)")
                return False

            # スクリーンネームダイアログ処理
            self._dismiss_screen_name()

            self.in_table = True
            self.current_table_id = table_id
            self.current_table_name = table_name
            logger.info(f"{table_name} 入場完了")
            return True

        except Exception as e:
            logger.error(f"テーブル入場エラー: {e}")
            return False

    def _dismiss_screen_name(self):
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
        except Exception:
            pass

    # ─── BETフェーズ待機 ───

    def wait_for_betting_phase(self, timeout: float = 120) -> bool:
        """1ラウンド見送り後、BETフェーズを待機 (WS + DOMハイブリッド)"""
        if self.demo_mode:
            return True
        return self.game_ws.wait_for_betting_phase(timeout, dom_checker=self._is_betting_phase_dom)

    def _is_betting_phase_dom(self) -> bool:
        """DOMでBETタイマー(円形カウントダウン)の表示を確認"""
        inner = self._get_evo_inner()
        if not inner:
            return False
        try:
            return inner.evaluate(
                '() => { const t = document.querySelector(\'[class*="timerCircleContainer"]\'); '
                'return t ? t.offsetParent !== null : false; }'
            )
        except Exception:
            return False

    # ─── BET実行 ───

    def place_bet(self, side: str, amount: float) -> bool:
        """チップ選択 → BETスポットクリック → WS受理確認

        Returns: True=BET受理, False=失敗
        """
        if self.demo_mode:
            logger.info(f"[DEMO] ${amount:.0f} {side.upper()} BET")
            return True

        logger.info(f"${amount:.0f} {side.upper()} BETします")

        evo = self._get_evo_locator()

        # 1. $1チップを常に選択
        if not self._select_chip(evo, 1):
            return False

        # 2. BETスポットをamount回クリック ($1 x N)
        dest = "Player" if side == "player" else "Banker"
        clicks_needed = int(amount)

        for click_i in range(clicks_needed):
            evo = self._get_evo_locator()
            bet_loc = evo.locator(f'[data-betspot-destination="{dest}"]').first
            clicked = False
            for attempt in range(5):
                try:
                    bet_loc.click(timeout=2000, force=True)
                    clicked = True
                    break
                except Exception:
                    time.sleep(0.3)
            if not clicked:
                logger.error(f"BETスポットクリック失敗 ({click_i+1}/{clicks_needed})")
                return False
            if click_i < clicks_needed - 1:
                time.sleep(0.3)

        # 3. TOTAL BET確認
        for _ in range(10):
            total = self._get_total_bet()
            if total > 0:
                logger.info(f"BET受理: ${total:.2f}")
                return True
            time.sleep(0.5)

        logger.error("BET受理確認タイムアウト")
        return False

    def _select_chip(self, evo, chip_value: int) -> bool:
        """チップ選択。スタック展開→チップクリック"""
        for retry in range(5):
            try:
                evo = self._get_evo_locator()
                chip = evo.locator(f'[data-role="chip"][data-value="{chip_value}"]').first
                chip.click(timeout=3000, force=True)
                logger.info(f"チップ${chip_value}選択OK")
                return True
            except Exception as e:
                if retry == 0:
                    # 初回失敗時にDOM確認
                    inner = self._get_evo_inner()
                    if inner:
                        try:
                            cnt = inner.evaluate(
                                f'() => document.querySelectorAll(\'[data-role="chip"][data-value="{chip_value}"]\').length'
                            )
                            logger.info(f"チップDOM: value={chip_value} count={cnt}")
                        except Exception:
                            pass
                # スタック展開してリトライ
                try:
                    evo = self._get_evo_locator()
                    evo.locator('[data-role="footer-perspective-chip-stack"]').first.click(timeout=2000, force=True)
                    time.sleep(0.3)
                    evo.locator(f'[data-role="chip"][data-value="{chip_value}"]').first.click(timeout=2000, force=True)
                    logger.info(f"チップ${chip_value}選択OK (展開後)")
                    return True
                except Exception:
                    time.sleep(0.3)

        logger.error(f"チップ${chip_value}選択失敗 — BET中止")
        return False

    def _select_chip_value(self, amount: float) -> int:
        chips = [1, 2, 5, 25, 100, 500]
        selected = chips[0]
        for c in chips:
            if c <= amount:
                selected = c
            else:
                break
        return selected

    def _get_total_bet(self) -> float:
        inner = self._get_evo_inner()
        if not inner:
            return 0.0
        try:
            text = inner.evaluate(
                '() => { const e = document.querySelector(\'[data-role="total-bet-label-value"]\'); '
                "return e ? e.textContent : ''; }"
            )
            nums = re.findall(r'[\d.]+', text)
            return float(nums[0]) if nums else 0.0
        except Exception:
            return 0.0

    # ─── 結果待ち ───

    def wait_for_result(self, timeout: float = 60) -> dict | None:
        """ゲーム内WSで結果確定を待つ。

        Returns: {"result": "player"/"banker"/"tie", "balance": float} or None
        """
        if self.demo_mode:
            return None

        logger.info("結果を待っています...")
        deadline = time.time() + timeout
        result_side = None

        # BETフェーズ終了を待つ
        while time.time() < deadline:
            if not self._is_betting_phase_dom():
                break
            time.sleep(1.0)

        # ディーリング中 → 結果表示をDOMポーリング (0.5秒間隔)
        while time.time() < deadline:
            dom_result = self._detect_result_dom()
            if dom_result:
                result_side = dom_result
                logger.info(f"結果検出: {dom_result.upper()}")
                break
            time.sleep(0.5)

        if not result_side:
            logger.warning("結果取得タイムアウト")
            return None

        # 残高取得 (DOM)
        balance = self._get_balance_dom()
        logger.info(f"結果: {result_side.upper()} 残高: ${balance:.2f}")
        return {"result": result_side, "balance": balance}

    def _detect_result_dom(self) -> str | None:
        """DOM: 結果オーバーレイ検出 ([class*="gameResult"]要素)"""
        inner = self._get_evo_inner()
        if not inner:
            return None
        try:
            return inner.evaluate("""() => {
                // gameResult要素 (結果表示時のみvisible)
                const els = document.querySelectorAll('[class*="gameResult"]');
                for (const e of els) {
                    if (e.offsetParent !== null) {
                        const t = e.innerText.replace(/\\u00a0/g, ' ').toUpperCase().trim();
                        if (t.includes('PLAYER')) return 'player';
                        if (t.includes('BANKER')) return 'banker';
                        if (t.includes('TIE')) return 'tie';
                    }
                }
                return null;
            }""")
        except Exception:
            return None

    # ─── 残高 ───

    def get_balance(self) -> float:
        return self._get_balance_dom()

    def _get_balance_dom(self) -> float:
        inner = self._get_evo_inner()
        if not inner:
            return 0.0
        try:
            text = inner.evaluate(
                '() => { const e = document.querySelector(\'[data-role="balance-label-value"]\'); '
                "return e ? e.textContent : ''; }"
            )
            import re as _re
            nums = _re.findall(r'[\d.]+', text)
            return float(nums[0]) if nums else 0.0
        except Exception:
            return 0.0

    # ─── テーブル退出 ───

    def exit_table(self) -> bool:
        if self.demo_mode:
            logger.info("ロビーに戻ります")
            self._reset_state()
            return True

        try:
            logger.info("ロビーに戻ります")
            evo = self._get_evo_locator()
            try:
                evo.locator('[data-role="lobby-button"]').first.click(timeout=5000)
            except Exception:
                game = self._get_evo_game()
                if game:
                    game.evaluate("() => { window.location.hash = 'category=baccarat_sicbo'; }")
            time.sleep(5)
            self.game_ws.reset()
            self._reset_state()
            logger.info("ロビー復帰完了")
            return True
        except Exception as e:
            logger.error(f"テーブル退出エラー: {e}")
            self._reset_state()
            return False

    def _reset_state(self):
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
