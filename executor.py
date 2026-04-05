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
    def __init__(self, page, game_ws, config: dict, humanizer=None):
        self.page = page
        self.game_ws = game_ws  # GameWSMonitor
        self.humanizer = humanizer
        self.in_table = False
        self.current_table_id = ""
        self.current_table_name = ""
        self.demo_mode = config.get("demo_mode", True)
        self._settled_seen = False
        self._pre_bet_balance = 0.0
        try:
            self.page.set_default_timeout(10000)
        except Exception:
            pass

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
        if not frames:
            return None
        # frame_locatorで確認できない場合のフォールバック
        # evaluateはハングする可能性があるので最小限にする
        if len(frames) >= 2:
            return frames[-1]
        return frames[0]

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
                try:
                    evo = self._get_evo_locator()
                    if evo.locator('[data-betspot-destination]').first.is_visible(timeout=2000):
                        logger.info(f"テーブル読込完了 ({(i+1)*2}秒)")
                        break
                except Exception:
                    pass
                # TRY AGAIN ダイアログチェック
                if not self.check_and_dismiss_error():
                    logger.warning("テーブル読込中にエラーダイアログ → 入場失敗")
                    return False
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

    def wait_for_betting_phase(self, timeout: float = 120, skip_round: bool = True) -> bool:
        """BETフェーズを待機 (WS + DOMハイブリッド)

        skip_round=True: 1ラウンド見送り後にBETフェーズを待つ
        skip_round=False: 即座にBETフェーズを待つ (連続BET時)
        """
        if self.demo_mode:
            return True
        return self.game_ws.wait_for_betting_phase(
            timeout, dom_checker=self._is_betting_phase_dom, skip_round=skip_round
        )

    def _is_betting_phase_dom(self) -> bool:
        """DOMでBETタイマー(円形カウントダウン)の表示を確認"""
        try:
            evo = self._get_evo_locator()
            return evo.locator('[class*="timerCircleContainer"]').first.is_visible(timeout=2000)
        except Exception:
            return False

    # ─── エラーダイアログ検出・回復 ───

    _error_dialog_count = 0

    def check_and_dismiss_error(self) -> bool:
        """TRY AGAIN / BACK TO LOBBY ダイアログを検出して回復。
        Returns: True=回復済み or エラーなし, False=回復不能
        """
        try:
            evo = self._get_evo_locator()
            try_again = evo.get_by_text("TRY AGAIN", exact=False).first
            if try_again.is_visible(timeout=500):
                self._error_dialog_count += 1
                if self._error_dialog_count <= 2:
                    logger.warning(f"エラーダイアログ検出 → TRY AGAIN ({self._error_dialog_count}/2)")
                    try_again.click(timeout=3000, force=True)
                    time.sleep(5)
                    return True
                else:
                    # TRY AGAINが3回失敗 → BACK TO LOBBY
                    logger.warning("TRY AGAIN 3回失敗 → BACK TO LOBBY")
                    try:
                        back = evo.get_by_text("BACK", exact=False).first
                        back.click(timeout=3000, force=True)
                        time.sleep(3)
                    except Exception:
                        pass
                    self._error_dialog_count = 0
                    return False
        except Exception:
            pass
        # エラーダイアログなし → カウントリセット
        self._error_dialog_count = 0
        return True

    # ─── ビーズロード読み取り ───

    def read_bead_road(self) -> str:
        """テーブル内DOMからビーズロードのP/B/T文字列を取得。
        例: "BPBTPPPTBTBBTBBBBPPBT"
        """
        # 方法1: data-role="Bead-road"
        try:
            evo = self._get_evo_locator()
            text = evo.locator('[data-role="Bead-road"]').first.text_content(timeout=3000)
            if text and text.strip():
                road = text.strip()
                return road
        except Exception:
            pass
        # 方法2: beadRoadクラス
        try:
            evo = self._get_evo_locator()
            text = evo.locator('[class*="beadRoad"]').first.text_content(timeout=3000)
            if text and text.strip():
                road = text.strip()
                return road
        except Exception:
            pass
        # 方法3: roads DIV
        try:
            evo = self._get_evo_locator()
            text = evo.locator('[class*="roads--"]').first.text_content(timeout=3000)
            if text and text.strip():
                road = ''.join(ch for ch in text.strip() if ch in 'PBT')
                if road:
                    return road
        except Exception:
            pass
        logger.warning("ビーズロード取得失敗 — 全方法が失敗")
        return ""

    def get_last_streaks_from_bead(self) -> list[dict]:
        """ビーズロードからP/B連続(streaks)を計算。TIEは無視。"""
        road = self.read_bead_road()
        if not road:
            return []
        streaks = []
        current_type = ""
        current_count = 0
        for ch in road:
            if ch == "T":
                continue
            side = "player" if ch == "P" else "banker" if ch == "B" else None
            if not side:
                continue
            if side == current_type:
                current_count += 1
            else:
                if current_type:
                    streaks.append({"type": current_type, "len": current_count})
                current_type = side
                current_count = 1
        if current_type:
            streaks.append({"type": current_type, "len": current_count})
        return streaks

    # ─── BET実行 ───

    def place_bet(self, side: str, amount: float) -> bool:
        """チップ選択 → BETスポットクリック → WS受理確認

        複数チップ額を組み合わせてクリック数を最小化。
        例: $13 → $5×2 + $2 + $1 = 4クリック (従来は13クリック)

        Returns: True=BET受理, False=失敗
        """
        if self.demo_mode:
            logger.info(f"[DEMO] ${amount:.0f} {side.upper()} BET")
            return True

        logger.info(f"${amount:.0f} {side.upper()} BETします")

        self._pre_bet_balance = self._get_balance_dom()

        dest = "Player" if side == "player" else "Banker"

        chip_plan = self._calc_chip_plan(int(amount))
        total_clicks = sum(count for _, count in chip_plan)
        logger.info(f"チップ計画: {chip_plan} ({total_clicks}クリック)")

        for chip_value, count in chip_plan:
            evo = self._get_evo_locator()
            if not self._select_chip(evo, chip_value):
                return False

            for click_i in range(count):
                evo = self._get_evo_locator()
                bet_loc = evo.locator(f'[data-betspot-destination="{dest}"]').first
                clicked = False
                for attempt in range(5):
                    try:
                        if self.humanizer and click_i == 0:
                            box = bet_loc.bounding_box(timeout=2000)
                            if box:
                                cx = int(box["x"] + box["width"] / 2)
                                cy = int(box["y"] + box["height"] / 2)
                                self.humanizer.click_with_offset_sync(self.page, cx, cy)
                                clicked = True
                                break
                        bet_loc.click(timeout=2000, force=True)
                        clicked = True
                        break
                    except Exception:
                        time.sleep(0.3)
                if not clicked:
                    logger.error(f"BETスポットクリック失敗 (chip=${chip_value} {click_i+1}/{count})")
                    return False
                time.sleep(0.25)

        for _ in range(10):
            total = self._get_total_bet()
            if total > 0:
                logger.info(f"BET受理: ${total:.2f}")
                return True
            time.sleep(0.5)

        logger.error("BET受理確認タイムアウト")
        return False

    @staticmethod
    def _calc_chip_plan(amount: int) -> list[tuple[int, int]]:
        """金額を最少クリック数のチップ組み合わせに分解。
        利用可能チップ: $100, $25, $5, $2, $1
        例: 250 → [(100,2),(25,2)] = 4クリック
            13 → [(5,2),(2,1),(1,1)] = 4クリック
        """
        plan = []
        remaining = amount
        for chip in [100, 25, 5, 2, 1]:
            if remaining >= chip:
                n = remaining // chip
                plan.append((chip, n))
                remaining -= chip * n
        return plan

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

    def wait_for_result(self, timeout: float = 60, bet_amount: float = 0) -> dict | None:
        """DOMのみで結果を検出 (WS不要)。

        タイマー消失(ディーリング中) → タイマー再出現(次BETフェーズ) → 残高変化で判定。
        bet_amount: BET額 (BET前の残高からの差分で勝敗判定に使用)
        """
        if self.demo_mode:
            import random
            time.sleep(random.uniform(2, 5))
            # Real baccarat probabilities: Player 44.62%, Banker 45.86%, Tie 9.52%
            r = random.choices(
                ["player", "banker", "tie"],
                weights=[44.62, 45.86, 9.52],
                k=1,
            )[0]
            logger.info(f"[DEMO] Result: {r}")
            return {"result": r, "balance": 0.0}

        logger.info("結果を待っています...")
        deadline = time.time() + timeout
        result_side = None
        pre_balance = self._pre_bet_balance

        # Step 1: BETフェーズ終了を待つ (タイマー消失)
        while time.time() < deadline:
            if not self._is_betting_phase_dom():
                logger.info("ディーリング中...")
                break
            if not self.check_and_dismiss_error():
                return None
            time.sleep(0.5)

        # Step 2: 次のBETフェーズ開始を待つ (タイマー再出現 = 結果確定済み)
        while time.time() < deadline:
            if self._is_betting_phase_dom():
                break
            if not self.check_and_dismiss_error():
                return None
            time.sleep(0.5)

        # Step 3: 結果判定
        time.sleep(0.3)
        new_balance = self._get_balance_dom()

        if bet_amount > 0 and pre_balance > 0 and new_balance > 0:
            # BETした場合: 残高変化で勝敗判定
            diff = new_balance - pre_balance
            logger.info(f"残高変化: ${pre_balance:.2f} → ${new_balance:.2f} (差${diff:+.2f}, BET${bet_amount:.0f})")
            if diff > 0.01:
                result_side = "player"
            elif diff < -0.01:
                result_side = "banker"
            else:
                result_side = "tie"

        # BETなし or 残高判定失敗 → DOM結果オーバーレイ
        if not result_side:
            dom_result = self._detect_result_dom()
            if dom_result:
                result_side = dom_result

        # それでも取れない場合 (観戦時は "unknown" で返す)
        if not result_side:
            if bet_amount == 0:
                return {"result": "unknown", "balance": new_balance}
            logger.warning("結果取得タイムアウト")
            return None

        logger.info(f"結果検出: {result_side.upper()} 残高: ${new_balance:.2f}")
        return {"result": result_side, "balance": new_balance}

    def _detect_result_dom(self) -> str | None:
        """DOM: 結果オーバーレイ検出"""
        try:
            evo = self._get_evo_locator()
            for selector in ['[class*="gameResult"]', '[class*="winResult"]', '[class*="resultText"]']:
                loc = evo.locator(selector).first
                if loc.is_visible(timeout=500):
                    text = loc.inner_text(timeout=500).upper().strip()
                    if 'PLAYER' in text:
                        return 'player'
                    if 'BANKER' in text:
                        return 'banker'
                    if 'TIE' in text:
                        return 'tie'
        except Exception:
            pass
        return None

    # ─── 残高 ───

    def get_balance(self) -> float:
        return self._get_balance_dom()

    def _get_balance_dom(self) -> float:
        try:
            evo = self._get_evo_locator()
            text = evo.locator('[data-role="balance-label-value"]').first.inner_text(timeout=3000)
            nums = re.findall(r'[\d.]+', text)
            if nums:
                return float(nums[0])
        except Exception:
            pass
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
