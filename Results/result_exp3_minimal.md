# Experiment 3: Minimal Baseline Results

## Overview
This document summarizes the findings from the "Minimal" arm of Experiment 3. 

The goal of the Minimal Agent was to test the absolute baseline reliability and latency of the LLM (`gemma3:4b`) by forcing it to operate with a tiny prompt and a heavily constrained 24-token output. The LLM was not allowed to generate Chain-of-Thought reasoning or use JSON formatting. Instead, it was required to output a strict string matching this Regex structure:
`(BUY|SELL|HOLD)(?:\s+(\d+)\s+(\d+))?`

### Experiment Configuration
- **Market Model:** Continuous Double Auction (CDA)
- **Total Agents:** 10
  - 1 Exchange Agent (Order Book matching)
  - 3 Zero Intelligence (ZIC) Agents (Randomized limit orders)
  - 3 Heuristic Belief Learning Agents (Adaptive ZIP-like learning)
  - 2 Value Agents (Provide liquidity based on fundamental value)
  - 1 Momentum Agent (Trend following)
  - 1 Minimal LLM Agent (Using Ollama / `gemma3:4b`)
- **Duration:** 2 Hours (09:30 - 11:30)

### The Minimal Prompt Structure
Each time the LLM Agent wakes up (every 60 seconds), it constructs the following prompt using the current market state:

```text
You are a trader. Maximize profit.
All prices are in cents (e.g. 100000 = $1000.00).
bid=100000 (500) ask=100020 (300) last=100010  pos=+2 cash=100000
BUY <price_cents> <qty> | SELL <price_cents> <qty> | HOLD
Reply with ONLY one action line.
```

## Key Metrics & Reliability Analysis

During the 2-hour simulated market session (09:30 - 11:30), the Minimal LLM Agent woke up every 60 seconds, resulting in **119 total queries** to the Ollama server.

- **Network / API Timeouts:** `0 / 119` (0%)
- **Format / Parse Failures:** `0 / 119` (0%)

### Reliability Conclusion
The parse reliability was **perfect**. By keeping the prompt terse, fixing `max_tokens=24`, and setting `temperature=0.1`, the LLM adhered exactly to the `BUY <price_cents> <qty>` formatting constraints 100% of the time. There was not a single instance of conversational text breaking the regex parser.

## Financial Performance (PnL)

### 1. Final P&L by Entity
Here is how every agent performed over the 2-hour session (values are in dollars):

| Strategy | Agent | Starting Cash | Ending MTM Value | Profit/Loss |
| :--- | :--- | :--- | :--- | :--- |
| **Heuristic Belief** | HBL_AGENT_5 | $100,000.00 | $102,062.00 | **+$2,062.00** |
| **Value** | VALUE_AGENT_8 | $100,000.00 | $100,343.83 | **+$343.83** |
| **Zero Intelligence** | ZI_AGENT_2 | $100,000.00 | $100,000.00 | **$0.00** |
| **Heuristic Belief** | HBL_AGENT_4 | $100,000.00 | $100,000.00 | **$0.00** |
| **Minimal LLM** | LLM_MINIMAL_10 | $100,000.00 | $100,000.00 | **$0.00** |
| **Momentum** | MOMENTUM_AGENT_9 | $100,000.00 | $99,982.50 | **-$17.50** |
| **Value** | VALUE_AGENT_7 | $100,000.00 | $99,908.44 | **-$91.56** |
| **Heuristic Belief** | HBL_AGENT_6 | $100,000.00 | $99,717.00 | **-$283.00** |
| **Zero Intelligence** | ZI_AGENT_1 | $100,000.00 | $98,999.00 | **-$1,001.00** |
| **Zero Intelligence** | ZI_AGENT_3 | $100,000.00 | $98,296.16 | **-$1,703.84** |

### 2. All Transactions of the Minimal LLM Agent
The LLM Agent woke up 119 times. Most of the time it outputted `HOLD`, but it did successfully place 4 limit orders throughout the session.

Here is its exact transaction log:

1. **10:43:00 AM:** Placed a Limit Order to `SELL` 100 shares at `$1,009.96`. *(Accepted by the exchange, but never filled).*
2. **10:44:00 AM:** Placed a Limit Order to `SELL` 100 shares at `$1,009.96`. *(Accepted, never filled).*
3. **10:45:00 AM:** Placed a Limit Order to `SELL` 100 shares at `$1,009.96`. *(Accepted, never filled).*
4. **11:29:00 AM:** Placed a Limit Order to `SELL` 100 shares at `$1,016.26`. 
   - **EXECUTION!** Immediately upon placing this order, the exchange matched **42 shares** with a willing buyer, and the LLM sold them at $1,016.26.
   - **EXECUTION!** A fraction of a second later, another **7 shares** were matched and sold at $1,016.26.

### 3. Discussion: Short Selling and MTM Value
**Why is its P&L exactly $0.00 if it successfully sold 49 shares?**

When the LLM sold those 49 shares, it did not actually own them yet. In ABIDES (and real-world financial markets), agents are allowed to **Short Sell**. This means they borrow shares and sell them immediately for cash, resulting in a negative inventory position. The LLM's inventory limit (`q_max`) allowed it to hold up to `-10` lots (1,000 shares) short, so selling 49 shares was fully permitted.

At the end of the simulation, the agent held **$149,796.74** in cash, but it was *short* 49 shares of stock (`pos=-49`). 

ABIDES calculates the final "Marked-to-Market" (MTM) value by taking the cash and subtracting the cost to buy back the shorted stock at the `last_trade` price. Because the LLM's sale at `$1,016.26` was the very last trade in the market, its short position was valued at exactly the price it sold them for:

`$149,796.74 cash + (-49 shares * $1016.26)` = **$100,000.00**.

Because $100,000.00 was its starting cash, its net profit was perfectly $0.00. It broke completely even on the trade!

## Visualization
The resulting market analysis (showing the sparse trading volume and the resulting price spread over the two-hour session) is available alongside this document at:
`result_exp3_minimal.png`
