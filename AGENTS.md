# AGENTS.md — Milan AI Week Hackathon: TradingAgents + Kraken CLI + Gemini

## 🧠 Project Overview

You are building a **production-ready autonomous trading agent** for the Milan AI Week Hackathon (lablab.ai). The project bridges two systems:

1. **TradingAgents** (`TauricResearch/TradingAgents`) — an open-source multi-agent LLM framework that reasons about markets using specialized analyst agents
2. **Kraken CLI** (`krakenfx/kraken-cli`) — the official AI-native CLI for executing real trades on Kraken exchange (xStocks = tokenized U.S. stocks/ETFs)

The LLM backbone is **Google Gemini** (via Google Cloud — €250 credits available). The deployment target is **Google Cloud VM** (using the same €250 Google Cloud credits).

Ranked **purely by net PnL** (profit/loss) at end of competition. The agent must trade autonomously with zero manual intervention.

---

## 🗂️ Repository Structure (After Setup)

```
project-root/
├── AGENTS.md                  ← This file
├── TradingAgents/             ← Cloned from TauricResearch/TradingAgents
│   ├── tradingagents/
│   │   ├── graph/
│   │   │   └── trading_graph.py      ← Main graph, find propagate()
│   │   ├── agents/                   ← All analyst/trader agents
│   │   └── default_config.py         ← LLM config lives here
│   ├── main.py
│   └── requirements.txt
├── kraken-cli/                ← Cloned from krakenfx/kraken-cli
├── bridge/                    ← YOUR CODE (the execution bridge)
│   ├── kraken_executor.py     ← Replaces simulated exchange with real Kraken CLI calls
│   ├── gemini_config.py       ← Gemini API setup
│   ├── scheduler.py           ← Runs agent autonomously on schedule
│   └── main.py                ← Entry point
├── deploy/
│   └── gcloud_setup.sh        ← Google Cloud VM deployment script
├── .env                       ← API keys (never commit)
└── requirements.txt           ← Top-level deps
```

---

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Multi-agent reasoning | TradingAgents (LangGraph + Python) |
| LLM provider | Google Gemini (via `google-generativeai` or Gemini API) |
| Trade execution | Kraken CLI (`krakenfx/kraken-cli`) |
| Assets traded | xStocks (tokenized U.S. stocks/ETFs on Kraken) |
| Deployment | Google Cloud VM (e2-small, Ubuntu 22.04) |
| Scheduling | Python `schedule` or `APScheduler` |
| Language | Python 3.13 |

---

## 🔑 Environment Variables

Create a `.env` file at project root. NEVER commit this file.

```env
# Google Gemini
GOOGLE_API_KEY=your_google_cloud_gemini_api_key

# Kraken Exchange
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_API_SECRET=your_kraken_api_secret

# Alpha Vantage (market data for TradingAgents)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

---

## 🔧 Step 1: Clone and Configure TradingAgents

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
conda create -n tradingagents python=3.13
conda activate tradingagents
pip install .
```

### Configure Gemini as LLM Provider

In `TradingAgents/tradingagents/default_config.py`, set:

```python
DEFAULT_CONFIG = {
    "llm_provider": "google",
    "deep_think_llm": "gemini-2.5-pro",     # For complex reasoning
    "quick_think_llm": "gemini-2.5-flash",   # For fast tasks
    "max_debate_rounds": 2,
    "online_tools": True,
}
```

---

## 🔧 Step 2: Clone Kraken CLI

```bash
git clone https://github.com/krakenfx/kraken-cli.git
cd kraken-cli
# Follow its README for installation
# Set KRAKEN_API_KEY and KRAKEN_API_SECRET in .env
```

The Kraken CLI is a **Rust binary** — zero dependencies. Install via curl, not npm or pip.

```bash
# Install
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh

# Verify
kraken --version

# All commands return JSON with -o json flag (ALWAYS use this in code)
kraken ticker AAPL -o json

# Paper trading (safe, no real money, uses live prices)
kraken paper buy AAPL 1 -o json

# Live trading (real money — use only when strategy is validated)
kraken order buy AAPL 1 -o json

# Check balance
kraken paper balance -o json

# Check open orders
kraken paper openorders -o json
```

