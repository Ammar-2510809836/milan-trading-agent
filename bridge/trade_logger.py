"""
Structured event logger — writes JSON lines to trade_log.jsonl.
Dashboard reads this file to show real-time agent pipeline activity.
"""

import json
import os
from datetime import datetime, timezone

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "trade_log.jsonl")
MAX_ENTRIES = 1000


def _write(event: dict):
    event["ts"] = datetime.now(timezone.utc).isoformat()
    line = json.dumps(event)
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


# ── Cycle lifecycle ───────────────────────────────────────────────────────────

def log_cycle_start(tickers: list):
    _write({"type": "cycle_start", "tickers": tickers})

def log_cycle_end():
    _write({"type": "cycle_end"})


# ── Agent pipeline — one event per agent ─────────────────────────────────────

def log_agent_state(ticker: str, state: dict):
    """Extract and log every agent's output from TradingAgents state."""
    def _trim(text, n=600):
        if not text:
            return ""
        return str(text)[:n] + ("…" if len(str(text)) > n else "")

    # 4 analyst reports
    _write({"type": "agent_market",        "ticker": ticker, "report": _trim(state.get("market_report", ""))})
    _write({"type": "agent_sentiment",     "ticker": ticker, "report": _trim(state.get("sentiment_report", ""))})
    _write({"type": "agent_news",          "ticker": ticker, "report": _trim(state.get("news_report", ""))})
    _write({"type": "agent_fundamentals",  "ticker": ticker, "report": _trim(state.get("fundamentals_report", ""))})

    # Bull vs Bear debate
    debate = state.get("investment_debate_state") or {}
    _write({
        "type": "agent_bull",
        "ticker": ticker,
        "argument": _trim(debate.get("bull_history", "")),
        "judge": _trim(debate.get("judge_decision", "")),
    })
    _write({
        "type": "agent_bear",
        "ticker": ticker,
        "argument": _trim(debate.get("bear_history", "")),
    })
    _write({
        "type": "agent_investment_plan",
        "ticker": ticker,
        "plan": _trim(state.get("investment_plan", "")),
    })

    # Trader
    _write({
        "type": "agent_trader",
        "ticker": ticker,
        "plan": _trim(state.get("trader_investment_plan", "")),
    })

    # Risk management
    risk = state.get("risk_debate_state") or {}
    _write({"type": "agent_risk_aggressive",  "ticker": ticker, "argument": _trim(risk.get("aggressive_history", ""))})
    _write({"type": "agent_risk_neutral",     "ticker": ticker, "argument": _trim(risk.get("neutral_history", ""))})
    _write({"type": "agent_risk_conservative","ticker": ticker, "argument": _trim(risk.get("conservative_history", ""))})
    _write({
        "type": "agent_risk_decision",
        "ticker": ticker,
        "decision": _trim(risk.get("judge_decision", "")),
    })

    # Final
    _write({
        "type": "agent_final",
        "ticker": ticker,
        "decision": _trim(state.get("final_trade_decision", "")),
    })


# ── Scan, analysis summary, trade, errors ────────────────────────────────────

def log_scan(scores: dict, top: list):
    _write({"type": "scan", "scores": scores, "top": top})

def log_analysis(ticker: str, action: str, conviction: str, reasoning: str):
    _write({"type": "analysis", "ticker": ticker, "action": action,
            "conviction": conviction, "reasoning": reasoning[:400]})

def log_trade(ticker: str, action: str, quantity: float, price: float,
              leverage: int, status: str, error: str = ""):
    _write({"type": "trade", "ticker": ticker, "action": action,
            "quantity": quantity, "price": price, "leverage": leverage,
            "status": status, "error": error})

def log_stop_loss(ticker: str, pnl_pct: float, quantity: float):
    _write({"type": "stop_loss", "ticker": ticker,
            "pnl_pct": round(pnl_pct, 4), "quantity": quantity})

def log_error(context: str, error: str):
    _write({"type": "error", "context": context, "error": str(error)[:300]})


# ── Reader ────────────────────────────────────────────────────────────────────

def read_recent(n: int = 200) -> list:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        lines = f.readlines()
    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line.strip()))
        except Exception:
            pass
    return entries


def read_latest_pipeline(ticker: str = None) -> dict:
    """Return the most recent full pipeline run for a ticker (or the latest overall)."""
    logs = read_recent(500)
    # find the latest cycle_start
    latest_cycle_ts = None
    for e in reversed(logs):
        if e["type"] == "cycle_start":
            latest_cycle_ts = e["ts"]
            if not ticker:
                ticker = (e.get("tickers") or [None])[0]
            break

    if not latest_cycle_ts:
        return {}

    pipeline_types = {
        "agent_market", "agent_sentiment", "agent_news", "agent_fundamentals",
        "agent_bull", "agent_bear", "agent_investment_plan",
        "agent_trader", "agent_risk_aggressive", "agent_risk_neutral",
        "agent_risk_conservative", "agent_risk_decision", "agent_final",
        "analysis", "trade",
    }

    result = {"ticker": ticker, "cycle_ts": latest_cycle_ts}
    for e in logs:
        if e["ts"] < latest_cycle_ts:
            continue
        t = e.get("type", "")
        if t in pipeline_types:
            if ticker and e.get("ticker") and e["ticker"] != ticker:
                continue
            result[t] = e
    return result
