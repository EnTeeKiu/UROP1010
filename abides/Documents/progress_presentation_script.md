# Progress Presentation Script

Suggested total length: 8-10 minutes.

Roles:
- Speaker A: Tu, responsible for introduction, Experiment 1, Experiment 4, and closing.
- Speaker B: Friend, responsible for Experiment 2 and Experiment 3 details.

## Slide 1: Title And Research Question

**Speaker A**

Good morning Professor. Today we will present our current progress on the project: *Heterogeneous LLM-Based Trading Agents in Continuous Double-Auction Markets*.

The main research question is: can a small, locally hosted open-source LLM act as a useful trading agent in a continuous double-auction market, and how do design choices like prompt structure and memory affect its behavior?

The important constraint is that we are not using a large commercial API model. We are using Gemma 3 4B Instruct locally through Ollama, with an OpenAI-compatible endpoint. This is important because it keeps cost low, avoids uncontrolled API latency, and lets us later study latency as an experimental variable instead of as a hidden confound.

We use ABIDES as the market simulator. The reason is that ABIDES gives us a realistic discrete-event, message-passing market with an exchange agent, configurable latency, dynamic fundamental value, and adaptive benchmark agents such as Heuristic Belief Learning agents. This makes it more suitable than a simpler simulator like BSE for our later experiments on latency and communication.

So far, we completed Experiments 1 to 4 as single-seed or diagnostic runs. The results are preliminary, but they already show a clear progression: first we validated the market, then we inserted a naive LLM trader, then we tested prompt design, and finally we tested memory design.

## Slide 2: Experimental Setup

**Speaker A**

Across the completed experiments, the setting is intentionally controlled. We run a two-hour ABIDES trading session, from 9:30 to 11:30, using seed 12345. The asset is JPM in a synthetic market where the fundamental value is mean-reverting around 1000 dollars.

The baseline market contains 10 traditional agents: four zero-intelligence agents, three HBL agents, two value agents, and one momentum agent. In the LLM experiments, we replace one traditional agent with one LLM trader, while keeping the other nine background agents fixed as much as possible.

We evaluate three main things. First is market quality, especially bid-ask spread and trading volume. Second is price discovery, meaning how the mid-price tracks the ABIDES fundamental value. Third is the LLM trader's mark-to-market profit and loss, because we want to know whether the LLM is actually competitive or simply increasing activity.

## Slide 3: Experiment 1, Traditional Baseline

**Speaker A**

Experiment 1 is the foundation. Before judging the LLM, we needed to confirm that our ABIDES setup works correctly on its own.

In this experiment, there is no LLM trader. The market contains only the 10 traditional agents: ZI, HBL, value, and momentum agents. The goal was to check whether the simulator, matching engine, logging pipeline, and analysis scripts were all functioning correctly.

The result was positive. The two-hour session ran successfully and produced a stable continuous double-auction market. The mean spread was 3.30 dollars, the median spread was 1.71 dollars, total volume was 1,062 shares, and there were 30 executions.

The price behavior was also reasonable. The mean mid-price was 1,002.62 dollars, close to the 1,000 dollar fundamental value, with a mid-price standard deviation of 6.44 dollars. The mid-price did not perfectly track the fundamental value at every moment, but it moved around it without extreme instability.

The PnL distribution also matched our expectation. HBL agents earned the largest aggregate profit, about 2,587 dollars in total, while zero-intelligence agents lost about 2,582 dollars in total. This is important because HBL agents are adaptive and order-book-aware, while ZI agents trade more randomly. So Experiment 1 confirms that the market dynamics are sensible and that the traditional benchmark agents behave as expected.

The takeaway from Experiment 1 is simple: the baseline market is stable enough to support the LLM experiments.

## Transition To Experiment 2

**Speaker A**

After we had a working traditional market, the next step was to insert one LLM trader into the same environment. I will hand over to Speaker B to explain what happened in Experiment 2.

## Slide 4: Experiment 2, Naive LLM Trader

**Speaker B**