**IMPORTANT — verify xStocks ticker symbols before trading:**
```bash
# Run this after install to confirm exact symbol format on Kraken
kraken ticker AAPL -o json
kraken ticker AAPLx -o json
# Use whichever returns valid data
```

---

## 🔧 Step 3: Build the Bridge (`bridge/kraken_executor.py`)

This is the **core of your hackathon contribution**. TradingAgents currently sends decisions to a simulated exchange. You must intercept the final decision and route it to Kraken CLI.

### Where to Hook In

In `TradingAgents/tradingagents/graph/trading_graph.py`, find the `propagate()` method. It returns a `decision` dict that looks like:

```python
decision = {
    "action": "buy" | "sell" | "hold",
    "ticker": "NVDA",
    "quantity": 2,
    "reasoning": "..."
}
```

### `bridge/kraken_executor.py`

```python
import subprocess
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ⚠️ VERIFY THESE SYMBOLS before trading by running:
# kraken ticker AAPL -o json
# kraken ticker AAPLx -o json
# Use whichever format returns valid data from Kraken
XSTOCK_PAIRS = {
    "AAPL": "AAPL",    # verify: may be AAPLx or XAAPL
    "NVDA": "NVDA",    # verify before live trading
    "TSLA": "TSLA",    # verify before live trading
    "MSFT": "MSFT",    # verify before live trading
    "GOOGL": "GOOGL",  # verify before live trading
    "SPY": "SPY",      # verify before live trading
    "QQQ": "QQQ",      # verify before live trading
}

# Set to False only when ready to trade with real money
PAPER_MODE = True

def execute_trade(decision: dict) -> dict:
    """
    Takes a TradingAgents decision and executes it via Kraken CLI.

    decision = {
        "action": "buy" | "sell" | "hold",
        "ticker": "NVDA",
        "quantity": 1,
        "reasoning": "..."
    }
    """
    action = decision.get("action", "hold").lower()
    ticker = decision.get("ticker", "")
    quantity = decision.get("quantity", 1)

    if action == "hold":
        print(f"[EXECUTOR] HOLD decision for {ticker}. No trade executed.")
        return {"status": "hold", "ticker": ticker}

    pair = XSTOCK_PAIRS.get(ticker)
    if not pair:
        print(f"[EXECUTOR] WARNING: {ticker} not in xStocks map. Skipping.")
        return {"status": "skipped", "ticker": ticker, "reason": "not in xStocks map"}

    # Kraken CLI syntax: kraken <paper|order> <buy|sell> <pair> <volume> -o json
    engine = "paper" if PAPER_MODE else "order"
    cmd = [
        "kraken", engine, action,
        pair,
        str(quantity),
        "-o", "json"    # Always use JSON output for machine parsing
    ]

    print(f"[EXECUTOR] Executing ({'PAPER' if PAPER_MODE else 'LIVE'}): {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ}
        )
        # NEVER parse stderr — Kraken CLI uses stderr only for diagnostics
        if result.returncode == 0:
            response = json.loads(result.stdout)
            print(f"[EXECUTOR] SUCCESS: {response}")
            return {"status": "executed", "action": action, "ticker": ticker, "response": response}
        else:
            # stderr has diagnostics, stdout has JSON error envelope
            try:
                error_json = json.loads(result.stdout)
            except Exception:
                error_json = result.stdout
            print(f"[EXECUTOR] ERROR: {error_json}")
            return {"status": "error", "error": error_json}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "ticker": ticker}
    except Exception as e:
        return {"status": "exception", "error": str(e)}


def get_balance() -> dict:
    """Fetch current Kraken paper account balance as JSON."""
    engine = "paper" if PAPER_MODE else "account"
    result = subprocess.run(
        ["kraken", engine, "balance", "-o", "json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"raw": result.stdout}


def get_open_orders() -> dict:
    """Fetch open orders from Kraken as JSON."""
    engine = "paper" if PAPER_MODE else "order"
    result = subprocess.run(
        ["kraken", engine, "openorders", "-o", "json"],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"raw": result.stdout}
```

---

## 🔧 Step 4: Build the Scheduler (`bridge/scheduler.py`)

