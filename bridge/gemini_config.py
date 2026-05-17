import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError("GOOGLE_API_KEY not set in .env")

from tradingagents.default_config import DEFAULT_CONFIG

TRADING_AGENTS_CONFIG = DEFAULT_CONFIG.copy()
TRADING_AGENTS_CONFIG.update({
    "llm_provider": "google",
    "deep_think_llm": "gemini-2.5-pro",
    "quick_think_llm": "gemini-2.5-flash",
    "max_debate_rounds": 1,
    "online_tools": True,
})

