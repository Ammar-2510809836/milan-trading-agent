"""
Trading agent dashboard backend.
Run: uvicorn dashboard.app:app --host 0.0.0.0 --port 8080 --reload
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, "TradingAgents"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from bridge.trade_logger import read_recent, read_latest_pipeline
from bridge.kraken_executor import get_balance, get_open_orders, get_ticker_price, PAPER_MODE, XSTOCK_PAIRS

POSITIONS_FILE = os.path.join(_project_root, "positions.json")
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Trading Agent Dashboard")

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

manager = ConnectionManager()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _load_positions() -> dict:
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return {}


def _enrich_positions(positions: dict) -> list[dict]:
    """Add current price + unrealized PnL to each position."""
    result = []
    for ticker, pos in positions.items():
        current_price = get_ticker_price(ticker)
        entry = pos.get("entry_price", 0)
        qty = pos.get("quantity", 0)
        if current_price and entry:
            unrealized = (current_price - entry) * qty
            pnl_pct = (current_price - entry) / entry * 100
        else:
            unrealized = 0.0
            pnl_pct = 0.0
        result.append({
            **pos,
            "current_price": current_price,
            "unrealized_pnl": round(unrealized, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
    return result


def _compute_total_pnl(positions: list[dict], logs: list[dict]) -> dict:
    unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
    realized = sum(
        (e.get("price", 0) * e.get("quantity", 0))
        for e in logs
        if e.get("type") == "trade" and e.get("action") == "sell" and e.get("status") == "executed"
    )
    return {"unrealized": round(unrealized, 2), "realized": round(realized, 2),
            "total": round(unrealized + realized, 2)}


# ── REST endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(DASHBOARD_DIR, "index.html")
    with open(html_path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/status")
async def status():
    logs = read_recent(20)
    last_cycle = next((e for e in reversed(logs) if e["type"] == "cycle_start"), None)
    last_end   = next((e for e in reversed(logs) if e["type"] == "cycle_end"), None)

    if last_cycle and last_end:
        running = last_cycle["ts"] > last_end["ts"]
    elif last_cycle:
        running = True
    else:
        running = False

    return {
        "running": running,
        "paper_mode": PAPER_MODE,
        "mode_label": "PAPER" if PAPER_MODE else "LIVE",
        "last_cycle": last_cycle["ts"] if last_cycle else None,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/balance")
async def balance():
    return get_balance()


@app.get("/api/positions")
async def positions():
    raw = _load_positions()
    return _enrich_positions(raw)


@app.get("/api/pnl")
async def pnl():
    raw = _load_positions()
    enriched = _enrich_positions(raw)
    logs = read_recent(200)
    return _compute_total_pnl(enriched, logs)


@app.get("/api/logs")
async def logs(n: int = 50):
    return read_recent(n)


@app.get("/api/trades")
async def trades(n: int = 30):
    logs = read_recent(200)
    return [e for e in logs if e["type"] == "trade"][:n]


@app.get("/api/decisions")
async def decisions(n: int = 20):
    logs = read_recent(200)
    return [e for e in logs if e["type"] == "analysis"][:n]


@app.get("/api/pipeline")
async def pipeline(ticker: str = None):
    return read_latest_pipeline(ticker)


@app.get("/api/full")
async def full():
    """Single endpoint the dashboard polls — everything in one shot."""
    raw = _load_positions()
    enriched = _enrich_positions(raw)
    logs = read_recent(200)
    pnl = _compute_total_pnl(enriched, logs)
    recent_logs = read_recent(60)

    return {
        "status": (await status()),
        "balance": get_balance(),
        "positions": enriched,
        "pnl": pnl,
        "trades": [e for e in logs if e["type"] == "trade"][:20],
        "decisions": [e for e in logs if e["type"] == "analysis"][:10],
        "logs": recent_logs,
        "pipeline": read_latest_pipeline(),
    }


# ── WebSocket live feed ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            payload = await full()
            await ws.send_json(payload)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(ws)
