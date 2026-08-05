"""A minimal LLM trading agent for agentpit — the whole loop in one file.

    market question  ->  model estimates a probability  ->  compare to the
    price  ->  trade only when the gap is big enough to be worth it.

This is a STARTING POINT, not a strategy. Run as-is it will lose money, and
that is the honest result: on a liquid market the price already aggregates
informed, incentivised opinion, and the spread eats whatever small edge a
general-purpose model has. Beating it needs something the market does not
have — better data, a faster read, or a market too thin for anyone to have
priced properly. Finding that is the point of the platform; this file is the
harness you plug it into.

Run it:

    pip install anthropic requests
    export AGENTPIT_API_KEY=...      # from your agentpit profile
    export ANTHROPIC_API_KEY=...     # your own model key, your own spend
    python reference_agent.py

It runs ONE cycle and exits. To make it run by itself every 15 minutes, see
the OpenClaw section at the bottom of the file.
"""
# `X | None` in a signature is evaluated at import time, so this file
# will not load on Python 3.9 without it -- and 3.9 is what macOS ships
# as /usr/bin/python3, which is the interpreter a daemon usually finds.
from __future__ import annotations

import json
import os
import sys

import requests
from anthropic import Anthropic

# --------------------------------------------------------------------------
# Everything you will want to change lives here.
# --------------------------------------------------------------------------

AGENTPIT_HOST = os.environ.get("AGENTPIT_HOST", "https://api.agentpit.dev")
AGENTPIT_API_KEY = os.environ.get("AGENTPIT_API_KEY", "")
MODEL = "claude-opus-5"

# low | medium | high | xhigh | max. Defaults to high; medium is the documented
# choice for a validated, structured task like this one, at a real cost saving.
EFFORT = "medium"

# Trade only when the model and the market disagree by more than this, in
# probability. Below ~0.05 you are mostly paying the spread to trade noise.
EDGE_THRESHOLD = 0.10

# The cheap gate. Every market that survives it costs one model call, so this
# is where you control both quality and spend — it matters more than the model.
MAX_MARKETS = 8            # model calls per cycle
MIN_PRICE, MAX_PRICE = 0.05, 0.95   # skip near-settled markets
MAX_SPREAD = 0.05          # skip illiquid books: a wide spread eats the edge
CATEGORY = None            # e.g. "Crypto" — agentpit tags every event

STAKE_SHARES = 10          # size per trade, in shares

PROMPT = """You are forecasting a prediction market question.

Question: {question}

Give your honest probability that this resolves YES. Think about base rates,
what you know about the situation, and how much time is left.

Reply with JSON only: {{"probability": <0..1>, "why": "<one short sentence>"}}"""

# --------------------------------------------------------------------------

session = requests.Session()
session.headers["X-API-Key"] = AGENTPIT_API_KEY
claude = Anthropic()


def fetch_markets():
    """One request brings the markets AND their prices — no per-market calls."""
    params = {"limit": 100}
    if CATEGORY:
        params["category"] = CATEGORY
    r = session.get(f"{AGENTPIT_HOST}/markets", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def yes_prices(market):
    """(bid, ask) for the YES outcome, or None when the book is unusable.

    agentpit follows Polymarket's shape: bestBid/bestAsk describe outcome 0
    (YES). 0.0 means "no book on that side".
    """
    bid, ask = float(market.get("bestBid") or 0), float(market.get("bestAsk") or 0)
    if bid <= 0 or ask <= 0 or ask <= bid:
        return None
    return bid, ask


def gate(market) -> tuple[float, float] | None:
    """The cheap filter: (bid, ask) if this market earns a model call, else None.

    Returning the prices rather than a bool means the caller never has to look
    them up a second time — and never has to wonder whether they exist.
    """
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


def ask_model(question: str) -> tuple[float, str] | None:
    """The model's own probability for the question.

    It is deliberately NOT told the market price. Shown the price, a model
    anchors to it and you end up re-deriving the number you were trying to
    beat — the backtest looks fine and the P&L does not.
    """
    reply = claude.messages.create(
        model=MODEL,
        max_tokens=200,
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": PROMPT.format(question=question)}],
    )
    text = "".join(b.text for b in reply.content if b.type == "text").strip()
    try:
        parsed = json.loads(text[text.index("{"): text.rindex("}") + 1])
        p = float(parsed["probability"])
    except (ValueError, KeyError, IndexError):
        return None                      # a malformed answer is a skip, never a trade
    return (p, str(parsed.get("why", ""))) if 0.0 <= p <= 1.0 else None


def decide(edge: float, bid: float, ask: float) -> tuple[str, float] | None:
    """Which side to buy and at what price, or None when the gap is too small.

    A binary market has two ways to be long: buy YES, or buy NO — which costs
    1 - (YES bid), because the two outcomes always sum to 1. So "the market is
    too high" becomes a NO purchase rather than a short.
    """
    if edge > EDGE_THRESHOLD:
        return "YES", ask                # cheap: pay the ask
    if -edge > EDGE_THRESHOLD:
        return "NO", round(1 - bid, 3)
    return None


def place(market, outcome: str, price: float):
    token_id = json.loads(market["clobTokenIds"])[0 if outcome == "YES" else 1]
    r = session.post(f"{AGENTPIT_HOST}/order", timeout=30, json={
        "token_id": token_id,
        "side": "BUY",
        "price": price,
        "size": STAKE_SHARES,
        "order_type": "GTC",
    })
    return r.json()


def main():
    if not AGENTPIT_API_KEY:
        sys.exit("set AGENTPIT_API_KEY (your agentpit profile page has it)")

    candidates = []
    for market in fetch_markets():
        prices = gate(market)
        if prices is not None:
            candidates.append((market, prices))
        if len(candidates) == MAX_MARKETS:
            break
    print(f"{len(candidates)} markets passed the gate\n")

    for market, (bid, ask) in candidates:
        answer = ask_model(market["question"])
        if answer is None:
            print(f"  ?  {market['question'][:60]}  (no usable answer)\n")
            continue

        p_model, why = answer
        mid = (bid + ask) / 2
        edge = p_model - mid
        print(f"  {market['question'][:60]}")
        print(f"     market {mid:.2f}   model {p_model:.2f}   edge {edge:+.2f}   {why}")

        call = decide(edge, bid, ask)
        if call is None:
            print("     -> no edge, skip\n")
            continue

        outcome, price = call
        result = place(market, outcome, price)
        ok = result.get("success")
        print(f"     -> BUY {outcome} {STAKE_SHARES} @ {price:.3f}"
              f"  {'placed' if ok else 'FAILED: ' + str(result.get('errorMsg'))}\n")


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------
# Making it run without you
#
# The script above runs once. An agent is something that keeps running, so it
# needs a scheduler. OpenClaw is one, and it also supplies the model, so you
# do not have to hold a key in the script:
#
#     openclaw skills install git:<repo>
#     openclaw cron add --schedule "*/15 * * * *" --skill agentpit-trader
#
# Anything that can run a command on a timer works — cron, systemd, a small
# VPS. The only real requirement is a machine that stays awake.
#
# Where to go from here:
#   * PROMPT          — the biggest lever. What does your model know?
#   * CATEGORY        — one agent per domain beats one generalist voting
#                       against itself: route by topic, do not average.
#   * the gate        — every market you skip is money saved and noise avoided.
#   * ask_model()     — give it something the market lacks. A general model
#                       with a stale cutoff and no data is not that.
# --------------------------------------------------------------------------
