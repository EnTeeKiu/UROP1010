# AI Agents and Market Behavior: Project Summary and Redesigned Experiment

## Executive Summary

This project has successfully built a working experimental platform that connects a locally hosted Gemma 3 4B language model to an ABIDES continuous double-auction market. The completed experiments validated the market environment, introduced an LLM trader, and examined how prompt structure and memory design changed the LLM's actions and market outcomes.

The existing results are valuable as pilot evidence, but they do not yet establish that the observed market disruption was caused specifically by AI reasoning. The LLM was configured to wake every 60 simulated seconds, cancel its previous orders, and make a new decision. Although the model was allowed to hold, it almost never chose to do so. The combination of frequent decision opportunities and an "always trade" tendency therefore generated unusually active order flow. Wider spreads, higher volume, and volatility could have resulted from:

- the LLM's state-dependent reasoning;
- the one-minute wake-up schedule;
- repeated order cancellation and replacement;
- its order-size and price aggressiveness;
- or an interaction between these factors.

The recommended direction is therefore to preserve Experiments 1-4 as an engineering and diagnostic pilot, but redesign the main research experiment around a causal market-level question. The redesigned study will separate the effect of the AI policy from the mechanical effect of how often the agent is allowed to act.

---

## 1. What We Did

### 1.1 Market and engineering platform

We developed a reproducible experimental environment using ABIDES, an event-driven market simulator with a persistent limit-order book, exchange messages, agent-specific latency, and heterogeneous trading agents.

The platform includes:

- a synthetic stock with a mean-reverting fundamental value;
- a two-hour continuous double-auction session;
- traditional Zero-Intelligence, Heuristic Belief Learning, Value, and Momentum agents;
- a locally hosted Gemma 3 4B Instruct model served through Ollama;
- an LLM-to-ABIDES interface that translates market observations into buy, sell, or hold decisions;
- position and order validation;
- logging of prompts, responses, orders, fills, inventory, market data, and PnL;
- analysis of spreads, volume, price discovery, LLM behavior, and output compliance.

Local hosting is important because it provides a low-cost and reproducible setting for studying small open-source AI agents rather than relying only on large proprietary models.

### 1.2 Experiment 1: Traditional market baseline

The first experiment used ten traditional traders and no LLM. It demonstrated that the simulator, exchange, agent population, and logging pipeline were operational. The market produced continuous trading, a functioning order book, and prices that moved around the synthetic fundamental value.

This experiment established the no-AI reference condition needed for later comparisons.

### 1.3 Experiment 2: Naive LLM-inclusive market

The second experiment replaced one Zero-Intelligence trader with one LLM trader. The LLM woke every 60 simulated seconds, observed the market, cancelled its previous resting orders, and returned a new JSON decision.

The pilot run reported:

- a higher mean spread;
- substantially more submitted and executed order activity;
- greater mid-price volatility;
- poor LLM PnL and profitable counterparty agents.

This run demonstrated that one LLM-controlled trader could materially alter the simulated market path. However, it did not isolate whether the difference was caused by AI reasoning or by the LLM agent's configured activity pattern.

### 1.4 Experiment 3: Prompt and reasoning ablation

The third experiment tested several prompt structures:

- minimal raw state;
- open or unstructured reasoning;
- structured reasoning using explicit reasoning sections;
- evidence-grounded reasoning;
- structured JSON output.

The main diagnostic finding was that the small model was highly sensitive to its output and reasoning scaffold. Unstructured reasoning increased parsing problems and produced poor trading behavior in the observed run. Structured prompts improved action compliance. The evidence-grounded condition produced the best LLM PnL among the prompt variants in that seed.

These results should be interpreted as pilot hypotheses, not final causal conclusions, because they were obtained primarily from one market seed. The JSON and evidence-grounded prompts also did not contain exactly identical instructions, so the difference cannot be attributed only to JSON syntax.

### 1.5 Experiment 4: Memory ablation

The fourth experiment compared:

- no history;
- the last five events;
- the last twenty events;
- a rolling session summary;
- optional inclusion of successful fills;
- decision-only versus rationale-producing output.

Some memory conditions produced much higher LLM PnL than the no-history condition in the observed seed. Compressed fill-aware summaries sometimes performed better than long raw histories. However, memory did not reliably produce selective participation: the LLM continued to trade at nearly every available decision opportunity in most conditions.