Experiment 2 tested the most basic LLM-inclusive market. We replaced one zero-intelligence trader with a Gemma 3 4B LLM trading agent. The LLM woke up every 60 simulated seconds, read the current market state, and returned a strict JSON decision: buy, sell, or hold, with price and quantity.

The purpose was not yet to make the LLM smart. The purpose was to prove that the engineering pipeline works: ABIDES can send market state to a local LLM, receive a parsed decision, and place orders into the exchange.

Technically, this worked. The run completed successfully with 120 sequential LLM inferences and no memory crash. But behaviorally, the naive LLM was very disruptive.

Compared with Experiment 1, the mean spread increased from 3.30 dollars to 8.15 dollars. Total volume increased from 1,062 shares to 2,716 shares, and executions increased from 30 to 86. Mid-price volatility also increased: the standard deviation rose from 6.44 dollars to 11.71 dollars.

The most striking result is the LLM's PnL. The LLM trader lost 16,106.42 dollars. Meanwhile, the HBL agents made strong positive profits. This suggests that the adaptive background agents were able to exploit the LLM's poor order placement.

So the conclusion from Experiment 2 is that the local LLM integration works, but a naive prompt produces an unstable and unprofitable trader. This motivated Experiment 3, where we tested whether prompt structure could improve the same model's behavior.

## Slide 5: Experiment 3, Prompt-Level Reasoning Ablation

**Speaker B**

Experiment 3 asks whether better prompt scaffolding can improve the LLM trader while holding the model, seed, market, wakeup frequency, and action grammar fixed.

We tested five prompt arms. The first was Minimal-Raw, which gave only the state and action grammar. The second was R1, which added open-ended chain-of-thought with the instruction to think step by step. The third was R2, which used structured reasoning tags: exposure, edge, and decision. The fourth was R3, which added an explicit verify step, requiring the model to cite a concrete number from the market state. The final arm used a strict JSON envelope around an R3-like reasoning structure.

The results show that not all reasoning helps. Minimal-Raw had no parse failures but effectively did not trade successfully, ending with 0 dollars PnL. R1, the open-ended chain-of-thought prompt, was the worst: it created 19 parse failures out of 119 decisions and the LLM lost 5,362.67 dollars, ranking last among the 10 agents.

When we moved to structured reasoning, performance improved. R2 had zero parse failures and produced positive PnL of 148.05 dollars, ranking third. R3, with the verify step, performed best among the prompt-only variants: it earned 793.92 dollars and ranked second among the 10 agents.

The key lesson is that the small model benefits from grounded structure, not from unconstrained extra reasoning. The verify step seems especially useful because it forces the model to anchor its action to a specific market number.

The JSON-envelope variant is also informative. It had perfect parse compliance, but decision quality dropped, and PnL fell to negative 889.34 dollars. So strict JSON formatting helped syntax but appeared to consume reasoning capacity or reduce evidence grounding in the small model.

Overall, Experiment 3 tells us that prompt design can turn the same local LLM from a poor trader into a somewhat competitive one, but only when the prompt is structured and evidence-grounded.

## Transition To Experiment 4

**Speaker B**

After Experiment 3, we knew that prompt structure matters. But prompt structure is only one design dimension. I will hand back to Speaker A to explain Experiment 4, where we isolated memory design.

## Slide 6: Experiment 4, Memory Ablation

**Speaker A**

Experiment 4 focuses on memory. The question is: if the LLM can see some history of its own previous decisions, does it place better trades?

To isolate memory, our primary setup fixes the prompt to decision-only JSON with no reasoning field. That means the treatment variable is memory, not prompt structure. We tested four memory modes: no history, last 5 events, last 20 events, and a rolling session summary.

We also ran two diagnostic variants. One allowed a one-sentence reasoning field in the JSON output, and the other added successful fills to the memory source, so the model could see not just what it decided, but what actually executed.

In the clean decision-only baseline, memory clearly helped. With no history, the LLM earned 476.88 dollars and ranked third. With last 5 events, it earned 4,098.52 dollars and ranked first. Last 20 events also earned 4,098.52 dollars and ranked first, while the rolling summary earned 3,042.80 dollars and also ranked first.

