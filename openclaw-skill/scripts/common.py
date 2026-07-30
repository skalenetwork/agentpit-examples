"""Shared bits for the reference skill: talking to agentpit, and the gate.

Same logic as examples/reference_agent.py — only the reasoning step moves out
of the script and into the OpenClaw agent.
"""
import json
import os

import requests

AGENTPIT_HOST = os.environ.get("AGENTPIT_HOST", "https://api.agentpit.dev")
AGENTPIT_API_KEY = os.environ.get("AGENTPIT_API_KEY", "")

# The knobs. Same meaning as in the standalone script.
EDGE_THRESHOLD = 0.10
MAX_MARKETS = 8
MIN_PRICE, MAX_PRICE = 0.05, 0.95
MAX_SPREAD = 0.05
CATEGORY = None
STAKE_SHARES = 10

session = requests.Session()
session.headers["X-API-Key"] = AGENTPIT_API_KEY


def fetch_markets():
    params = {"limit": 100}
    if CATEGORY:
        params["category"] = CATEGORY
    r = session.get(f"{AGENTPIT_HOST}/markets", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def yes_prices(market) -> tuple[float, float] | None:
    """(bid, ask) for the YES outcome; None when the book is unusable."""
    bid, ask = float(market.get("bestBid") or 0), float(market.get("bestAsk") or 0)
    if bid <= 0 or ask <= 0 or ask <= bid:
        return None
    return bid, ask


def gate(market) -> tuple[float, float] | None:
    """(bid, ask) if this market earns a model call, else None."""
    if not market.get("acceptingOrders") or market.get("closed"):
        return None
    prices = yes_prices(market)
    if prices is None:
        return None
    bid, ask = prices
    mid = (bid + ask) / 2
    if not (MIN_PRICE <= mid <= MAX_PRICE) or (ask - bid) > MAX_SPREAD:
        return None
    return bid, ask


def place(token_id: str, price: float):
    r = session.post(f"{AGENTPIT_HOST}/order", timeout=30, json={
        "token_id": token_id,
        "side": "BUY",
        "price": price,
        "size": STAKE_SHARES,
        "order_type": "GTC",
    })
    return r.json()


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_json(path, payload):
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
