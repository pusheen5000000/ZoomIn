import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

STEEL_API_KEY = os.getenv("STEEL_API_KEY", "")
SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
STEEL_TEST_URL = os.getenv("STEEL_TEST_URL", "https://example.com")
SKIP_BROWSER_USE = os.getenv("SKIP_BROWSER_USE", "0") == "1"
STEEL_API_BASE = os.getenv("STEEL_API_BASE", "https://api.steel.dev")
DEMO_USER = os.getenv("DEMO_USER", "judge@demo.local")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "SeniorSafety2026")
SESSION_SECRET = os.getenv("SESSION_SECRET", "hackathon-dev-session-secret")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))
