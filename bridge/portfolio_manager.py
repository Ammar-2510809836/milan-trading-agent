"""
Position sizing and risk management for the hackathon trading agent.

Strategy:
- 2% of portfolio per base trade (conservative sizing)
- Up to 2x leverage on high-conviction signals (NVDA, TSLA)
- Stop-loss at -5% from entry price
- Max 5 concurrent open positions
- Never risk more than 10% of portfolio in a single ticker
"""

import json
import os
from datetime import datetime
from bridge.kraken_executor import get_ticker_price, close_position, XSTOCK_PAIRS

POSITIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "positions.json")

# Tickers eligible for leverage (high liquidity, Kraken supports up to 3x)
LEVERAGE_ELIGIBLE = {"NVDA", "TSLA", "AAPL", "MSFT", "META"}

STOP_LOSS_PCT = 0.05   # cut at -5%
MAX_POSITIONS = 5
BASE_POSITION_PCT = 0.02   # 2% of portfolio per trade


def _load_positions() -> dict:
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return {}


def _save_positions(positions: dict):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def get_position_size(ticker: str, portfolio_value: float, conviction: str) -> tuple[float, int]:
    """
    Return (quantity_in_shares, leverage) for a trade.

    conviction: "high" | "medium" | "low"
    """
    price = get_ticker_price(ticker)
    if not price or price <= 0:
        return 0.0, 1

    pct = BASE_POSITION_PCT
    leverage = 1

    if conviction == "high" and ticker in LEVERAGE_ELIGIBLE:
        pct = BASE_POSITION_PCT * 2   # 4% of portfolio
        leverage = 2
    elif conviction == "medium":
        pct = BASE_POSITION_PCT * 1.5  # 3% of portfolio

    dollar_amount = portfolio_value * pct
    quantity = round(dollar_amount / price, 4)
    quantity = max(quantity, 0.01)  # Kraken minimum fractional share

    return quantity, leverage


def record_entry(ticker: str, quantity: float, price: float, action: str):
    positions = _load_positions()
    positions[ticker] = {
        "ticker": ticker,
        "quantity": quantity,
        "entry_price": price,
        "action": action,
        "entry_time": datetime.now().isoformat(),
    }
    _save_positions(positions)


def record_exit(ticker: str):
    positions = _load_positions()
    positions.pop(ticker, None)
    _save_positions(positions)


def check_stop_losses() -> list[dict]:
    """Check all open positions for stop-loss triggers. Returns list of tickers to close."""
    positions = _load_positions()
    to_close = []

    for ticker, pos in positions.items():
        if pos["action"] != "buy":
            continue
        current_price = get_ticker_price(ticker)
        if current_price is None:
            continue
        entry = pos["entry_price"]
        pnl_pct = (current_price - entry) / entry
        if pnl_pct <= -STOP_LOSS_PCT:
            print(f"[RISK] Stop-loss triggered for {ticker}: {pnl_pct:.1%} (entry={entry}, now={current_price})")
            to_close.append({"ticker": ticker, "quantity": pos["quantity"], "pnl_pct": pnl_pct})

    return to_close


def get_open_position_count() -> int:
    return len(_load_positions())


def is_at_capacity() -> bool:
    return get_open_position_count() >= MAX_POSITIONS


def has_open_position(ticker: str) -> bool:
    return ticker in _load_positions()


def enforce_stop_losses():
    """Close any positions that have hit the stop-loss threshold."""
    for pos in check_stop_losses():
        print(f"[RISK] Closing {pos['ticker']} — PnL {pos['pnl_pct']:.1%}")
        result = close_position(pos["ticker"], pos["quantity"])
        if result.get("status") == "executed":
            record_exit(pos["ticker"])
