"""
Pre-screens the watchlist to surface the highest-opportunity tickers each cycle.

Scoring factors (all fetched via Kraken CLI live prices):
  - 1-day price momentum
  - Bid-ask spread tightness (liquidity proxy)
  - Intraday range (volatility proxy)

Returns the top N tickers ranked by combined score.
"""

import subprocess
import json
import os
from bridge.kraken_executor import XSTOCK_PAIRS

WATCHLIST = ["NVDA", "TSLA", "AAPL", "META", "MSFT", "GOOGL", "SPY", "QQQ"]


def _fetch_ticker(ticker: str) -> dict | None:
    xstock = XSTOCK_PAIRS.get(ticker)
    if not xstock:
        return None
    try:
        result = subprocess.run(
            ["kraken", "ticker", f"{xstock}/USD",
             "--asset-class", "tokenized_asset", "-o", "json"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ},
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def _score_ticker(data: dict) -> float:
    """
    Heuristic score. Higher = more interesting to trade right now.
    Uses Kraken ticker JSON fields: ask, bid, high, low, open, last
    """
    try:
        ask = float(data["ask"][0])
        bid = float(data["bid"][0])
        high = float(data["high"][0])
        low = float(data["low"][0])
        open_p = float(data["open"])
        last = float(data["last"][0] if isinstance(data.get("last"), list) else data.get("last", ask))

        # Momentum: how far price has moved from open
        momentum = abs(last - open_p) / open_p if open_p else 0

        # Volatility: intraday range
        volatility = (high - low) / low if low else 0

        # Tightness: tight spread = liquid = tradeable
        spread = (ask - bid) / ask if ask else 1
        tightness = max(0, 1 - spread * 100)

        return momentum * 0.5 + volatility * 0.35 + tightness * 0.15
    except Exception:
        return 0.0


def scan(top_n: int = 3) -> list[str]:
    """
    Fetch live prices for the watchlist and return the top_n tickers by score.
    Falls back to the full watchlist if Kraken CLI is unavailable.
    """
    scores = {}
    for ticker in WATCHLIST:
        data = _fetch_ticker(ticker)
        if data:
            scores[ticker] = _score_ticker(data)
        else:
            scores[ticker] = 0.0

    ranked = sorted(scores, key=lambda t: scores[t], reverse=True)
    top = ranked[:top_n]

    print(f"[SCANNER] Top tickers this cycle: {top}")
    for t in top:
        print(f"  {t}: score={scores[t]:.4f}")

    return top if top else WATCHLIST[:top_n]
