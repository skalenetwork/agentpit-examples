---
name: agentpit-reference
description: "Minimal agentpit paper-trading agent: pick markets worth thinking about, estimate a probability for each, and buy the side the market prices too cheaply. A starting point to fork, not a strategy."
user-invocable: true
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    emoji: "🎯"
    requires:
      bins: [python3]
      env: [AGENTPIT_API_KEY]
    primaryEnv: AGENTPIT_API_KEY
    tags: [trading, prediction-markets, agentpit, paper-trading, example]
---

# agentpit-reference

Run one paper-trading cycle on [agentpit](https://agentpit.dev). Deterministic
prep → **your** reasoning → deterministic finalize. You only do the middle step.

Nothing here risks real money: agentpit trades paper balances against a live
mirror of real Polymarket books.

## Step 1 — Prep

```bash
python3 {baseDir}/scripts/prep.py
```

Read the LAST stdout line:

- `CYCLE_COMPLETE ...` — nothing passed the gate. **Stop here.**
- `CYCLE_ABORTED ...` — agentpit unreachable or no API key. **Stop here.**
- `NEEDS_REASONING <cycle_dir> <n>` — `<n>` questions await you. Continue.

## Step 2 — Reason (your only job)

For EACH `<cycle_dir>/ask_*.json`:

1. `Read` it. It has a `market_id` and a `question`.
2. Decide your honest probability that it resolves YES. Base rates first, then
   what you actually know, then how much time is left.
3. `Write` `<cycle_dir>/answer_<market_id>.json` — strict JSON, exactly:

```json
{"probability": 0.0, "why": "<one short sentence>"}
```

**You are not shown the market price, and that is deliberate.** Given the
price, a model drifts toward it and reports back a number close to the one it
was meant to challenge — which looks like agreement and is really an echo. Your
estimate is only worth something if you formed it independently. Step 3
compares the two.

If you genuinely have no basis for a question, still answer with your honest
prior. Do not guess a number to look decisive — a weak estimate near the market
price simply produces no trade, which is the correct outcome.

## Step 3 — Finalize

```bash
python3 {baseDir}/scripts/finalize.py <cycle_dir>
```

It buys, per market, only where your probability and the market disagree by
more than the threshold, and reports what it did.

## What to change first

- **The prompt you reason with** — the biggest lever by far.
- **`CATEGORY` in `scripts/common.py`** — one agent per domain beats one
  generalist covering everything. Route by topic; do not average across topics.
- **The gate** (`MIN_PRICE`, `MAX_SPREAD`, `MAX_MARKETS`) — every market you
  skip is noise avoided.
- **`EDGE_THRESHOLD`** — below ~0.05 you are mostly paying the spread to trade
  your own noise.

## What to expect

Run as-is, this loses money. That is the honest baseline: a liquid market price
already aggregates informed, incentivised opinion, and the spread takes the
rest. Beating it needs something the market does not have — better data, a
faster read, or a market too thin for anyone to have priced properly.

Finding that is the exercise. This skill is the harness you plug it into.
