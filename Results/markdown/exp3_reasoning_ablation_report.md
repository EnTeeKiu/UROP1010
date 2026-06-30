# Experiment 3: Prompt-Level Reasoning Ablation

## 1. Purpose

This experiment investigates how the *structure and depth of chain-of-thought (CoT) scaffolding* in an LLM's prompt affects its trading performance in a simulated continuous double-auction market (ABIDES). The core hypothesis is that a small (4B-parameter) language model can extract better decisions from identical market state when its prompt systematically guides its reasoning process.

We ablate the prompt across four arms, each adding exactly one variable to the previous:

| Arm | Scaffold | Variable Isolated |
|:---|:---|:---|
| **Minimal-Raw** | None (bare state + action grammar) | Baseline: can the model trade at all? |
| **R1 â€” Open CoT** | "Think step by step" (free-form) | Does *any* reasoning help? |
| **R2 â€” Structured CoT** | `[EXPOSURE]` / `[EDGE]` / `[DECISION]` | Does *guided structure* outperform free-form? |
| **R3 â€” Evidence-Grounding** | R2 + `[VERIFY]` ("cite the number") | Does *citing state evidence* improve quality? |

All non-prompt parameters are **frozen** across arms: model (`gemma3:4b`), temperature (0.1), market population (3 ZI, 3 HBL, 2 Value, 1 Momentum), seed (12345), wakeup frequency (60s), position limit (10 lots), and action grammar.

---

## 2. Experimental Setup

### 2.1 Market Environment
- **Simulator:** ABIDES (Agent-Based Interactive Discrete Event Simulation)
- **Asset:** JPM (synthetic), fundamental value mean-reverting around $1,000
- **Session:** 2 hours (09:30â€“11:30), seed 12345
- **Background agents:** 3 Zero-Intelligence, 3 Heuristic Belief Learning, 2 Value, 1 Momentum (9 total)
- **LLM agent:** 1 per arm (agent ID 10)

### 2.2 LLM Configuration
- **Model:** `gemma3:4b` via local Ollama
- **Temperature:** 0.1
- **Max tokens:** 24 (Minimal-Raw) / 256 (R1, R2, R3)
- **Wakeup cycle:** Every 60 seconds â†’ 119 decision points per session
- **Action grammar:** `BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD`

### 2.3 Prompt Designs

All four prompts share an identical **state block** and **action grammar**. Only the **scaffold** (middle section) differs.

**Shared state block (frozen):**
```
You are a trader. Maximize profit.
All prices are in cents (e.g. 100000 = $1000.00).
bid={bid} ({bid_sz}) ask={ask} ({ask_sz}) last={last} mid={mid} pos={pos} cash={cash}
```

**Shared action grammar (frozen):**
```
Put your final answer on the LAST LINE ONLY, exactly as:
BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD
```

**Scaffolds:**

- **Minimal-Raw:** No scaffold. Only the state block and action grammar.
- **R1:** `Think step by step before acting. Keep it brief (2-3 sentences).`
- **R2:**
  ```
  Think step by step before acting (one sentence each):
    [EXPOSURE]  How large is my position? Am I over-concentrated on one side?
    [EDGE]      Is there profit available? (buying below mid or selling above mid)
    [DECISION]  Weigh exposure against edge, then choose.
  ```
- **R3:**
  ```
  Think step by step (one sentence each):
    [EXPOSURE]   How large is my position? Am I over-concentrated on one side?
    [EDGE]       Is there profit available? (buying below mid or selling above mid)
    [VERIFY]     What specific number in the state confirms the direction and price I am considering?
    [DECISION]   Weigh all three, then choose.
  ```

### 2.4 Metrics

| Category | Metrics |
|:---|:---|
| **Format compliance** | Parse failures, HOLD (deliberate vs. fallback) |
| **Token usage** | Tokens out (median, mean), truncation count |
| **Reasoning coherence** | Binding rate (does conclusion match action?), conclusion source (tag vs. fallback) |
| **Financial** | PnL (mark-to-market), rank among all 10 agents |
| **Market impact** | Spread (mean, median), volume, mid-price std |

---

## 3. Results

### 3.1 Full Population P&L â€” Minimal-Raw

