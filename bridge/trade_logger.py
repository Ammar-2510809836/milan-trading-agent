"""
Structured event logger — writes JSON lines to trade_log.jsonl.
Dashboard reads this file to show real-time agent activity.
"""

import json
import os
from datetime import datetime, timezone

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "trade_log.jsonl")
MAX_ENTRIES = 500   # rotate after this many lines


def _write(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(event)

    # Simple rotation: keep last MAX_ENTRIES lines
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            lines = f.readlines()
        if len(lines) >= MAX_ENTRIES:
            lines = lines[-(MAX_ENTRIES - 1):]
        lines.append(line + "\n")
        with open(LOG_FILE, "w") as f:
            f.writelines(lines)
    else:
        with open(LOG_FILE, "w") as f:
            f.write(line + "\n")


def log_cycle_start(tickers: list[str]):
    _write({"type": "cycle_start", "tickers": tickers})


def log_cycle_end():
    _write({"type": "cycle_end"})


def log_scan(scores: dict, top: list[str]):
    _write({"type": "scan", "scores": scores, "top": top})


def log_analysis(ticker: str, action: str, conviction: str, reasoning: str):
    _write({
        "type": "analysis",
        "ticker": ticker,
        "action": action,
        "conviction": conviction,
        "reasoning": reasoning[:400],
    })


def log_trade(ticker: str, action: str, quantity: float, price: float,
              leverage: int, status: str, error: str = ""):
    _write({
        "type": "trade",
        "ticker": ticker,
        "action": action,
        "quantity": quantity,
        "price": price,
        "leverage": leverage,
        "status": status,
        "error": error,
    })


def log_stop_loss(ticker: str, pnl_pct: float, quantity: float):
    _write({
        "type": "stop_loss",
        "ticker": ticker,
        "pnl_pct": round(pnl_pct, 4),
        "quantity": quantity,
    })


def log_error(context: str, error: str):
    _write({"type": "error", "context": context, "error": str(error)[:300]})


def read_recent(n: int = 100) -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        lines = f.readlines()
    entries = []
    for line in reversed(lines[-n:]):
        try:
            entries.append(json.loads(line.strip()))
        except Exception:
            pass
    return list(reversed(entries))