An important distinction is that the basic memory implementation often stored the model's proposed decisions, including decisions that might later be rejected, clamped, cancelled, or left unfilled. It therefore measured memory of intentions more than memory of realized trading outcomes.

---

## 2. What Was Our Existing Contribution?

The completed work makes four useful preliminary contributions.

### 2.1 A local LLM-ABIDES research pipeline

We created an end-to-end framework for placing a small, locally hosted language model inside a high-fidelity, event-driven market. The framework supports controlled agent replacement, prompt and memory changes, order execution, and detailed behavioral logging.

### 2.2 Evidence of behavioral and interface fragility

The experiments show that LLM trading behavior depends strongly on how market state, reasoning, memory, quantities, and output formats are presented. A model can produce correctly formatted decisions while still making poorly calibrated trades. Conversely, a more verbose reasoning format can reduce machine-readability.

### 2.3 Identification of an always-trade failure mode

Across prompt and memory variants, the LLM almost never deliberately held. This is practically important because a model that treats every wake-up as a requirement to trade can create excessive turnover, cancellation traffic, and inventory risk.

### 2.4 Identification of an experimental confound

The experiments revealed that "introducing an AI trader" and "introducing a trader with a different activity schedule" were changed simultaneously. Recognizing this issue is itself an important methodological contribution. It motivates a stronger experiment that separates:

1. the effect of the decision policy;
2. the effect of decision frequency;
3. the effect of order aggressiveness and cancellation behavior.

The present work should therefore be reported as a successful pilot and validation study that discovered the mechanisms and measurement requirements for the redesigned experiment.

---

## 3. Why the Main Experiment Should Be Redesigned

The previous comparison cannot yet support the statement that the LLM's reasoning destabilized the market.

The LLM was not literally forced to submit an order at every wake-up because `HOLD` was available. Nevertheless, it was forced to reconsider the market every minute, and the model almost always interpreted that opportunity as a reason to trade. The observed activity was therefore an interaction between configuration and model behavior:

> Frequent scheduled wake-ups created many opportunities to act, while the LLM's learned policy converted nearly every opportunity into an order.

A traditional agent with the same wake frequency, cancellation policy, quantity distribution, and aggressive prices might also increase volume and volatility. Without such a control, the previous experiment cannot distinguish an AI-specific effect from a high-activity-trader effect.

Other issues to correct in the redesigned analysis include:

- repeating conditions across multiple market seeds;
- explicitly controlling the LLM sampling seed and model version;
- counting each matched trade once rather than counting both buyer and seller execution messages;
- reconstructing valid order-book states instead of forward-filling stale quotes across one-sided books;
- using time-weighted spreads rather than event-weighted averages;
- valuing every agent's terminal inventory at one common terminal price;
- separating proposed, validated, submitted, accepted, cancelled, and executed orders;
- representing LLM computation delay in simulated time rather than wall-clock time.

---

## 4. Central Research Question

> **How does the introduction of an LLM-based trading agent affect liquidity, price efficiency, volatility, and shock resilience after controlling for decision frequency, cancellation behavior, order size, and quote aggressiveness?**

This question separates the AI decision policy from the market activity generated by the experimental configuration.

### Supporting questions

1. Does frequent scheduled participation change market quality even when the trader is not controlled by an LLM?
2. Does an LLM produce additional market effects beyond those produced by an activity-matched stochastic trader?
3. Does reducing the wake-up frequency reduce any harmful effects of the LLM?
4. Does the LLM help prices incorporate a fundamental-value shock, or does it increase overshooting and instability?
5. Can a deterministic risk-governance layer reduce harmful market effects without removing useful price discovery?

---

## 5. Hypotheses

### H1: Activity-frequency effect

Frequent wake-ups and order replacement will increase order submissions, cancellations, and volume for both AI and non-AI traders.

### H2: AI-policy effect

After matching activity frequency and basic order-flow characteristics, any remaining difference between the LLM and stochastic control will represent an AI-policy effect arising from how the LLM maps market states to actions.

### H3: Interaction effect

The effect of the LLM will be strongest under the frequent wake-up condition because its tendency to trade at nearly every opportunity interacts with the number of available decision points.