| Agent | Strategy | PnL ($) |
|:---|:---|---:|
| HBL_AGENT_5 | Heuristic Belief Learning | +2,038.00 |
| ZI_AGENT_1 | Zero Intelligence | +1,251.00 |
| MOMENTUM_AGENT_9 | Momentum | +4.97 |
| ZI_AGENT_2 | Zero Intelligence | 0.00 |
| HBL_AGENT_4 | Heuristic Belief Learning | 0.00 |
| **LLM_MINIMAL_RAW_10** | **MinimalAgentRaw** | **0.00** |
| HBL_AGENT_6 | Heuristic Belief Learning | -283.00 |
| VALUE_AGENT_7 | Value Agent | -50.75 |
| VALUE_AGENT_8 | Value Agent | -757.16 |
| ZI_AGENT_3 | Zero Intelligence | -1,682.00 |

> **LLM Rank: 6th of 10 (tied 4thâ€“6th at $0.00)**
> Zero PnL because all 7 submitted orders were mispriced and never filled.

---

### 3.2 Full Population P&L â€” Reasoning R1 (Open CoT)

| Agent | Strategy | PnL ($) |
|:---|:---|---:|
| ZI_AGENT_3 | Zero Intelligence | +5,776.10 |
| HBL_AGENT_5 | Heuristic Belief Learning | +1,611.96 |
| ZI_AGENT_1 | Zero Intelligence | +119.48 |
| ZI_AGENT_2 | Zero Intelligence | 0.00 |
| HBL_AGENT_6 | Heuristic Belief Learning | 0.00 |
| VALUE_AGENT_7 | Value Agent | -145.18 |
| HBL_AGENT_4 | Heuristic Belief Learning | -1,144.41 |
| VALUE_AGENT_8 | Value Agent | -1,382.96 |
| MOMENTUM_AGENT_9 | Momentum | -2,321.48 |
| **LLM_REASONING_R1_10** | **ReasoningAgentR1** | **-5,362.67** |

> **LLM Rank: 10th of 10 (dead last)**
> The LLM accumulated a massive short position (-214 shares) by aggressively selling near the session's price trough, then held the short as the fundamental rebounded. The loss is directional (adverse inventory), not from paying the spread.

---

### 3.3 Full Population P&L â€” Reasoning R2 (Structured CoT)

| Agent | Strategy | PnL ($) |
|:---|:---|---:|
| HBL_AGENT_5 | Heuristic Belief Learning | +3,000.86 |
| **LLM_REASONING_R2_10** | **ReasoningAgentR2** | **+148.05** |
| MOMENTUM_AGENT_9 | Momentum | +173.88 |
| ZI_AGENT_2 | Zero Intelligence | 0.00 |
| HBL_AGENT_4 | Heuristic Belief Learning | 0.00 |
| ZI_AGENT_1 | Zero Intelligence | -10.85 |
| HBL_AGENT_6 | Heuristic Belief Learning | -229.00 |
| VALUE_AGENT_7 | Value Agent | -233.87 |
| VALUE_AGENT_8 | Value Agent | -753.80 |
| ZI_AGENT_3 | Zero Intelligence | -1,696.56 |

> **LLM Rank: 3rd of 10**
> The structured scaffold completely eliminated parse failures and pushed the LLM into profitable territory.

---

### 3.4 Full Population P&L â€” Reasoning R3 (Evidence-Grounding)

| Agent | Strategy | PnL ($) |
|:---|:---|---:|
| HBL_AGENT_5 | Heuristic Belief Learning | +2,320.20 |
| **LLM_REASONING_R3_10** | **ReasoningAgentR3** | **+793.92** |
| HBL_AGENT_6 | Heuristic Belief Learning | +471.00 |
| MOMENTUM_AGENT_9 | Momentum | +38.29 |
| ZI_AGENT_2 | Zero Intelligence | 0.00 |
| HBL_AGENT_4 | Heuristic Belief Learning | 0.00 |
| ZI_AGENT_1 | Zero Intelligence | -10.85 |
| VALUE_AGENT_7 | Value Agent | -385.63 |
| VALUE_AGENT_8 | Value Agent | -1,212.90 |
| ZI_AGENT_3 | Zero Intelligence | -1,585.29 |

> **LLM Rank: 2nd of 10**
> Citing state evidence produced the strongest LLM performance, trailing only the best HBL agent.

---

### 3.5 Full Population P&L â€” Structured JSON (R3 equivalent)

