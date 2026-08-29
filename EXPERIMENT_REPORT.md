# Does LLM Reasoning Affect Market Quality? — Design Report

*A plain-language explanation of the experiment, its rationale, and its configuration.*

---

## 1. What we are trying to find out

We place a small local language model (Gemma 3 4B Instruct, served via Ollama) inside ABIDES,
an event-driven simulated stock market with a real limit order book and a population of
traditional trading agents. The question is:

> **After controlling for decision frequency, cancellation behavior, order size, and quote
> aggressiveness, how does an LLM-based trading policy affect the market's liquidity, price
> efficiency, volatility, and ability to recover from shocks?**

Note what the question is *not*: it is not "does the LLM make money?" We judge the agent by
what it does **to the market**, not by its profits.

## 2. Why the question is phrased so carefully — the confound we found

In our pilot experiments we simply swapped one traditional Zero-Intelligence (ZI) trader for
an LLM trader and watched what changed. Things did change — volume, spread, the price path.
But the swap changed **many things at once**:

- the decision policy (reasoning instead of random draws),
- the wake-up schedule (the LLM acted every 60 seconds),
- cancellation behavior (it cancelled and replaced its orders every cycle),
- how aggressively it quoted, how large its orders were,
- how often it acted at all (it almost never chose to hold).

So when the market changed, we could not say *why*. A completely mindless agent that wakes
every 60 seconds and churns its orders would also move spreads and volume — no intelligence
required. The pilot result was **descriptive** ("this happened") but could not support a
**causal** claim ("the reasoning caused it"). Identifying this confound was the main lesson
of the pilot phase, and fixing it is the point of the new design.

## 3. The fix: make the mechanics identical, vary only the mind

The solution has two parts.

**Part 1 — a fixed wrapper.** We build one agent "body" whose mechanics are hard-coded and
identical no matter which brain drives it:

- wakes at a fixed interval (60 s or 300 s), no exceptions;
- on every wake-up: cancels all its resting orders, then submits exactly one limit order;
- order size is fixed (one standard lot) — the policy cannot choose it;
- order price follows a fixed placement rule (e.g., join the current best quote) — the
  policy cannot choose it;
- there is no "hold" option — every wake-up produces an order, so participation is 100%.

The only decision left to the brain is: **buy or sell?**

**Part 2 — two brains.**

- **LLM policy:** reads a snapshot of the market (best quotes, recent trades, its own
  inventory, a short frozen history) and chooses the side by reasoning.
- **Coin policy (the stochastic control):** flips a fair coin. It sees nothing.

Because the body is identical, every mechanical factor is equal between the two arms *by
construction* — not approximately, not statistically matched, but bit-for-bit the same
number of wake-ups, cancellations, orders, sizes, and the same placement rule. The single
remaining difference is whether the side choice is conditioned on the state of the market.
If the two arms produce different markets, reasoning is the only available explanation.

**Why a coin, and not something smarter?** Because the coin is the perfect "zero" on the
intelligence axis. It is a zero-intelligence decision rule in the classic Gode & Sunder
sense — but wearing the LLM's exact mechanical footprint, which the canonical ZI agent does
not. That's why we call it an *activity-matched stochastic control* rather than "a ZI."

**A deliberate scope decision:** by fixing size and price placement, we give up studying
whether the LLM sizes or times its aggressiveness intelligently. For this paper that is the
right trade — it is exactly what makes "controlling for order size and quote aggressiveness"
literally true, and it keeps the estimand clean: the effect of *directional, state-contingent
decision-making*. Sizing/aggressiveness policies are future work.

## 4. The five conditions

| # | Condition | Wake interval | Decision rule |
|---|-----------|---------------|---------------|
| C1 | ZI-canonical baseline | native ZI arrival | classic ABIDES ZI agent, untouched |
| C2 | Coin control | 60 s | fair coin |
| C3 | LLM | 60 s | Gemma 3 4B |
| C4 | Coin control | 300 s | fair coin |
| C5 | LLM | 300 s | Gemma 3 4B |

Each condition occupies the same single "treatment slot" in an otherwise identical market of
background agents.

**Why keep C1 if C2 is the real comparison?** Because the two answer different questions,
and together they give a decomposition:

```
C3 − C1  =  total effect of putting the LLM agent into a normal market
C2 − C1  =  the "footprint" part (frequent wake-ups, churn — no thinking needed)
C3 − C2  =  the "policy" part  (the reasoning itself)          ← the headline claim
```

C1 tells us what an ordinary market looks like; C2 tells us what the LLM's footprint alone
would do to it; C3 − C2 tells us what the reasoning adds on top. The pilot could only
measure the first line; the new design measures all three.

