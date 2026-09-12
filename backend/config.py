import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

STEEL_API_KEY = os.getenv("STEEL_API_KEY", "")
SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
STEEL_TEST_URL = os.getenv("STEEL_TEST_URL", "https://example.com")
SKIP_BROWSER_USE = os.getenv("SKIP_BROWSER_USE", "0") == "1"
STEEL_API_BASE = os.getenv("STEEL_API_BASE", "https://api.steel.dev")
