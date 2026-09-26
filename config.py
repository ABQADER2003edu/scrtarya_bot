import os
import json
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("SECRTARYA_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", 0))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# Gemini Models
GEMINI_MODEL_TEXT = os.getenv("MODEL", "gemini-1.5-flash")
model_v_str = os.getenv("MODEL_V", "gemini-1.5-flash")
GEMINI_MODEL_VOICE_LIST = [m.strip() for m in model_v_str.split(",") if m.strip()]

# OAuth 2.0 Configuration
# OAuth 2.0 Configuration
# Load JSON content directly from env vars
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_TOKEN_JSON = os.getenv("GOOGLE_TOKEN_JSON")

from pathlib import Path
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", str(Path(__file__).resolve().parent / "credentials.json"))
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", str(Path(__file__).resolve().parent / "token.json"))

MORNING_MESSAGE_HOUR = int(os.getenv("MORNING_MESSAGE_HOUR", 7))
MORNING_MESSAGE_MINUTE = int(os.getenv("MORNING_MESSAGE_MINUTE", 0))

# Sohag Coordinates
SOHAG_LATITUDE = 26.5591
SOHAG_LONGITUDE = 31.6968
TIMEZONE = "Africa/Cairo"
