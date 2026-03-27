"""バカラモニター設定"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# --- Stake.com ---
STAKE_USERNAME = os.getenv("STAKE_USERNAME", "")
STAKE_PASSWORD = os.getenv("STAKE_PASSWORD", "")
STAKE_URL = "https://stake.com"
BACCARAT_LOBBY_URL = f"{STAKE_URL}/casino/games/evolution-baccarat-lobby"

# --- Telegram (optional) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Paths ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
AUTH_STATE_DIR = BASE_DIR / "auth_state"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
DB_PATH = DATA_DIR / "baccarat.db"

DATA_DIR.mkdir(exist_ok=True)
AUTH_STATE_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR.mkdir(exist_ok=True)

# --- Monitor ---
# Evolutionのバカラは1ラウンド約30-60秒
# DOMポーリング間隔（秒）
POLL_INTERVAL = 5
# セッション再接続の最大リトライ
MAX_RETRIES = 10
RETRY_DELAY = 30

# レポート間隔（秒）
REPORT_INTERVAL = 3600  # 1時間ごと

# ターゲットテーブル名（空ならSpeed Baccaratを自動選択）
TARGET_TABLE = os.getenv("TARGET_TABLE", "")