### H4: Shock-response effect

Evidence-grounded LLM decisions may help prices respond to a fundamental shock, but frequent reactions may also create overshooting, wider spreads, or directional inventory accumulation.

### H5: Governance effect

A deterministic participation and risk-control layer will reduce excessive turnover, inventory exposure, and volatility while preserving any improvement in price discovery.

---

## 6. Detailed Redesigned Experiment

### 6.1 Market environment

The core environment will retain the existing ABIDES infrastructure:

- one synthetic asset;
- a mean-reverting fundamental-value process;
- ten trading agents plus the exchange;
- the existing heterogeneous traditional-agent population;
- identical starting cash, position limits, and information access;
- one designated Zero-Intelligence position replaced by the experimental agent;
- fixed agent-specific random seeds that do not shift when the treatment agent changes;
- complete order, execution, inventory, prompt, and market-state logging.

The same model, prompt, memory configuration, decoding settings, and model digest must be frozen across all LLM conditions.

### 6.2 Main factorial treatments

The main experiment varies two factors:

1. **Decision policy**
   - LLM policy;
   - activity-matched stochastic policy.

2. **Wake-up frequency**
   - frequent: every 60 simulated seconds;
   - slower: every 300 simulated seconds.

A no-treatment traditional market is retained as the reference condition.

| Condition | Treatment agent | Wake schedule | Purpose |
| --- | --- | --- | --- |
| C0 | Traditional ZI agent | Original ZI schedule | No-AI market baseline |
| C1 | Activity-matched stochastic agent | 60 seconds | Mechanical high-activity control |
| C2 | LLM agent | 60 seconds | Replication of the high-frequency LLM treatment |
| C3 | Activity-matched stochastic agent | 300 seconds | Mechanical lower-activity control |
| C4 | LLM agent | 300 seconds | Tests whether reducing opportunities changes LLM impact |

The comparison `C2 - C1` estimates the AI-policy effect under frequent participation. The comparison `C4 - C3` estimates the AI-policy effect under slower participation. The comparison `C2 - C4`, interpreted together with `C1 - C3`, estimates whether wake-up frequency affects the LLM differently from a non-AI trader.

### 6.3 Activity-matched stochastic control

The stochastic control should not simply be the original ZI agent. It should imitate the mechanical properties of the pilot LLM without using language reasoning.

It will use:

- the same wake schedule as its paired LLM condition;
- the same order lifetime and cancellation policy;
- the same position and quantity limits;
- the same empirical probability of proposing BUY, SELL, or HOLD;
- a matched distribution of order quantities;
- a matched distribution of quote distance from the current midpoint;
- the same deterministic validation and risk rules.

The control may calculate a price relative to the current midpoint, but its direction and aggressiveness will be sampled from pilot distributions rather than generated through state-dependent language reasoning. This preserves basic activity while removing the LLM's interpretation of market state.

### 6.4 LLM treatment

The LLM configuration should be selected for reliability rather than because it happened to earn the highest PnL in seed 12345.

The treatment should:

- use one frozen, compact, evidence-grounded prompt;
- explicitly state that holding is acceptable and does not represent failure;
- express quantity consistently in lots;
- separate optional reasoning from the machine-readable action;
- use temperature zero and an explicit inference seed where supported;
- log the model name, model digest, prompt hash, response, and token count;
- apply the same position and price validation used by the matched control.

The LLM should not receive the true fundamental value unless information access is itself a planned treatment. Otherwise, it would have an information advantage over some background agents.

### 6.5 Shock treatment

Each of the five conditions will be run in two market regimes:

- **Normal regime:** the existing mean-reverting process without an imposed shock.
- **Shock regime:** a standardized change in fundamental value halfway through the session.

The shock direction should be balanced across seeds: half positive and half negative. Shock magnitude should be specified before the experiment, such as a fixed percentage or fixed number of price ticks.

This produces ten principal cells:

`5 agent conditions × 2 market regimes`.

### 6.6 Optional governance extension

After the main effects are established, an additional risk-governed LLM can be tested. The governance layer may:

