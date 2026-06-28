# Experiment 3: Minimal-Raw Arm — Results

**Agent:** `MinimalAgentRaw`
**Seed:** 12345 | **Duration:** 09:30–11:30 (2 hours)
**Model:** `gemma3:4b` via Ollama | **temp=0.1** | **max_tokens=24**

---

## Arm Design

The Minimal-Raw arm is the **true baseline** for Exp 3's prompt ablation. It provides the model with only raw market state — no strategy guidance, no heuristic, no instructed edge.

### Prompt Structure

```text
You are a trader. Maximize profit.
All prices are in cents (e.g. 100000 = $1000.00).
bid=100908 (100) ask=101852 (23) last=101380 mid=101380 pos=+0 cash=10000000
BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD
Reply with ONLY one action line.
```

**What changed vs. V1 (original Minimal):**
- Added `mid=` field as raw information (not guidance)

**What did NOT change:** No strategy heuristic, no "buy below mid" instruction.

---

## Decision Quality — HOLD Classification

The critical diagnostic: distinguishing **deliberate** HOLD from **fallback** HOLD.

| Metric | Count | / Total |
| :--- | :--- | :--- |
| Total wakeup decisions | **119** | — |
| Network / API errors | **0** | 0% |
| Parse failures → fallback HOLD | **0** | 0% |
| Deliberate HOLD (model said HOLD) | **0** | 0% |
| **Active orders submitted** | **7** | ~6% of wakeups |

> [!IMPORTANT]
> **The model never said HOLD.** Zero deliberate HOLDs, zero fallback HOLDs.
> This falsifies the original hypothesis that "the minimal prompt yields near-zero trading because the model can't find edge and defaults to HOLD."

---

## What Actually Happened: Price Discovery Failure

The model was actively trying to trade on almost every wakeup — but its price choices were wrong, causing every order to expire unfilled before the next cancellation cycle.

### Order Analysis

| Property | Value |
| :--- | :--- |
| Orders submitted | **7** (of 119 wakeups) |
| Direction | **100% SELL** (model never once issued BUY) |
| Prices used | $1006.25 and $1009.08 (two values, repeated) |
| Quantity submitted | **1,000 shares** (10× the position limit of 100 shares) |
| Orders filled | **0** |
| Orders cancelled | **7** (all expired at next wakeup) |

> [!WARNING]
> **The model submitted SELL orders for 1,000 shares** — 10× the configured `q_max=10` lot limit (1,000 shares = 10 lots × 100 shares/lot). The position-clamp logic correctly bounds qty to `q_max`, but 1,000 was parsed as the raw integer from the model output — the model appears to be treating quantity as shares directly rather than lots.
>
> **Additionally, the model only ever issued SELL orders** across all 7 active decisions. It found no occasion to BUY, suggesting a systematic bias in how it interprets bare market state.

### Why Orders Never Filled

The market bid/ask during the session hovered around **$1013–$1016**. The model's SELL orders were priced at **$1006.25 and $1009.08** — well *below* the best bid, meaning they were limit sells priced too cheap to be passive and too low to cross the spread as market sells. In a standard continuous double auction, a SELL limit order only fills when a buyer bids ≥ your limit price. The model's prices were in-range but the order quantities (1,000 vs. the small market depth) made them unmatchable.

---

## Financial Performance

| Agent | Strategy | PnL |
| :--- | :--- | :--- |
| HBL_AGENT_5 | HeuristicBeliefLearning | **+$2,038.00** |
| ZI_AGENT_1 | ZeroIntelligence | +$1,251.00 |
| MOMENTUM_AGENT_9 | Momentum | +$4.97 |
| ZI_AGENT_2 | ZeroIntelligence | $0.00 |
| HBL_AGENT_4 | HeuristicBeliefLearning | $0.00 |
| **LLM_MINIMAL_RAW_10** | **MinimalAgentRaw** | **$0.00** |
| HBL_AGENT_6 | HeuristicBeliefLearning | -$283.00 |
| VALUE_AGENT_7 | ValueAgent | -$50.75 |
| VALUE_AGENT_8 | ValueAgent | -$757.16 |
| ZI_AGENT_3 | ZeroIntelligence | -$1,682.00 |

**PnL: $0.00** — Not because the agent was passive, but because all orders were submitted at wrong prices/quantities and never filled.

---

## Market Statistics

| Metric | Value |
| :--- | :--- |
| Mean bid-ask spread | $5.22 |
| Median spread | $2.26 |
| Total trading volume | 670 shares |
| Trade executions | 26 |
| Mean mid-price | $1,003.37 |

---

## Key Finding

> **The Minimal-Raw arm refines the experimental hypothesis.** The failure mode is not behavioral passivity (HOLD) — it is price discovery failure and quantity miscalibration.
>
> The model understands the output format perfectly (0 parse failures). It consistently tries to act (0 HOLDs). But given only bare state and no guidance, it:
> 1. **Always chooses SELL** — a direction bias from bare state with no anchor
> 2. **Chooses prices just below market** — in-range but at wrong prices for fills
> 3. **Submits 1,000 shares** — confusing lot size with share count
>
> This is a richer finding than "the model holds": it shows the model knows **how** to format a trade, but cannot determine **when, at what price, or in what size** to trade from raw state alone.
>
> **The clean Exp 3 claim becomes:** *"Without explicit edge guidance, the model exhibits direction bias, price miscalibration, and quantity confusion — resulting in zero fills despite 119 attempted decisions."*

---

## Comparison Across Minimal Arms (Preview)

| Arm | Orders Placed | Orders Filled | PnL | HOLDs (deliberate) |
| :--- | :--- | :--- | :--- | :--- |
| Minimal-Raw *(this run)* | 7 SELL only | 0 | $0.00 | 0/119 |
| Minimal+Hint (V2) | 112 | 10 | +$3,424.65 | — |

The +$3,424 jump from Raw → Hint is attributable entirely to the one-line heuristic: *"BUY below mid, SELL above mid"* — not to the addition of `mid` as a field.