**Why two wake intervals (60 s and 300 s)?** To see whether the value of reasoning depends
on how often the agent acts. If the LLM-vs-coin gap differs between 60 s and 300 s, the
policy effect interacts with participation frequency — something a single frequency could
never reveal.

## 5. The two market regimes

Every condition runs in two environments:

**Normal regime.** A calm, mean-reverting fundamental value. This measures everyday market
quality: spreads, depth, volatility, how closely prices track fundamental value. But it is
an easy environment — prices are usually near fundamental, so reasoning has little to
exploit, and the LLM could look identical to the coin here simply for lack of opportunity.

**Shock regime.** At a fixed mid-session time, the fundamental value jumps by a
standardized amount. This creates a large, known, temporary mispricing — a situation with a
*correct answer* (buy if value jumped up). A coin cannot find that answer; a reasoning agent
in principle can. This is the high-power test: if the LLM's reasoning has any content, its
order flow should be corrective, speeding recovery and reducing overshoot relative to the
coin. It is also where dangerous failure modes (chasing, amplifying the move) would appear.

Crossing regime with condition gives the most informative quantity in the design: does the
reasoning effect **grow** when there is actually something to reason about?

## 6. How runs are made comparable: paired seeds

Simulated markets are noisy — two runs with different random seeds differ a lot even with
identical agents. So we pair: for each random seed, all five conditions run on the **same
fundamental path and the same background-agent randomness**. Differences are computed
*within* a seed (e.g., C3's spread minus C2's spread on seed 2041) and then averaged across
many independent seeds, with confidence intervals. Seed-level noise cancels instead of
masquerading as an effect. The pilot's other weakness — conclusions resting on a single
seed — is fixed by running N independent seed-pairs (target ≈ 30, confirmed by a variance
check on pilot seeds).

## 7. What we measure

**Primary outcomes (market quality):**
1. **Price efficiency** — time-weighted gap between the market midpoint and the true
   fundamental value.
2. **Liquidity** — time-weighted quoted spread and depth at the best quotes.
3. **Shock resilience** — time for the price to reach and hold near the *new* fundamental
   after the shock; plus overshoot.

**Secondary:** volatility, book availability, trade counts, volume, submissions,
cancellations, fill rate, inventory, turnover, PnL (secondary on purpose), invalid-action
rate, token usage, latency.

**A useful diagnostic:** how often is the LLM's chosen side "fundamental-correcting" (buying
below value, selling above)? The coin sits at 50% by definition; any reliable deviation is
direct evidence the model reads the state.

## 8. Guardrails that make the result trustworthy

- **Everything frozen before the final run:** model version, prompt, memory design,
  placement rule, shock spec, metric definitions. Pilot seeds used for validation are
  discarded from the analysis.
- **Mechanics-identity audit:** an automated check asserting that the coin arm and the LLM
  arm produced the *same* number of wake-ups, submissions, cancellations, and sizes on every
  pilot seed. In this design matching is guaranteed by construction; the audit proves the
  code implements the design.
- **Invalid LLM outputs** (unparseable responses) fall back to a coin flip and are logged —
  so participation stays at 100% in both arms and a flaky model cannot silently break the
  matching. The invalid rate is reported as a model-quality statistic.
- **One model call per wake-up, no retries,** so decision latency cannot become
  state-dependent through the back door.

## 9. How to read the eventual results

| Outcome pattern | Interpretation |
|---|---|
| C3 ≈ C2 in both regimes | The LLM's apparent market impact is entirely its mechanical footprint; the reasoning adds nothing detectable. (A real, publishable finding.) |
| C3 ≈ C2 normal, C3 ≠ C2 shock | Reasoning matters only when there is a mispricing to exploit — its value is state-contingent. |
| C3 ≠ C2 in both | The language policy shapes market quality even in calm conditions; direction of each metric tells us whether it helps or harms. |
| C2 ≠ C1 large | Much of "the LLM effect" people would naively report is really just an active, churning agent — a caution for how LLM trading agents are evaluated. |

## 10. One-paragraph summary

We ask whether an LLM's *reasoning* — as opposed to its mere activity — changes the quality
of a simulated market. We strip the agent down so that its schedule, order size, pricing,
and cancellations are hard-coded and identical across arms, leaving it exactly one choice:
buy or sell. One arm makes that choice with a language model reading the market; the other
flips a coin. Both run on identical random worlds, in calm markets and through standardized
value shocks, across many paired seeds. Whatever difference survives — in spreads, price
accuracy, volatility, or recovery speed — is attributable to the reasoning and nothing else;
and if nothing survives, that too is an answer.