- require a minimum price discrepancy before trading;
- impose a cooldown after an execution;
- prevent repeated same-direction orders at the position boundary;
- cap quote distance from the best bid or ask;
- require a deliberate hold when expected edge is below a threshold;
- limit cancellation and replacement frequency.

The governance condition should not be mixed into the first causal comparison. It is a follow-up intervention designed to answer a practical question: whether market harm can be reduced through deterministic controls around an unchanged LLM.

### 6.7 Replication and run count

Begin with 5-10 paired seeds per cell to estimate variance and identify technical problems. The final target should be at least 20 paired market seeds per cell if computation time permits.

For the main design:

- 5 agent conditions;
- 2 regimes;
- 20 seeds;
- 200 total market runs.

Only four of the ten cells contain an LLM, so 80 of the 200 runs require model inference. If this remains too costly, the pilot can use ten seeds and the estimated variance can guide a formal power calculation.

All conditions sharing a seed should use the same fundamental-value path and the same background-agent random streams. This paired design substantially improves statistical efficiency.

### 6.8 Simulated latency

Wall-clock inference time does not automatically become ABIDES market latency because the simulation clock pauses during a synchronous model call. The main experiment should therefore give the LLM and matched control the same fixed simulated decision delay.

Latency can later become a separate treatment, but it should not be allowed to vary unintentionally in the core experiment.

### 6.9 Market size and future scalability

Ten trading agents are sufficient for a controlled small-market experiment, provided that the conclusion is scoped correctly and each condition is repeated across enough independent market seeds. The ten agents define the market being studied; they are not ten independent statistical observations. The independent experimental units are the repeated simulation runs or paired seeds.

With approximately 20-30 paired seeds per condition, the main experiment can support a conclusion such as:

> In a small ABIDES market containing ten heterogeneous traders, introducing an LLM under the specified participation schedule changed liquidity, price efficiency, volatility, or shock resilience by the estimated amount.

Repeating seeds tests whether this result is robust to different stochastic market paths. It does not test whether the effect remains the same in a larger or deeper market. A single treatment agent may have disproportionate influence when it represents 10% of all traders.

The future robustness phase should therefore repeat selected principal comparisons in a larger market, initially with approximately 30 trading agents:

| Larger-market condition | Composition | Purpose |
| --- | --- | --- |
| L0 | 30 traditional traders | Larger no-AI baseline |
| L1 | 29 traditional traders + 1 activity-matched control | Mechanical-activity comparison |
| L2 | 29 traditional traders + 1 LLM | Tests whether a single LLM's effect is diluted in a deeper market |

Approximately ten paired seeds per larger-market condition would provide an initial scalability check without repeating the entire factorial design.

Two distinct scaling questions can eventually be studied:

1. **Fixed number of AI agents:** Compare one LLM among ten traders with one LLM among thirty traders. This tests whether a single AI agent's effect becomes diluted as market depth increases.
2. **Fixed AI market share:** Compare one LLM among ten traders with three LLMs among thirty traders. This tests whether the effect persists when AI participation remains at 10%.

The fixed-number test should be performed first because it is cheaper and isolates market-depth sensitivity. The fixed-share test is a later multi-LLM extension and requires substantially more inference, as well as additional controls for correlated outputs or interaction among the LLM agents.

---

## 7. Outcome Measures

### 7.1 Primary market-level outcomes

Three primary outcomes should be specified before running the experiment.

1. **Price efficiency**
   - time-weighted midpoint RMSE relative to fundamental value.

2. **Liquidity**
   - time-weighted quoted spread;
   - time-weighted depth at the best bid and ask.

3. **Shock resilience**
   - time required for the midpoint to enter and remain within a predefined band around the new fundamental value.

### 7.2 Secondary outcomes

- realized price volatility;
- maximum price deviation from fundamental value;
- overshoot following a shock;
- duration of one-sided or empty books;
- unique trade count and executed volume;
- order-submission and cancellation rates;
- fill rate;
- signed short-horizon price impact after treatment-agent orders;
- treatment-agent inventory and turnover;
- PnL and wealth transfers by agent type;
- frequency of invalid, rejected, clamped, or fallback actions;
- token use and simulated decision latency.

Agent PnL should be a secondary outcome. A profitable LLM can still reduce market quality, while an unprofitable LLM can still contribute liquidity or information.

---

## 8. Analysis Plan