This runs the agent autonomously on a loop — no human intervention.

```python
import schedule
import time
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from bridge.kraken_executor import execute_trade, get_balance

# Tickers to trade (must be available as xStocks on Kraken)
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "SPY"]

def run_trading_cycle():
    print(f"\n{'='*50}")
    print(f"[AGENT] Trading cycle started at {datetime.now()}")
    print(f"{'='*50}")

    # Print current balance
    print("[AGENT] Current balance:")
    print(get_balance())

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "google"
    config["deep_think_llm"] = "gemini-2.5-pro"
    config["quick_think_llm"] = "gemini-2.5-flash"
    config["max_debate_rounds"] = 1   # Keep fast for hackathon

    ta = TradingAgentsGraph(debug=True, config=config)

    today = datetime.now().strftime("%Y-%m-%d")

    for ticker in WATCHLIST:
        try:
            print(f"\n[AGENT] Analyzing {ticker}...")
            state, decision = ta.propagate(ticker, today)

            print(f"[AGENT] Decision for {ticker}: {decision}")

            # Execute via Kraken CLI
            result = execute_trade({
                "action": decision.get("action", "hold"),
                "ticker": ticker,
                "quantity": decision.get("quantity", 1),
                "reasoning": decision.get("reasoning", "")
            })

            print(f"[EXECUTOR] Result: {result}")

        except Exception as e:
            print(f"[AGENT] ERROR analyzing {ticker}: {e}")
            continue

    print(f"\n[AGENT] Cycle complete at {datetime.now()}")


if __name__ == "__main__":
    print("[SCHEDULER] Autonomous trading agent starting...")

    # Run immediately on start
    run_trading_cycle()

    # Then run every 4 hours
    schedule.every(4).hours.do(run_trading_cycle)

    print("[SCHEDULER] Running on schedule. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)
```

---

## 🔧 Step 5: Entry Point (`bridge/main.py`)

```python
#!/usr/bin/env python3
"""
Milan AI Week Hackathon — Autonomous xStocks Trading Agent
Powered by: TradingAgents (Gemini) + Kraken CLI
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'TradingAgents'))

from bridge.scheduler import run_trading_cycle
import argparse

def main():
    parser = argparse.ArgumentParser(description="Autonomous xStocks Trading Agent")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--ticker", type=str, help="Analyze a single ticker")
    args = parser.parse_args()

    if args.once or args.ticker:
        run_trading_cycle()
    else:
        from bridge.scheduler import run_trading_cycle
        import schedule, time
        schedule.every(4).hours.do(run_trading_cycle)
        run_trading_cycle()
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    main()
```

---

## 🚀 Step 6: Deploy on Google Cloud VM (`deploy/gcloud_setup.sh`)

Your €250 Google Cloud credits cover both Gemini API usage AND a VM. Use an **e2-small** instance (~€12/month, well within budget).

### 6a: Create the VM (Google Cloud Console or CLI)

```bash
# Install Google Cloud CLI locally first: https://cloud.google.com/sdk/docs/install
gcloud auth login

# Create VM (e2-small is enough, costs ~€0.50/day)
gcloud compute instances create trading-agent-vm \
  --machine-type=e2-small \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --zone=europe-west1-b \
  --tags=trading-agent

# SSH into it
gcloud compute ssh trading-agent-vm --zone=europe-west1-b
```

### 6b: Setup Script (`deploy/gcloud_setup.sh`)

```bash
#!/bin/bash
# Run this INSIDE the Google Cloud VM after SSH-ing in

# Update system
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git python3.11 python3-pip python3-venv nodejs npm screen curl

# Install Miniconda
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
export PATH="$HOME/miniconda3/bin:$PATH"
conda init bash && source ~/.bashrc

# Clone repos
git clone https://github.com/TauricResearch/TradingAgents.git
git clone https://github.com/krakenfx/kraken-cli.git
git clone https://github.com/YOUR_USERNAME/YOUR_HACKATHON_REPO.git project

# Setup Python env
conda create -n tradingagents python=3.13 -y
conda activate tradingagents
cd TradingAgents && pip install . && cd ..
cd project && pip install -r requirements.txt && cd ..

# Install Kraken CLI — Rust binary, zero dependencies (NOT npm or pip)
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
# Verify install
kraken --version

# Create .env file
cd project
cp .env.example .env
nano .env  # ← fill in your API keys here

# Run agent in background via screen (persists after SSH disconnect)
screen -dmS trading_agent bash -c "conda activate tradingagents && python bridge/main.py"
echo "✅ Agent running in screen session 'trading_agent'"
echo "   Attach with: screen -r trading_agent"
echo "   Detach with: Ctrl+A then D"
```

