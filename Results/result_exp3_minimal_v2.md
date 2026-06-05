# Experiment 3: Minimal Baseline Results (Version 2)

## Overview
This document summarizes the findings from the "Minimal Version 2" arm of Experiment 3. 

The goal of V2 was to solve the zero-activity problem observed in V1. While V1 achieved perfect parse reliability, it generated $0 PnL because it almost always chose `HOLD` or placed passive, unfilled orders. V2 uses the same market setup but applies 4 targeted changes to the `MinimalAgentV2` to encourage active trading:

1. **HOLD Reframing**: The prompt instructs: `"BUY below mid to profit. SELL above mid to profit. HOLD only if no edge."`
2. **Mid-Price Signal**: The computed `mid` price is provided as an anchor.
3. **max_tokens Raised**: Increased from 24 to 32 to prevent parse cutoffs.
4. **Temperature Raised**: Increased from 0.1 to 0.4 to allow more decision exploration.

### Experiment Configuration
- **Market Model:** Continuous Double Auction (CDA)
- **Total Agents:** 10
  - 1 Exchange Agent (Order Book matching)
  - 3 Zero Intelligence (ZIC) Agents (Randomized limit orders)
  - 3 Heuristic Belief Learning Agents (Adaptive ZIP-like learning)
  - 2 Value Agents (Provide liquidity based on fundamental value)
  - 1 Momentum Agent (Trend following)
  - 1 Minimal LLM Agent V2 (Using Ollama / `gemma3:4b`)
- **Duration:** 2 Hours (09:30 - 11:30)

### The Minimal Prompt Structure (V2)
Each time the LLM Agent wakes up (every 60 seconds), it constructs the following prompt using the current market state:

```text
You are a trader. Maximize profit.
All prices are in cents (e.g. 100000 = $1000.00).
bid=100000 (500) ask=100020 (300) last=100010 mid=100010 pos=+2 cash=10000000
BUY below mid to profit. SELL above mid to profit. HOLD only if no edge.
BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD
Reply with ONLY one action line.
```

## Key Metrics & Reliability Analysis

During the 2-hour simulated market session (09:30 - 11:30), the Minimal LLM Agent woke up every 60 seconds, resulting in **119 total queries** to the Ollama server.

- **Network / API Timeouts:** `0 / 119` (0%)
- **Format / Parse Failures:** `0 / 119` (0%)

### Reliability Conclusion
**An incredible success.** Even with the temperature raised to 0.4 and the model strongly incentivized to output `BUY` and `SELL` strings (which require filling out `<price>` and `<qty>`), the parse reliability remained **perfect (100%)**. The LLM never broke the Regex formatting. Raising `max_tokens` to 32 provided exactly the safety margin needed.

## Financial Performance (PnL)

### 1. Final P&L by Entity
Here is how every agent performed over the 2-hour session (values are in dollars):

| Strategy | Agent | Starting Cash | Ending MTM Value | Profit/Loss |
| :--- | :--- | :--- | :--- | :--- |
| **Minimal LLM V2** | LLM_MINIMAL_V2_10 | $100,000.00 | $103,424.65 | **+$3,424.65** |
| **Zero Intelligence** | ZI_AGENT_2 | $100,000.00 | $101,563.00 | **+$1,563.00** |
| **Zero Intelligence** | ZI_AGENT_1 | $100,000.00 | $101,257.62 | **+$1,257.62** |
| **Heuristic Belief** | HBL_AGENT_5 | $100,000.00 | $100,473.00 | **+$473.00** |
| **Heuristic Belief** | HBL_AGENT_4 | $100,000.00 | $100,000.00 | **$0.00** |
| **Heuristic Belief** | HBL_AGENT_6 | $100,000.00 | $100,000.00 | **$0.00** |
| **Value** | VALUE_AGENT_7 | $100,000.00 | $99,920.60 | **-$79.40** |
| **Value** | VALUE_AGENT_8 | $100,000.00 | $99,144.65 | **-$855.35** |
| **Zero Intelligence** | ZI_AGENT_3 | $100,000.00 | $98,500.15 | **-$1,499.85** |
| **Momentum** | MOMENTUM_AGENT_9 | $100,000.00 | $93,773.83 | **-$6,226.17** |

### 2. Trading Activity Comparison
The prompt changes had a massive effect on the agent's willingness to trade:

| Metric | Version 1 | Version 2 |
| :--- | :--- | :--- |
| **Total Wakeups** | 119 | 119 |
| **Orders Placed (Accepted)** | 4 | **112** |
| **Orders Executed (Fills)** | 2 | **10** |
| **Final Profit** | $0.00 | **+$3,424.65** |

### 3. Discussion: Winning the Market
By simply providing the `mid` price and framing `HOLD` as a loss of edge, the agent transformed from a completely passive entity into **the most profitable agent in the entire simulation**. It placed an order on almost every single turn (112 out of 119 wakeups), actively attempting to capture the spread. Its limit orders were matched 10 times, allowing it to accumulate a final net profit of **$3,424.65**, vastly outperforming the traditional Heuristic Belief and Value agents.

## Visualization
The resulting market analysis is available alongside this document at:
`result_exp3_minimal_v2.png`
