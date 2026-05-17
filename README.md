# xStocks Trading Agent
### Milan AI Week Hackathon — Kraken Challenge

> Autonomous AI trading agent for tokenized U.S. stocks (xStocks) on Kraken.
> Powered by **Google Gemini 2.5 Pro/Flash** · **TradingAgents** multi-agent framework · **Kraken CLI** execution · Deployed on **Google Cloud VM**.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS TRADING LOOP (1h cycle)           │
│                                                                     │
│   Market Scanner          Multi-Agent Analysis        Execution     │
│   ─────────────          ──────────────────────      ─────────────  │
│   Kraken live prices  →  TradingAgents (Gemini)  →  Kraken CLI     │
│   Score 8 tickers        9 specialized agents        xStocks order  │
│   Pick top 3             BUY / SELL / HOLD            positions.json │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                            FastAPI Dashboard
                         (real-time pipeline UI)
```

---

## How It Works

### 1. Market Scanner (`bridge/market_scanner.py`)
Each cycle begins by scoring 8 xStock tickers (NVDA, TSLA, AAPL, META, MSFT, GOOGL, SPY, QQQ) using live Kraken price data:

| Factor | Weight | Signal |
|--------|--------|--------|
| Price momentum (vs open) | 50% | Strong directional move |
| Intraday volatility (high-low range) | 35% | Trading opportunity |
| Bid-ask spread tightness | 15% | Liquidity / executability |

Top 3 tickers are passed to the analysis pipeline.

---

### 2. Multi-Agent Pipeline (`TradingAgents` framework)

Each ticker is analyzed by **9 specialized AI agents** running in sequence:

```
DATA SOURCES          ANALYST TEAM             RESEARCHER TEAM
─────────────         ──────────────────────   ───────────────────────
Yahoo Finance    →    Market Analyst           Bull Researcher
X / Reddit            (RSI, MACD, Bollinger)   (buy evidence)
FinHub / Reuters      Social Analyst                    ⚡ Debate
Financials DB         (sentiment, buzz)        Bear Researcher
                      News Analyst             (sell evidence)
                      (headlines, events)
                      Fundamentals             Investment Plan
                      (P/E, EPS, revenue)      (judge decision)
                             │
                      TRADER AGENT
                      (transaction proposal)
                             │
              RISK MANAGEMENT TEAM           PORTFOLIO MANAGER
              ────────────────────────       ────────────────────
              Aggressive (max return)   →    Final Decision
              Neutral (balanced)             BUY / SELL / HOLD
              Conservative (capital safe)
```

**LLMs used:**
- `gemini-2.5-pro` — deep reasoning (debate, investment plan, risk decision)
- `gemini-2.5-flash` — fast tasks (data fetching, summaries)

---

### 3. Position Sizing (`bridge/portfolio_manager.py`)

| Conviction | Position Size | Leverage | Trigger |
|-----------|--------------|----------|---------|
| High | 4% of portfolio | 2x | "strong", "very bullish", "high confidence" |
| Medium | 3% of portfolio | 1x | Default buy/sell |
| Low | 2% of portfolio | 1x | Weak signal |

**Risk controls:**
- Stop-loss at **-5%** from entry price (enforced every cycle)
- Maximum **5 concurrent open positions**
- Leverage only on NVDA, TSLA, AAPL, MSFT, META (Kraken-supported)
- Minimum order size: 0.01 fractional shares

---

### 4. Trade Execution (`bridge/kraken_executor.py`)

Executes via **Kraken CLI** (Rust binary) using the xStocks format:

```bash
# xStocks require the AAPLx/USD format + tokenized_asset class
kraken order buy AAPLx/USD 0.1 --asset-class tokenized_asset --type market -o json
```

| Mode | Command | Use |
|------|---------|-----|
| Paper | `kraken paper buy ...` | Testing (no real money) |
| Live | `kraken order buy ...` | Real trading (set `PAPER_MODE=False`) |

---

### 5. Dashboard (`dashboard/`)

Real-time FastAPI + Chart.js dashboard showing:
- Live pipeline state with animated node progression
- USD balance + Total PnL (realized + unrealized)
- Open positions table with unrealized PnL per ticker
- Trade history and agent decision log
- Full agent reasoning text per stage

**Auto-refreshes every 5 seconds** via `/api/full`.

---

## Project Structure

```
project-root/
├── bridge/
│   ├── main.py              # Entry point (CLI args: --once, --ticker)
│   ├── scheduler.py         # 1-hour autonomous trading loop
│   ├── kraken_executor.py   # Kraken CLI subprocess wrapper
│   ├── portfolio_manager.py # Position sizing + stop-loss
│   ├── market_scanner.py    # Ticker scoring + top-N selection
│   ├── trade_logger.py      # JSONL event log (read by dashboard)
│   └── gemini_config.py     # Gemini API + TradingAgents config
├── dashboard/
│   ├── app.py               # FastAPI backend (REST + WebSocket)
│   └── index.html           # Single-page dashboard UI
├── deploy/
│   └── gcloud_setup.sh      # Google Cloud VM setup script
├── TradingAgents/           # Cloned: TauricResearch/TradingAgents
├── .env                     # API keys (never commit)
├── requirements.txt
└── positions.json           # Live position tracker (auto-created)
```

---

## Setup Guide

### Prerequisites

- Python 3.10+
- [Google Cloud account](https://console.cloud.google.com) with Gemini API enabled
- [Kraken account](https://www.kraken.com) with API keys
- Linux VM (Kraken CLI is Linux/Mac only)

---

### Step 1 — Clone and install

```bash
git clone https://github.com/Ammar-2510809836/milan-trading-agent.git
cd milan-trading-agent