### 6c: Keep it Running

```bash
# Check agent is alive
screen -ls

# Reattach to see logs
screen -r trading_agent

# Detach without killing
# Press: Ctrl+A, then D

# If VM restarts, SSH back in and re-run:
screen -dmS trading_agent bash -c "conda activate tradingagents && cd project && python bridge/main.py"
```

---

## 📋 Top-Level `requirements.txt`

```
python-dotenv
schedule
APScheduler
requests
pandas
```

---

## ⚠️ Critical Rules for Codex

1. **NEVER commit `.env`** — add it to `.gitignore` immediately
2. **TradingAgents is read-only** — do NOT modify files inside `TradingAgents/` directory. Only import from it. All your code lives in `bridge/`
3. **Kraken CLI is a Rust binary** — install via `curl` installer, NOT npm or pip. Call it via `subprocess.run(["kraken", ...])` with `-o json` always
4. **Always use `-o json`** — never parse the human-readable table output. Never parse stderr (diagnostics only)
5. **Paper mode first** — `PAPER_MODE = True` in `kraken_executor.py`. Paper uses live prices but no real money. Switch to `False` only when ready
6. **Verify xStocks ticker symbols** — run `kraken ticker AAPL -o json` after install to confirm exact format before setting `XSTOCK_PAIRS`
5. **Decision format** — TradingAgents `propagate()` returns `(state, decision)`. Always unpack both. The `decision` dict contains `action`, `ticker`, `quantity`
6. **Gemini config** — set `llm_provider: "google"` in `DEFAULT_CONFIG`. Models: `gemini-2.5-pro` for deep think, `gemini-2.5-flash` for quick think
7. **Market hours** — xStocks trade 24/7. The scheduler can run at any hour
8. **Error handling** — wrap every `ta.propagate()` call in try/except. One failed ticker should NOT crash the whole cycle
9. **Google Cloud deployment** — use `screen` or `tmux` to keep the agent running after SSH disconnect. The VM zone should be `europe-west1-b` (closest to Milan, lowest latency)
10. **Read-only Kraken API key for submission** — the hackathon requires a READ-ONLY key for audit. Your agent uses a FULL key to trade. These are two different keys

---

## 🏆 Hackathon Submission Checklist

- [ ] Agent runs autonomously with zero human input
- [ ] Trades are executing on Kraken via Kraken CLI
- [ ] xStocks pairs are being used (not crypto)
- [ ] Gemini is the LLM powering the reasoning
- [ ] Deployed on Google Cloud VM (agent running 24/7 autonomously)
- [ ] Read-only Kraken API key submitted to lablab.ai
- [ ] Demo video shows agent reasoning + trade execution live
- [ ] GitHub repo is public and documented

---

## 🎯 Demo Script (For May 20 Presentation)

1. Show the Google Cloud VM running (`screen -r trading_agent`)
2. Trigger one manual cycle live: `python bridge/main.py --once`
3. Show the agent analyzing a ticker (Gemini reasoning visible in logs)
4. Show the Kraken order being placed in real-time
5. Show Kraken account balance before/after
6. Show the PnL dashboard

---

## 📞 Key Links

- TradingAgents repo: https://github.com/TauricResearch/TradingAgents
- Kraken CLI repo: https://github.com/krakenfx/kraken-cli
- xStocks info: https://www.kraken.com/xstocks
- Hackathon page: https://lablab.ai/ai-hackathons/milan-ai-week-hackathon
- Gemini API docs: https://ai.google.dev/gemini-api/docs
- Google Cloud Console: https://console.cloud.google.com
- Google Cloud CLI install: https://cloud.google.com/sdk/docs/install