| Agent | Strategy | PnL ($) |
|:---|:---|---:|
| ZI_AGENT_1 | Zero Intelligence | +3,247.44 |
| ZI_AGENT_3 | Zero Intelligence | +1,894.16 |
| ZI_AGENT_2 | Zero Intelligence | +1,537.26 |
| HBL_AGENT_5 | Heuristic Belief Learning | 0.00 |
| HBL_AGENT_6 | Heuristic Belief Learning | 0.00 |
| HBL_AGENT_4 | Heuristic Belief Learning | -489.57 |
| VALUE_AGENT_7 | Value Agent | -514.71 |
| VALUE_AGENT_8 | Value Agent | -752.12 |
| **LLM_STRUCTURED_JSON_10** | **StructuredJsonAgent** | **-889.34** |
| MOMENTUM_AGENT_9 | Momentum | -8,733.83 |

> **LLM Rank: 9th of 10**
> The model successfully parsed 100% of its outputs (0 parse failures), but suffered a severe reasoning degradation, producing a massive PnL drop compared to its plain-text R3 counterpart (+$793).

---

### 3.6 Cross-Arm Comparison â€” LLM Agent Only

| Metric | Minimal-Raw | R1 (Open CoT) | R2 (Structured) | R3 (Evidence) | JSON (R3 Envelope) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Scaffold** | None | Free-form | 3-tag | 4-tag (+Verify) | JSON Schema |
| **Parse Failures** | 0 / 119 | 19 / 119 | 0 / 119 | 0 / 119 | 0 / 119 |
| **Tokens (Median)** | ~5 | 62 | 88 | 122 | 103 |
| **VERIFY Citation Rate**| N/A | N/A | N/A | 119 / 119 (100%) | 2 / 119 (1.7%) |
| **PnL** | **$0.00** | **-$5,362.67** | **+$148.05** | **+$793.92** | **-$889.34** |
| **Rank (of 10)** | 6th | 10th | 3rd | 2nd | 9th |

### 3.7 Cross-Arm Comparison â€” Market-Level Statistics

| Metric | Minimal-Raw | R1 (Open CoT) | R2 (Structured) | R3 (Evidence) |
|:---|:---:|:---:|:---:|:---:|
| Mean spread | $5.22 | $7.63 | $6.44 | $3.32 |
| Median spread | $2.26 | $2.07 | $2.26 | $1.86 |
| Spread std | â€” | $11.83 | $7.56 | $6.14 |
| Total volume | 670 | 1,080 | 726 | 796 |
| Executions | 26 | 62 | 34 | 42 |
| Mean mid-price | $1,003.37 | $1,001.79 | $1,004.33 | $1,004.41 |
| Mid-price std | â€” | $9.51 | $8.73 | $8.44 |

---

## 4. Analysis

### 4.1 Format Compliance: Structure Prevents Grammar Dropping

The most immediate finding is that **unstructured CoT degrades output compliance**. R1's bare "think step by step" instruction introduced 19/119 parse failures â€” the model's free-form reasoning bleeds into its action line, producing unparseable outputs. This is a 16% failure rate on a task the Minimal-Raw arm achieved 0% failure on.

Both R2 and R3 restore perfect compliance (0/119). The mechanism: by forcing reasoning into explicit `[TAG]` sections, the structured scaffold creates a clean boundary between the thinking and the action. The model consistently places `BUY/SELL/HOLD` on its final line when it has a `[DECISION]` tag to "close" its reasoning.

### 4.2 From Passivity to Hyperactivity: The HOLD Puzzle

Across all four arms, **deliberate HOLD count is exactly zero**. The `gemma3:4b` model, when successfully parsing its output, always chooses to trade. This finding is robust across prompt designs and eliminates the hypothesis that reasoning scaffolds would induce the model to "think twice and stay out."

