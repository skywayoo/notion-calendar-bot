import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_CALENDAR_DB_ID = os.getenv("NOTION_CALENDAR_DB_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TIMEZONE = "Asia/Taipei"