The primary analysis will compare outcomes at the seed level using paired differences. A suitable model is:

`Outcome ~ AI policy + frequent wake-up + shock + interactions + seed effect`

The most important coefficient is the interaction between AI policy and wake-up frequency. It tests whether frequent opportunities are especially destabilizing when the policy is produced by the LLM.

The report should include:

- treatment means and standard deviations;
- paired treatment differences;
- bootstrap or model-based 95% confidence intervals;
- effect sizes, not only p-values;
- event-study plots centered on the shock;
- distributions across seeds rather than only one representative trajectory;
- sensitivity analysis using midpoint, fundamental-value, and liquidation-based terminal valuation.

The three primary outcomes should be separated from exploratory secondary metrics to reduce the risk of selecting only favorable results.

---

## 9. Expected Contribution of the Redesigned Experiment

### 9.1 Causal decomposition of market impact

The new experiment will distinguish an AI-specific policy effect from the effects of wake frequency, cancellations, order sizing, and quote aggressiveness. This is stronger than comparing a standard traditional agent directly with a differently configured LLM trader.

### 9.2 Evidence about small local AI agents

Much existing research emphasizes large proprietary models. This study focuses on a small, locally deployed 4B model under constrained hardware and controlled market conditions.

### 9.3 Market-level rather than profit-only evaluation

The study prioritizes price efficiency, liquidity, volatility, and resilience. It therefore evaluates whether an AI trader benefits or harms the market, not merely whether the AI earns money.

### 9.4 Configuration as part of AI market risk

The research explicitly tests whether market effects emerge from the interaction between a model's behavior and its deployment configuration. This is practically important: wake-up schedules, order lifetimes, cancellation rules, and risk limits are design choices controlled by system developers.

### 9.5 Stress testing and governance

The shock and optional risk-governance experiments connect the research to market resilience and responsible deployment. The results can show whether simple deterministic controls reduce destabilizing behavior without removing useful price discovery.

### 9.6 Reproducible evaluation framework

The final output can include an open experimental configuration, activity-matched control agent, corrected metric pipeline, paired-seed runner, and standardized result report. This infrastructure is itself a useful contribution for future research on AI agents in markets.

### 9.7 Evidence about scalability

The full ten-trader factorial study establishes internally valid effects in a controlled small market. The larger-market robustness phase will show whether those effects are diluted, preserved, or amplified as market depth and the number of counterparties increase. Clearly separating seed replication from population-size robustness prevents repeated runs from being incorrectly presented as evidence that the result automatically generalizes to larger markets.

Even a null result would be informative. If the LLM and activity-matched control produce similar outcomes, the earlier disruption was mainly mechanical. If they differ after activity is matched, the residual difference provides stronger evidence of an AI-specific market effect.

---

## 10. Recommended Project Narrative

The project can be presented as a progression:

1. We built and validated a local LLM trading environment in ABIDES.
2. A naive LLM-inclusive pilot produced much more activity and a different market path.
3. Prompt and memory experiments revealed behavioral fragility and an almost universal tendency to trade.
4. These diagnostics showed that the original AI-versus-traditional comparison confounded decision policy with deployment configuration.
5. We therefore redesigned the main study to isolate AI reasoning from wake frequency and matched order flow.
6. The new experiment evaluates market efficiency, liquidity, volatility, and shock resilience, with an optional governance intervention.

This framing preserves the value of all completed work. The earlier experiments are not discarded; they provide the empirical motivation, agent calibration data, implementation foundation, and methodological insight required for the stronger causal experiment.

---

## Selected Related Research

- Alejandro Lopez-Lira, [Can Large Language Models Trade? Testing Financial Theories with LLM Agents in Market Simulations](https://arxiv.org/abs/2504.10789).
- Kushal Agrawal et al., [Evaluating LLM Agent Collusion in Double Auctions](https://arxiv.org/abs/2507.01413).
- Ing-Haw Cheng et al., [Agents Are Not Algorithms: The Tradeoffs of Decision-Time Reasoning in AI Trading](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6713620).
- Taojie Zhu et al., [From Knowing to Doing: A Memory-Controlled Benchmark for LLM Trading Agents on Stock Markets](https://arxiv.org/abs/2605.28359).
