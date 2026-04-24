# Laplace Copilot — ba GUI v2

ba ディレクトリの新規 Copilot 型 GUI。友人戦略 (2026-04-24 統合版) を可視化し、
user が Camoufox で手動 BET する際のアシスト表示に徹するツール。

**BET の自動執行はしません**。全 BET は user が Camoufox で手動で行います。

---

## 🚀 クイックスタート (初回)

```batch
cd E:\dev\Cusor\ba\gui_v2
setup.bat        ← 依存インストール (1 回だけ)
run.bat          ← 起動
```

ブラウザで `http://127.0.0.1:5050` を開く

---

## 📋 機能

### GUI パネル

1. **Lobby (左)**
   - 🔴 **Live タブ**: VPS DB から直近 4 時間のシューを読み、稼働中テーブルを分類・ランク付け
     - テーブル名クリックで入力欄に自動コピー
     - ⭐ = watchlist / 🟢 = エントリー条件 OK / pattern tag で状態が一目瞭然
   - ⭐ **Watchlist タブ**: OOS 検証結果ベースの静的リスト
     - 🟢 持続確定 5 / 🟡 持続期待 3 / 🔴 回収確定 9

2. **シュー (中央)**
   - P / B / T ボタンで手動入力 (キーボード `P`/`B`/`T` も可)
   - Undo ボタン / キーボード `U` or `Backspace`
   - 大路の canvas 描画、直近 hand の視覚履歴

3. **AI 判定 (右)**
   - Pattern 分類 (縦面5+密集 / 縦面4以下密集 / ニコニコ・ニコイチ / ブリッジ / 不規則 / 偏り / 不明)
   - エントリー条件判定 (3列目ルール / 5列目 2落連続ルール / 20目 3:7 ルール)
   - 次 BET 推奨 (🟢 BET / 🟡 LOOK / 🔴 EXIT) + 理由
   - BET 額 ($1 base の旧 SEQ 現 unit)
   - 特徴量パネル (5+連数、4+連数、≤2段率、1落連続、末尾1落、overshoot)

4. **KPI (下)**
   - 勝率 (52% で緑、48% 未満で赤)
   - PNL / ROI / stake
   - 旧 SEQ 現 unit / overshoot / 完了セット数

5. **グラフ (下)**
   - Equity curve (累計 PNL): 勝ち=緑ドット、負け=赤ドット
   - 勝率推移: 50% 基準線 + 52% 目標線

6. **判定ログ**
   - START / ENTER / EXIT / BET_RESULT / TABLE 切替などすべてタイムスタンプ付き
   - STOP 時に `logs/YYYY-MM-DDTHH-MM-SS.json` に自動保存 (将来の ML 学習データ)

### ロビー監視の 2 ソース

- **DB ソース (即動作)**: `analytics_vps_latest.sqlite3` の直近シューから現 pattern を計算
  - VPS collector が動いている限り自動更新
  - collector 停止中は古いデータしか取れない
- **Scraper ソース (任意)**: `lobby_scraper.py` (Playwright) を別プロセスで動かすと `lobby_state.json` を書き出し、GUI が優先的に読む

---

## 🔧 Playwright スクレイパの使い方 (任意)

ロビー をリアルタイムに読みたい場合:

```batch
python -m pip install playwright
python -m playwright install chromium
python lobby_scraper.py
```

1 回目は `lobby_scraper_config.json` が生成される。編集:

```json
{
  "casino_url": "https://YOUR-CASINO.com/play",
  "lobby_url_hint": "evolution",
  "scrape_interval_sec": 60,
  "user_data_dir": "./.browser_profile",
  "headless": false
}
```

再実行するとブラウザが起動、初回は手動ログイン → Evolution ロビー表示状態で放置。
60 秒ごとに `lobby_state.json` が更新される。

**DOM selector は casino ごとに異なるため、`lobby_scraper.py` 内の `scrape_once()` の selector を調整する必要があります**。

---

## ⌨️ キーボードショートカット

- `P` / `B` / `T`: hand 入力
- `U` or `Backspace`: undo

---

## 🗃️ ファイル

```
gui_v2/
├── app.py                      Flask backend + REST API
├── strategy_engine.py          pattern / エントリー / BET / エグジット判定
├── lobby_monitor.py            DB ソース + lobby_state.json 統合
├── lobby_scraper.py            Playwright スクレイパ (任意, 別プロセス)
├── templates/index.html        シングルページ
├── static/
│   ├── style.css
│   └── app.js
├── requirements.txt
├── setup.bat                   初回セットアップ
├── run.bat                     起動
└── logs/                       セッション JSON 自動保存
```

---

## 🎯 OOS 検証結果ベースの Watchlist (2026-04-24)

| 区分 | テーブル | OOS 勝率 | OOS ROI |
|---|---|---|---|
| 🟢 持続確定 | Japanese Speed Baccarat E | 56.9% | +13.85% |
| 🟢 持続確定 | Korean Speaking Speed Baccarat 2 | 51.3% | +2.63% |
| 🟢 持続確定 | Baccarat Squeeze | 53.2% | +6.49% |
| 🟢 持続確定 | Japanese Speed Baccarat A | 51.2% | +2.33% |
| 🟢 持続確定 | Korean Speed Baccarat H | 51.9% | +3.77% |
| 🟡 持続期待 | Speed Baccarat D | 50.8% | +1.59% |
| 🟡 持続期待 | Speed Baccarat T | 50.0% | 0.00% |
| 🟡 持続期待 | Lotus Speed Baccarat A | 50.7% | +1.49% |

---

## 📐 思想

- AI は**補佐のみ**。BET ボタンは Camoufox で user 手動
- 旧 SEQ の overshoot / unit 進行は user が暗算しなくて良いよう AI 側で自動
- 勝率 52% を維持できているかを常時確認 (赤/緑で色分け)
- 連敗や pattern 悪化時は即退室を促す
- 全判定の根拠をテキスト表示、「なぜ BET する/しないのか」が user に見える

---

## 🔜 今後の拡張候補

1. **BET 推奨の詳細化**: マーチン / ダランベールの切替を収支状況で自動判定
2. **通知**: エントリー/エグジット時にブラウザ通知 or 音
3. **対戦記録 CSV エクスポート**
4. **decision_log → ML 学習**: 蓄積ログから pattern 判定精度を再学習
5. **Scraper の DOM selector 自動キャリブレーション**