# Clone TradingAgents framework
git clone https://github.com/TauricResearch/TradingAgents.git

# Install Python dependencies
pip3 install -r requirements.txt
pip3 install stockstats yfinance langchain-google-genai langgraph \
             langchain-community langchain openai anthropic \
             tavily-python langgraph-checkpoint-sqlite

# Install TradingAgents
pip3 install TradingAgents/
```

---

### Step 2 — Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_API_SECRET=your_kraken_private_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
```

> **Two Kraken keys needed:**
> - Full-permission key → for the agent to trade (goes in `.env`)
> - Read-only key → submit to lablab.ai for audit

---

### Step 3 — Install Kraken CLI (Linux)

```bash
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh

kraken --version   # verify install

# Initialize paper trading account
kraken paper init --balance 10000
```

---

### Step 4 — Run locally (paper mode)

**Run one cycle:**
```bash
cd project-root
PYTHONPATH=. python3 bridge/main.py --once
```

**Analyze a specific ticker:**
```bash
PYTHONPATH=. python3 bridge/main.py --ticker NVDA --once
```

**Run the autonomous scheduler (every 1 hour):**
```bash
PYTHONPATH=. python3 bridge/main.py
```

---

### Step 5 — Start the dashboard

```bash
touch dashboard/__init__.py
PYTHONPATH=. python3 -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```

Open **http://localhost:8080**

---

## Google Cloud VM Deployment

### Create the VM

```bash
gcloud compute instances create trading-agent-vm \
  --machine-type=e2-small \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --zone=europe-west1-b \
  --tags=trading-agent

# Open port 8080 for dashboard
gcloud compute firewall-rules create allow-dashboard \
  --allow=tcp:8080 \
  --target-tags=trading-agent \
  --description="Trading agent dashboard"
```

### Deploy

```bash
gcloud compute ssh trading-agent-vm --zone=europe-west1-b
```

Inside the VM:

```bash
git clone https://github.com/Ammar-2510809836/milan-trading-agent.git project
cd project
# Follow steps 1-3 above, then:

# Start dashboard (persists after SSH disconnect)
touch dashboard/__init__.py
PYTHONPATH=/home/$USER/project nohup python3 -m uvicorn dashboard.app:app \
  --host 0.0.0.0 --port 8080 > ~/dashboard.log 2>&1 & disown

# Start trading agent
PYTHONPATH=/home/$USER/project nohup python3 bridge/main.py \
  > ~/agent.log 2>&1 & disown
```

Dashboard live at: `http://YOUR_VM_IP:8080`

### Monitor

```bash
# Agent logs
tail -f ~/agent.log

# Dashboard logs
tail -f ~/dashboard.log

# Check processes
ps aux | grep python3
```

---

## Switching to Live Trading

1. Open `bridge/kraken_executor.py`
2. Set `PAPER_MODE = False`
3. Ensure real Kraken API keys are in `.env`
4. Restart the agent

> **Warning:** Live mode executes real trades with real money. Validate thoroughly in paper mode first.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard UI |
| `GET /api/status` | Agent running state + mode |
| `GET /api/balance` | Kraken account balance |
| `GET /api/positions` | Open positions + unrealized PnL |
| `GET /api/pnl` | Total PnL summary |
| `GET /api/trades` | Recent executed trades |
| `GET /api/decisions` | Recent agent decisions |
| `GET /api/pipeline` | Latest full agent pipeline state |
| `GET /api/full` | Everything in one shot (used by dashboard) |
| `WS /ws` | WebSocket live feed (5s updates) |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Multi-agent reasoning | TradingAgents (LangGraph + Python) |
| LLM provider | Google Gemini 2.5 Pro / Flash |
| Trade execution | Kraken CLI (Rust binary) |
| Assets traded | xStocks (tokenized U.S. stocks on Kraken) |
| Dashboard backend | FastAPI + uvicorn |
| Dashboard frontend | Tailwind CSS + Chart.js |
| Deployment | Google Cloud VM (e2-small, europe-west1-b) |
| Scheduling | Python `schedule` (1-hour cycles) |

---

## Hackathon Submission Checklist

- [x] Agent trades autonomously with zero human input
- [x] Executes on Kraken via Kraken CLI
- [x] xStocks pairs (AAPLx, NVDAx, TSLAx, etc.)
- [x] Gemini 2.5 Pro/Flash powers all reasoning
- [x] Deployed on Google Cloud VM (24/7)
- [ ] Read-only Kraken API key submitted to lablab.ai
- [ ] Demo video recorded

---

## Links

- [TradingAgents](https://github.com/TauricResearch/TradingAgents)
- [Kraken CLI](https://github.com/krakenfx/kraken-cli)
- [xStocks info](https://www.kraken.com/xstocks)
- [Milan AI Week Hackathon](https://lablab.ai/ai-hackathons/milan-ai-week-hackathon)
- [Gemini API docs](https://ai.google.dev/gemini-api/docs)
