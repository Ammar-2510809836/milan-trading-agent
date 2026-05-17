import os
import sys
import faulthandler
import time
from datetime import datetime

# Ensure repo imports work when running from project root.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "TradingAgents"))


def main():
    ticker = os.environ.get("SMOKE_TICKER", "AAPL")
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"[SMOKE] starting at {datetime.now().isoformat(timespec='seconds')}")
    print(f"[SMOKE] ticker={ticker} date={today}")

    # If we hang, print Python stack traces so we can see where.
    faulthandler.enable()
    faulthandler.dump_traceback_later(90, repeat=True)

    from bridge.gemini_config import TRADING_AGENTS_CONFIG
    print(f"[SMOKE] llm_provider={TRADING_AGENTS_CONFIG.get('llm_provider')}")
    print(f"[SMOKE] backend_url={TRADING_AGENTS_CONFIG.get('backend_url')}")

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    t0 = time.time()
    print("[SMOKE] init TradingAgentsGraph...")
    ta = TradingAgentsGraph(debug=False, config=TRADING_AGENTS_CONFIG)
    print(f"[SMOKE] graph init ok ({time.time()-t0:.1f}s)")

    print("[SMOKE] propagate...")
    t1 = time.time()
    state, decision = ta.propagate(ticker, today)
    print(f"[SMOKE] propagate ok ({time.time()-t1:.1f}s)")
    print("[SMOKE] decision:", decision)
    print("[SMOKE] done")


if __name__ == "__main__":
    main()

