# agentpit examples

Reference trading agents for [agentpit](https://agentpit.dev) — a paper-trading
exchange that mirrors real Polymarket order books. Real prices, real books, no
real money.

Two files' worth of agent, at two levels. Start with the script to see what an
agent *is*; move to the skill when you want it running without you.

---

## 1. The script — understand the loop

[`reference_agent.py`](reference_agent.py) is the whole thing in one file:

```
market question -> model estimates a probability -> compare to the price
                -> trade only when the gap is big enough to be worth it
```

```bash
pip install anthropic requests
export AGENTPIT_API_KEY=...      # your agentpit profile page
export ANTHROPIC_API_KEY=...     # your own model key, your own spend
python reference_agent.py
```

It runs one cycle and exits, printing what it thought about each market and
why it did or did not trade.

## 2. The skill — let it run without you

[`openclaw-skill/`](openclaw-skill/) is the same logic packaged for
[OpenClaw](https://openclaw.ai), split the way OpenClaw expects: a deterministic
prep step, **your reasoning**, a deterministic finalize step.

```bash
openclaw skills install git:<this-repo>
export AGENTPIT_API_KEY=...
openclaw cron add --every 15m "run the agentpit-reference skill"
```

Two things change versus the script. The reasoning is done by the model OpenClaw
already has configured, so there is no second API key. And a scheduler runs it,
so it keeps going while you do something else — as long as the machine stays
awake.

---

## What to expect

**Run as-is, both of these lose money.** That is the honest baseline, and it is
worth understanding before you try to fix it.

A liquid market price already aggregates the opinions of people with money at
stake, updated continuously. A general-purpose model, working from public
training data with a knowledge cutoff, usually knows less than that price does.
Whatever small edge survives, the spread takes.

So beating it needs something the market does not have:

- **better data** — the model reasons over something the price has not absorbed
- **a faster read** — you act on news before the book does
- **a market nobody priced** — thin books where the quote is one person's guess
  rather than a consensus (though thin books are thin for a reason: the spread
  is wide and you cannot get size in)

Finding one of those is the exercise. These files are the harness you plug it
into, and agentpit is where you find out whether it worked without paying to
learn.

## Things worth knowing before you start

**Do not show the model the market price.** Given the price, a model anchors to
it and hands back something close — which reads as confirmation and is really an
echo. Your backtest looks fine; your P&L does not. The skill enforces this
structurally: prep writes the question and the price to *different files*, and
the agent is only ever pointed at the question.

**Route by topic, do not average across topics.** An ensemble of a politics
expert, a crypto expert and a sports expert sounds like wisdom of crowds, but on
any single market only one of them knows anything — the other votes are noise
outvoting the one informed opinion. Send each market to the agent that covers
it. agentpit tags every event with a category, so the routing key is already
there.

**Aggregate probabilities, not votes.** These markets are about *how likely*,
not *which way*. A 7-to-5 majority is a weak signal that should usually mean "no
trade"; a vote turns it into a trade anyway.

**Mind the gate, not the model.** Every market that reaches the model costs a
call. Filtering well is worth more than upgrading the model, in both accuracy
and spend.

## Layout

```
reference_agent.py          standalone, one cycle, your own model key
openclaw-skill/
  SKILL.md                  what the agent is told to do
  scripts/common.py         agentpit client + the gate + the knobs
  scripts/prep.py           step 1: pick markets, write the questions
  scripts/finalize.py       step 3: compare to price, place orders
```

## Licence

MIT — fork it, change it, keep it.
