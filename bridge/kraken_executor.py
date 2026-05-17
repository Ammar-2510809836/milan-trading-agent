"""
Kraken CLI execution bridge for xStocks trading.

xStocks require:
  - Ticker format: AAPLx (not AAPL)
  - Pair format:   AAPLx/USD
  - Flag:          --asset-class tokenized_asset
"""

import subprocess
import os
import json
from dotenv import load_dotenv

load_dotenv()

# xStocks available on Kraken — 79 total; these are the highest-volatility targets
# Format: standard_symbol -> kraken_xstock_symbol
XSTOCK_PAIRS = {
    "AAPL":  "AAPLx",
    "NVDA":  "NVDAx",
    "TSLA":  "TSLAx",
    "MSFT":  "MSFTx",
    "META":  "METAx",
    "GOOGL": "GOOGLx",
    "AMZN":  "AMZNx",
    "SPY":   "SPYx",
    "QQQ":   "QQQx",
}

# Switch to False only when strategy is validated on paper
PAPER_MODE = True


def _run(cmd: list[str]) -> dict:
    """Run a kraken CLI command and return parsed JSON."""
    env = {**os.environ}
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode == 0:
            return {"ok": True, "data": json.loads(result.stdout)}
        # stdout carries the JSON error envelope even on failure
        try:
            err = json.loads(result.stdout)
        except Exception:
            err = result.stdout.strip()
        return {"ok": False, "error": err}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_trade(decision: dict) -> dict:
    """
    Execute a TradingAgents decision via Kraken CLI.

    decision = {
        "action":    "buy" | "sell" | "hold",
        "ticker":    "NVDA",
        "quantity":  0.5,       # fractional shares supported
        "reasoning": "...",
        "leverage":  1,         # optional, 1-3x on supported assets
    }
    """
    action = decision.get("action", "hold").lower()
    ticker = decision.get("ticker", "")
    quantity = decision.get("quantity", 0.1)
    leverage = int(decision.get("leverage", 1))

    if action == "hold":
        print(f"[EXECUTOR] HOLD {ticker} — no trade.")
        return {"status": "hold", "ticker": ticker}

    xstock = XSTOCK_PAIRS.get(ticker)
    if not xstock:
        print(f"[EXECUTOR] WARNING: {ticker} not in xStocks map — skipping.")
        return {"status": "skipped", "ticker": ticker, "reason": "not in xStocks map"}

    pair = f"{xstock}/USD"

    if PAPER_MODE:
        # kraken-cli v0.3.x: `paper buy/sell` currently supports only <PAIR> <VOLUME>
        # (no --asset-class / --type flags). Keep it minimal for compatibility.
        cmd = [
            "kraken", "paper", action,
            pair, str(quantity),
            "-o", "json",
        ]
    else:
        cmd = [
            "kraken", "order", action,
            pair, str(quantity),
            "-o", "json",
        ]
        if leverage > 1:
            cmd += ["--leverage", str(leverage)]

    mode_label = "PAPER" if PAPER_MODE else "LIVE"
    print(f"[EXECUTOR] {mode_label}: {' '.join(cmd)}")

    result = _run(cmd)
    if result["ok"]:
        print(f"[EXECUTOR] SUCCESS: {result['data']}")
        return {"status": "executed", "action": action, "ticker": ticker, "response": result["data"]}
    else:
        print(f"[EXECUTOR] ERROR: {result['error']}")
        return {"status": "error", "ticker": ticker, "error": result["error"]}


def get_ticker_price(ticker: str) -> float | None:
    """Return current ask price for a ticker, or None on failure."""
    xstock = XSTOCK_PAIRS.get(ticker)
    if not xstock:
        return None
    result = _run([
        "kraken", "ticker", f"{xstock}/USD",
        "--asset-class", "tokenized_asset",
        "-o", "json",
    ])
    if result["ok"]:
        try:
            data = result["data"]
            # Kraken ticker JSON: {"ask": [...], "bid": [...], ...}
            return float(data.get("ask", [0])[0])
        except Exception:
            return None
    return None


def get_balance() -> dict:
    """Fetch current account balance as JSON."""
    if PAPER_MODE:
        result = _run(["kraken", "paper", "status", "-o", "json"])
    else:
        result = _run(["kraken", "balance", "-o", "json"])
    return result.get("data", result)


def get_open_orders() -> dict:
    """Fetch open orders as JSON."""
    if PAPER_MODE:
        result = _run(["kraken", "paper", "openorders", "-o", "json"])
    else:
        result = _run(["kraken", "order", "openorders", "-o", "json"])
    return result.get("data", result)


def close_position(ticker: str, quantity: float) -> dict:
    """Close (sell) an open long position."""
    return execute_trade({"action": "sell", "ticker": ticker, "quantity": quantity})
