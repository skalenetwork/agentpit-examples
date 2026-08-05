# agentpit examples

A reference trading agent for [agentpit](https://agentpit.dev) — a paper-trading
exchange that mirrors real Polymarket order books. Real prices, real books, no
real money.

One agent, packaged as an OpenClaw skill: install it, give it your key, and it
trades on a schedule using the model OpenClaw already has. No second API key,
nothing to `pip install`.

---

## The skill

[`SKILL.md`](SKILL.md) plus [`scripts/`](scripts/) split the loop the way
OpenClaw expects: a deterministic prep step, **your reasoning**, a deterministic
finalize step.

```bash
openclaw skills install git:https://github.com/skalenetwork/agentpit-examples
openclaw config set skills.entries.agentpit-reference.env.AGENTPIT_API_KEY <your-key>
openclaw cron add --every 15m "run the agentpit-reference skill"
```

The key goes in the skill's own config, not `export`: the cron runs inside the
OpenClaw gateway, which does not see your shell's environment.

The reasoning is done by the model OpenClaw already has configured, so there is
no second API key to buy. A scheduler runs it, so it keeps going while you do
something else — as long as the machine stays awake.

---

## What to expect

**Run as-is, this loses money.** That is the honest baseline, and it is
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

**A huge edge is a bug report about yourself.** The first live run of this
bot found a market priced at 0.94 where it estimated 0.15, and happily bought
the other side. A 79-point disagreement with a market that has money on it is
not an opportunity — it means the resolution criteria say something other than
what you assumed, or something happened that you have not seen. `MAX_PLAUSIBLE_EDGE`
skips those. Raise it only once you know why the gap is there.

**Mind the gate, not the model.** Every market that reaches the model costs a
call. Filtering well is worth more than upgrading the model, in both accuracy
and spend.

## Layout

```
SKILL.md                    what the agent is told to do
scripts/common.py           agentpit client + the gate + the knobs
scripts/prep.py             step 1: pick markets, write the questions
scripts/finalize.py         step 3: compare to price, place orders
```

`SKILL.md` sits at the repository root because that is where `openclaw skills
install` looks for it — one repository is one skill, so a second example agent
means a second repository.

## Licence

MIT — fork it, change it, keep it.
