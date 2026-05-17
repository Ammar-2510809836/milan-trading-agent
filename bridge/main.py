#!/usr/bin/env python3
"""
Milan AI Week Hackathon — Autonomous xStocks Trading Agent
Powered by: TradingAgents (Gemini 2.5) + Kraken CLI
"""

import sys
import os
import argparse

# Project root on path so `bridge.*` and `TradingAgents.*` are both importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "TradingAgents"))


def main():
    parser = argparse.ArgumentParser(description="Autonomous xStocks Trading Agent")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--ticker", type=str, help="Analyze a single ticker (implies --once)")
    parser.add_argument("--paper", action="store_true", default=True, help="Paper trading mode (default)")
    parser.add_argument("--live", action="store_true", help="Live trading mode (real money)")
    parser.add_argument("--dry-run", action="store_true", help="Run analysis only (no trades executed)")
    parser.add_argument("--fast", action="store_true", help="Fast mode (market-only analysts)")
    parser.add_argument("--balance", action="store_true", help="Print current balance and exit")
    parser.add_argument("--scan", action="store_true", help="Run market scanner and exit")
    args = parser.parse_args()

    # Configure paper/live mode before importing executor
    if args.live:
        import bridge.kraken_executor as ex
        ex.PAPER_MODE = False
        print("[MAIN] *** LIVE TRADING MODE — REAL MONEY ***")
    else:
        print("[MAIN] Paper trading mode (safe, uses live prices)")

    if args.balance:
        from bridge.kraken_executor import get_balance
        import json
        print(json.dumps(get_balance(), indent=2))
        return

    if args.scan:
        from bridge.market_scanner import scan
        top = scan(top_n=5)
        print(f"Top tickers: {top}")
        return

    from bridge.scheduler import run_once, run_scheduler

    if args.once or args.ticker:
        run_once(args.ticker, execute_trades=not args.dry_run, fast=args.fast)
    else:
        run_scheduler(execute_trades=not args.dry_run, fast=args.fast)


if __name__ == "__main__":
    main()