So the first finding is that even shallow memory improves the LLM's order placement. It does not necessarily make the model smarter in a human sense, but it gives enough context for better price and quantity decisions.

The reasoning diagnostic produced the best single result. With reasoning JSON and last 20 events, the LLM earned 6,004.31 dollars and ranked first. But reasoning was not uniformly helpful: with reasoning JSON and no history, the LLM lost 226.35 dollars. This supports the same lesson from Experiment 3: prompt features and memory features interact. We should not mix them when estimating the causal effect of memory alone.

The decisions-plus-fills diagnostic gives another useful result. When successful fills were included, the rolling summary was strongest, earning 4,576.82 dollars. But raw last 20 events with fills performed poorly: it submitted only 7 orders and earned just 387.66 dollars. This suggests that successful-trade memory is useful when compressed, but a long raw mixed memory can distract or overconstrain the small model.

There is also an important behavioral limitation. Across variants, the LLM remains strongly buy-biased and continues to submit orders at nearly every wakeup. Memory improves the quality and execution profile of trades, but it does not create restraint. The model still rarely chooses to hold.

Finally, Experiment 4 shows that agent-level profitability and market-level quality are not the same thing. Some high-PnL memory arms have tighter spreads or higher volume, but better LLM PnL does not always mean cleaner price discovery against the fundamental value. So in future analysis we need to report both LLM PnL and market-level metrics such as spread, volume, and tracking error against the fundamental.

The main conclusion from Experiment 4 is that memory can help, but more memory is not automatically better. Compact, relevant memory is safer than long raw history for a small local model.

## Slide 7: Overall Interpretation

**Speaker A**

Putting Experiments 1 through 4 together, the project has moved from infrastructure validation to LLM behavior diagnosis.

Experiment 1 showed that our ABIDES baseline is stable and that adaptive HBL agents outperform random zero-intelligence agents as expected.

Experiment 2 showed that a naive local LLM trader can be integrated successfully, but it destabilizes the market and loses heavily.

Experiment 3 showed that prompt structure matters. Open-ended chain-of-thought is harmful for this small model, while structured and evidence-grounded reasoning improves compliance and PnL.

Experiment 4 showed that memory also matters. Memory improves trading outcomes, but its benefit depends on representation. Summaries and compact recent history are more reliable than long raw history, especially when fills are included.

The recurring failure mode is that the LLM almost always trades. So far, neither reasoning nor memory reliably teaches the model to hold. That will be important for the next version of the agent, because a realistic trader should sometimes choose not to participate.

## Slide 8: Limitations And Next Steps

**Speaker A**

There are several limitations at this stage.

First, the completed results are still preliminary. Most runs use seed 12345 only, so we cannot make statistical claims yet. The next step is to replicate the main arms across at least 10 seeds and report means and dispersion.

Second, price discovery is still mostly inspected visually through the mid-price versus fundamental plots. We need to add a numeric tracking-error metric, such as RMSE between the mid-price and the ABIDES fundamental value.

Third, the current work uses one local model, Gemma 3 4B. This is useful for isolating design effects, but later replication with other small models would strengthen the conclusion.

Our immediate next experimental priorities are Experiment 5 and Experiment 6. Experiment 5 will vary the LLM's information access, such as top-of-book versus fuller order-book information. Experiment 6 will add controlled decision latency using ABIDES' latency model.

After that, the planned work includes shock-response experiments and communication or collusion experiments between LLM agents.

## Closing

**Speaker A**

To summarize, we have built a working local LLM-in-ABIDES pipeline and completed the first four experiments. The early evidence suggests that a small local LLM is not naturally a good trader, but its behavior can be improved substantially through structured prompting and carefully represented memory.

At the same time, the results warn us that better LLM PnL does not automatically mean better market quality, and that the model's always-trade bias remains unresolved. Those are the main issues we will address in the next stage.

Thank you. We are happy to discuss the results and get your feedback on the next experiments.
