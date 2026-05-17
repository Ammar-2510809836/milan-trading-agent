"""
Autonomous trading loop.

Every cycle:
  1. Enforce stop-losses on open positions
  2. Scan market for top-opportunity tickers
  3. Run TradingAgents multi-agent analysis (Gemini 2.5 Pro/Flash)
  4. Size position and execute via Kraken CLI
"""

import sys
import os
import schedule
import time
from datetime import datetime

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "TradingAgents"))

from bridge.gemini_config import TRADING_AGENTS_CONFIG
from bridge.kraken_executor import execute_trade, get_balance
from bridge.portfolio_manager import (
    get_position_size, record_entry, record_exit,
    enforce_stop_losses, is_at_capacity, has_open_position,
    get_ticker_price,
)
from bridge.market_scanner import scan
from bridge.trade_logger import (
    log_cycle_start, log_cycle_end, log_analysis,
    log_trade, log_error, log_stop_loss, log_agent_state,
)

CYCLE_INTERVAL_HOURS = 1


def _map_conviction(decision: dict) -> str:
    reasoning = decision.get("reasoning", "").lower()
    action = decision.get("action", "hold").lower()
    if action == "hold":
        return "low"
    strong_keywords = ["strong", "very bullish", "very bearish", "high confidence", "clear signal"]
    if any(kw in reasoning for kw in strong_keywords):
        return "high"
    return "medium"


def _normalize_decision(ticker: str, state: dict, decision) -> dict:
    """TradingAgents returns a 5-tier rating string; normalize to our dict shape."""
    if isinstance(decision, dict):
        return decision

    if isinstance(decision, str):
        rating = decision.strip().lower()
        if rating in ("buy", "overweight"):
            action = "buy"
        elif rating in ("sell", "underweight"):
            action = "sell"
        else:
            action = "hold"

        reasoning = ""
        try:
            reasoning = str(state.get("final_trade_decision", "")).strip()
        except Exception:
            reasoning = ""

        return {
            "action": action,
            "ticker": ticker,
            "quantity": 1,
            "reasoning": reasoning,
            "rating": decision,
        }

    return {"action": "hold", "ticker": ticker, "quantity": 0, "reasoning": "", "raw": decision}


def run_trading_cycle(
    tickers: list[str] | None = None,
    *,
    execute_trades: bool = True,
    fast: bool = False,
):
    print(f"\n{'='*60}")
    print(f"[AGENT] Cycle started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if execute_trades:
        enforce_stop_losses()

    focus = tickers if tickers else scan(top_n=3)
    log_cycle_start(focus)

    if execute_trades:
        print("[AGENT] Balance:", get_balance())

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
    except ImportError:
        msg = "TradingAgents not installed. Run: cd TradingAgents && pip install ."
        print(f"[AGENT] ERROR: {msg}")
        log_error("import", msg)
        return

    config = TRADING_AGENTS_CONFIG.copy()
    selected_analysts = ["market"] if fast else ["market", "social", "news", "fundamentals"]
    ta = TradingAgentsGraph(debug=False, config=config, selected_analysts=selected_analysts)
    today = datetime.now().strftime("%Y-%m-%d")

    for ticker in focus:
        try:
            if is_at_capacity():
                print(f"[AGENT] Portfolio at max capacity — skipping {ticker}")
                break

            print(f"\n[AGENT] Analyzing {ticker}...")
            _state, raw_decision = ta.propagate(ticker, today)
            decision = _normalize_decision(ticker, _state, raw_decision)
            action = str(decision.get("action", "hold")).lower()
            reasoning = str(decision.get("reasoning", ""))
            conviction = _map_conviction(decision)

            # Log full multi-agent pipeline state for dashboard
            try:
                log_agent_state(ticker, _state)
            except Exception:
                pass

            print(f"[AGENT] Decision: {action.upper()} {ticker} | {reasoning[:120]}")
            log_analysis(ticker, action, conviction, reasoning)

            if action == "hold":
                continue

            if action == "buy" and has_open_position(ticker):
                print(f"[AGENT] Already holding {ticker} — skipping buy.")
                continue

            balance = get_balance()
            try:
                portfolio_usd = float(
                    balance.get("USD", balance.get("balance", {}).get("USD", 10000))
                )
            except Exception:
                portfolio_usd = 10000.0

            quantity, leverage = get_position_size(ticker, portfolio_usd, conviction)

            if quantity <= 0:
                print(f"[AGENT] Could not size position for {ticker} — skipping.")
                continue

            result = {"status": "skipped"}
            if execute_trades:
                result = execute_trade(
                    {
                        "action": action,
                        "ticker": ticker,
                        "quantity": quantity,
                        "leverage": leverage,
                        "reasoning": reasoning,
                    }
                )

            price = get_ticker_price(ticker) or 0.0

            if not execute_trades:
                log_trade(ticker, action, quantity, price, leverage, "dry_run")
                print(f"[AGENT] DRY RUN: would {action} {quantity} {ticker} @ ~${price:.2f} (leverage={leverage}x)")
            elif result.get("status") == "executed":
                if action == "buy":
                    record_entry(ticker, quantity, price, action)
                else:
                    record_exit(ticker)
                log_trade(ticker, action, quantity, price, leverage, "executed")
                print(f"[AGENT] {action.upper()} {quantity} {ticker} @ ~${price:.2f} (leverage={leverage}x)")
            else:
                log_trade(
                    ticker,
                    action,
                    quantity,
                    price,
                    leverage,
                    "failed",
                    str(result.get("error", "")),
                )
                print(f"[AGENT] Trade not executed: {result}")

        except Exception as e:
            print(f"[AGENT] ERROR on {ticker}: {e}")
            log_error(ticker, str(e))
            continue

    log_cycle_end()
    print(f"[AGENT] Cycle complete at {datetime.now().strftime('%H:%M:%S')}")


def run_once(
    ticker: str | None = None,
    *,
    execute_trades: bool = True,
    fast: bool = False,
):
    tickers = [ticker] if ticker else None
    run_trading_cycle(tickers, execute_trades=execute_trades, fast=fast)


def run_scheduler(*, execute_trades: bool = True, fast: bool = False):
    print("[SCHEDULER] Autonomous trading agent starting...")
    run_trading_cycle(execute_trades=execute_trades, fast=fast)

    schedule.every(CYCLE_INTERVAL_HOURS).hours.do(
        run_trading_cycle, execute_trades=execute_trades, fast=fast
    )
    print(f"[SCHEDULER] Running every {CYCLE_INTERVAL_HOURS}h. Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(60)
