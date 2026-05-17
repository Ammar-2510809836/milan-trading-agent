import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not NVIDIA_API_KEY and not GOOGLE_API_KEY:
    raise EnvironmentError("Set NVIDIA_API_KEY or GOOGLE_API_KEY in .env")

from tradingagents.default_config import DEFAULT_CONFIG

if NVIDIA_API_KEY:
    # NVIDIA NIM — OpenAI-compatible endpoint
    os.environ["OPENAI_API_KEY"]  = NVIDIA_API_KEY
    os.environ["OPENAI_BASE_URL"] = "https://integrate.api.nvidia.com/v1"

    TRADING_AGENTS_CONFIG = DEFAULT_CONFIG.copy()
    TRADING_AGENTS_CONFIG.update({
        "llm_provider":    "openai",
        "deep_think_llm":  "nvidia/llama-3.1-nemotron-70b-instruct",
        "quick_think_llm": "meta/llama-3.3-70b-instruct",
        "max_debate_rounds": 1,
        "online_tools": True,
    })
    print("[CONFIG] Using NVIDIA NIM as primary LLM")

else:
    # Fallback to Gemini
    TRADING_AGENTS_CONFIG = DEFAULT_CONFIG.copy()
    TRADING_AGENTS_CONFIG.update({
        "llm_provider":    "google",
        "deep_think_llm":  "gemini-2.5-pro",
        "quick_think_llm": "gemini-2.5-flash",
        "max_debate_rounds": 1,
        "online_tools": True,
    })
    print("[CONFIG] Using Google Gemini as LLM (NVIDIA_API_KEY not set)")
