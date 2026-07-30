"""Step 3: turn the agent's probabilities into orders.

Reads answer_<id>.json (written by the agent) beside market_<id>.json (written
by prep.py, and never shown to the agent), compares the two, and trades only
where the gap clears EDGE_THRESHOLD.

The comparison lives here rather than in the agent's head on purpose: the
threshold is a rule you can change and re-run, not something a model re-decides
each cycle.
"""
import glob
import json
import os
import sys

from common import DRY_RUN, EDGE_THRESHOLD, STAKE_SHARES, place, read_json


def decide(edge: float, bid: float, ask: float) -> tuple[str, float] | None:
    """Which side to buy and at what price, or None when the gap is too small.

    A binary market has two ways to be long: buy YES, or buy NO — which costs
    1 - (YES bid), since the outcomes always sum to 1. "The market is too high"
    is therefore a NO purchase, not a short.
    """
    if edge > EDGE_THRESHOLD:
        return "YES", ask
    if -edge > EDGE_THRESHOLD:
        return "NO", round(1 - bid, 3)
    return None


def main():
    cycle_dir = sys.argv[1] if len(sys.argv) > 1 else ""
    if not os.path.isdir(cycle_dir):
        sys.exit("usage: finalize.py <cycle_dir>   (the path prep.py printed)")

    placed = skipped = unanswered = 0
    for market_path in sorted(glob.glob(f"{cycle_dir}/market_*.json")):
        market = read_json(market_path)
        answer_path = f"{cycle_dir}/answer_{market['market_id']}.json"
        if not os.path.exists(answer_path):
            unanswered += 1
            continue

        try:
            probability = float(read_json(answer_path)["probability"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            unanswered += 1              # a malformed answer is a skip, never a trade
            continue
        if not 0.0 <= probability <= 1.0:
            unanswered += 1
            continue

        bid, ask = market["bid"], market["ask"]
        edge = probability - (bid + ask) / 2
        print(f"  {market['question'][:60]}")
        print(f"     market {(bid + ask) / 2:.2f}   model {probability:.2f}"
              f"   edge {edge:+.2f}")

        call = decide(edge, bid, ask)
        if call is None:
            print("     -> no edge, skip\n")
            skipped += 1
            continue

        outcome, price = call
        token_id = json.loads(market["clob_token_ids"])[0 if outcome == "YES" else 1]
        result = place(token_id, price)
        ok = result.get("success")
        verb = "would buy" if DRY_RUN else "BUY"
        outcome_note = ("dry run" if DRY_RUN else
                        "placed" if ok else "FAILED: " + str(result.get("errorMsg")))
        print(f"     -> {verb} {outcome} {STAKE_SHARES} @ {price:.3f}  {outcome_note}\n")
        placed += ok is True

    print(f"CYCLE_COMPLETE placed={placed} skipped={skipped} unanswered={unanswered}")


if __name__ == "__main__":
    sys.exit(main())
