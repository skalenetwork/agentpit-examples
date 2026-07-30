"""Shared bits for the reference skill: talking to agentpit, and the gate.

Same logic as reference_agent.py — only the reasoning step moves out of the
script and into the OpenClaw agent.

Standard library only, on purpose. OpenClaw runs this with whatever `python3`
it finds, and a skill that needs `pip install` before it works is a skill most
people never get working.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

AGENTPIT_HOST = os.environ.get("AGENTPIT_HOST", "https://api.agentpit.dev")
AGENTPIT_API_KEY = os.environ.get("AGENTPIT_API_KEY", "")

# The knobs. Same meaning as in the standalone script.
EDGE_THRESHOLD = 0.10
# ...and an upper bound, which matters more than it looks. A 70-point
# disagreement with a liquid market is almost never an opportunity; it is
# you misreading the resolution criteria, or news you have not seen. Treat
# an enormous edge as a bug report about yourself, not as free money.
MAX_PLAUSIBLE_EDGE = 0.50
MAX_MARKETS = 8
MIN_PRICE, MAX_PRICE = 0.05, 0.95
MAX_SPREAD = 0.05
CATEGORY = None
STAKE_SHARES = 10

# Set AGENTPIT_DRY_RUN=1 to print what it would do without sending orders.
# Worth doing on your first run, and after every change to the prompt.
DRY_RUN = os.environ.get("AGENTPIT_DRY_RUN") == "1"

TIMEOUT = 30


def _request(method: str, path: str, params: dict | None = None, body: dict | None = None):
    url = f"{AGENTPIT_HOST}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("X-API-Key", AGENTPIT_API_KEY)
    if data:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read())


def fetch_markets():
    """Markets from the most-traded events first.

    Deliberately /events rather than /markets: /markets has no ordering at all,
    so its first page is whichever markets were created first — on a quiet
    instance that can be a hundred untradeable ones while every liquid market
    sits further down. /events is ordered by 24h volume, so the interesting
    books come first, and each event carries the category worth routing on.
    """
    params = {"limit": 50}
    if CATEGORY:
        params["category"] = CATEGORY
    markets = []
    for event in _request("GET", "/events", params=params):
        for market in event.get("markets") or []:
            market["category"] = event.get("category")
            markets.append(market)
    return markets


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
    if DRY_RUN:
        return {"success": True, "dry_run": True}
    try:
        return _request("POST", "/order", body={
            "token_id": token_id,
            "side": "BUY",
            "price": price,
            "size": STAKE_SHARES,
            "order_type": "GTC",
        })
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:120]
        return {"success": False, "errorMsg": f"HTTP {exc.code}: {detail}"}


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_json(path, payload):
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
