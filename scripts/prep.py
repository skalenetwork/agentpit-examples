"""Step 1: pick the markets worth thinking about, and write the questions out.

Deliberately writes TWO kinds of file:

  ask_<id>.json     the QUESTION ONLY — this is all the agent ever reads
  market_<id>.json  prices and token ids — for finalize.py, never for the agent

That split is the point, not tidiness. A model shown the market price anchors
to it and hands back a number close to the one you were trying to beat. Keeping
the price in a file the agent is never told to open makes that mistake
impossible rather than merely discouraged.
"""
import os
import sys
import tempfile

from common import MAX_MARKETS, fetch_markets, gate, write_json


def main():
    if not os.environ.get("AGENTPIT_API_KEY"):
        print("CYCLE_ABORTED no AGENTPIT_API_KEY in the environment")
        return

    try:
        markets = fetch_markets()
    except Exception as exc:                 # agentpit down, network, bad key
        print(f"CYCLE_ABORTED {type(exc).__name__}: {exc}")
        return

    cycle_dir = tempfile.mkdtemp(prefix="agentpit-cycle-")
    picked = 0
    for market in markets:
        prices = gate(market)
        if prices is None:
            continue
        bid, ask = prices
        market_id = market["id"]
        write_json(f"{cycle_dir}/ask_{market_id}.json", {
            "market_id": market_id,
            "question": market["question"],
        })
        write_json(f"{cycle_dir}/market_{market_id}.json", {
            "market_id": market_id,
            "question": market["question"],
            "bid": bid,
            "ask": ask,
            "clob_token_ids": market["clobTokenIds"],
        })
        picked += 1
        if picked == MAX_MARKETS:
            break

    if picked == 0:
        print("CYCLE_COMPLETE no market passed the gate")
        return
    print(f"NEEDS_REASONING {cycle_dir} {picked}")


if __name__ == "__main__":
    sys.exit(main())
