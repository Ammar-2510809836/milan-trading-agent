import os
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not NVIDIA_API_KEY and not GOOGLE_API_KEY:
    raise EnvironmentError("Set NVIDIA_API_KEY or GOOGLE_API_KEY in .env")

from tradingagents.default_config import DEFAULT_CONFIG

if NVIDIA_API_KEY:
    # NVIDIA NIM — OpenAI-compatible endpoint (Chat Completions, not Responses API).
    # Use provider="deepseek" so TradingAgents routes through /v1/chat/completions
    # instead of OpenAI's /v1/responses which NVIDIA does not support.
    os.environ["OPENAI_API_KEY"] = NVIDIA_API_KEY

    TRADING_AGENTS_CONFIG = DEFAULT_CONFIG.copy()
    TRADING_AGENTS_CONFIG.update({
        "llm_provider":    "deepseek",
        "backend_url":     "https://integrate.api.nvidia.com/v1",
        "deep_think_llm":  "nvidia/nemotron-3-super-120b-a12b",   # backup: z-ai/glm-5.1
        "quick_think_llm": "qwen/qwen3.5-122b-a10b",              # backup: deepseek-ai/deepseek-v4-flash
        "max_debate_rounds": 1,
        "online_tools": True,
    })
    print("[CONFIG] Using NVIDIA NIM (deepseek provider → chat/completions)")
    print("[CONFIG]   deep_think  → nvidia/nemotron-3-super-120b-a12b")
    print("[CONFIG]   quick_think → qwen/qwen3.5-122b-a10b")

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