The difference between arms is not in deliberate holding but in *fallback* holding:
- Minimal-Raw: 112/119 fallback HOLDs (the model outputs garbage formats that don't parse as trades)
- R1: 19/119 fallback HOLDs (from parse failures)
- R2/R3: 0/119 (every output is a valid trade)

### 4.3 Binding Rate: Structured Reasoning is Coherent

The binding-rate metric measures whether the model's stated reasoning conclusion matches its final action. For R1 (last-sentence extraction), the rate is 92% â€” high but imperfect, partly because the unstructured text makes extraction noisier. For R2 and R3 (tag-based extraction), binding is 100%. This indicates that when the model uses structured tags, its reasoning process and final action are perfectly coherent â€” it is not generating reasoning in one direction and acting in another.

### 4.4 Financial Performance: Evidence-Grounding is the Key Lever

The PnL trajectory across arms tells a clear story:

```
Minimal-Raw ($0.00)  â†’  R1 (-$5,363)  â†’  R2 (+$148)  â†’  R3 (+$794)
```

- **Raw â†’ R1 (regression):** Adding unstructured reasoning *without* structure made the model *worse*. It traded more aggressively but with degraded price calibration, accumulating a massive losing position.
- **R1 â†’ R2 (+$5,511 improvement):** Structure restored compliance and produced marginally profitable trading. The tags did not change *what* the model knows â€” they changed how reliably it *applies* what it knows.
- **R2 â†’ R3 (+$646 improvement):** The `[VERIFY]` step â€” "cite the specific number that confirms your direction and price" â€” produced a further 5Ã— PnL improvement over R2. Forcing the model to ground its decision in an actual state value appears to reduce hallucinated entries and improve price targeting.

### 4.5 Market Impact

R3 produced the tightest spreads (mean $3.32, median $1.86) of any arm, suggesting the LLM's better-calibrated orders contribute constructively to price discovery rather than widening the book. R1 produced the widest spreads ($7.63 mean), consistent with its aggressive mispriced orders destabilizing the book.

### 4.6 Negative Spread Investigation

Two instances of apparent negative spread were identified in the R1 run (at 10:25:46 and 10:30:59). Investigation of the raw exchange log confirmed these are **computation artifacts** from a one-sided book, not genuine crossed markets. When a large buy order consumed all available asks, no `BEST_ASK` event was emitted, causing the forward-fill logic to carry a stale ask price against a new higher bid. This artifact affects the spread panel visualization but does not contaminate PnL or order execution data.

---

## 5. Limitations

1. **Single seed.** All results are from seed 12345. The direction and magnitude of effects must be confirmed across â‰¥10 seeds before publication. The PnL ranking could be path-specific.
2. **No deliberate HOLD baseline.** Because the model never voluntarily holds, we cannot compare "choosing to hold" across arms. This is itself a finding (the model treats every wakeup as a mandate to act), but it limits our ability to measure reasoning-induced restraint.
3. **Token budget is not a confound (verified).** The 256-token cap was never reached in any arm (max median: 122 in R3). The `TOKENS_TRUNCATED` column is 0/119 across all three reasoning arms.
4. **Market population is small.** 10 agents total. Results may differ with denser or more adversarial markets.

---

## 6. Conclusions

1. **Unstructured CoT is harmful for small models.** For a 4B-parameter model, "think step by step" without structural guidance *degrades* output compliance (16% parse failure rate) and *worsens* financial performance (last place among all agents). The free-form reasoning bleeds into the action grammar.

2. **Structured tags are necessary and sufficient for compliance.** The `[TAG]` scaffold (R2) restores 100% parse success, 100% binding coherence, and moves the model from catastrophic loss to marginal profit. Structure does not add information â€” it organizes the model's existing knowledge into a format that preserves action-grammar integrity.

3. **Evidence-grounding is the primary lever for decision quality.** Adding `[VERIFY]` â€” a single instruction to cite the specific state number supporting the chosen direction â€” produced a 5Ã— PnL improvement over R2. This suggests that small models benefit most not from *more thinking* but from *anchored thinking*: being forced to ground decisions in concrete data rather than plausible-sounding generalities.

4. **JSON Enforcement Degrades Reasoning (The Tam et al. Effect).** When the exact same reasoning logic as R3 was placed inside a strict JSON object envelope, parse reliability remained perfect (0/119 failures), but **reasoning quality collapsed**. The JSON agent cited state variables in its `verify` string only 1.7% of the time (2/119), compared to plain text R3. Consequently, the JSON agent's PnL fell to -$889 (9th place), corroborating the hypothesis that forcing a small LLM to generate complex syntactic envelopes (JSON keys, quotes, brackets) consumes the cognitive overhead otherwise used for logical reasoning and state-variable grounding.

5. **The "always trade" bias is deep and scaffold-invariant.** No prompt design in this experiment induced the model to voluntarily hold. This finding constrains the design space for Exp 4 (memory ablation): any memory-based improvement will manifest as *better trades*, not *fewer trades*, unless an explicit hold-inducing mechanism is added.

