# EXPERIMENT BLUEPRINT — LLM Policy Effect on Market Quality (Fixed-Wrapper Design)

> **Audience:** coding agent (Antigravity). This file is the authoritative spec.
> **Goal:** implement and run the paired-seed experiment that answers:
> *"After controlling for decision frequency, cancellation behavior, order size, and quote
> aggressiveness, how does replacing a random decision policy with an LLM-based one affect
> liquidity, price efficiency, volatility, and shock resilience?"*
>
> **Core design decision (LOCKED):** all mechanical factors are fixed in the agent wrapper,
> identically for both arms. The ONLY degree of freedom given to any policy is the ORDER SIDE
> (BUY or SELL). The LLM chooses side by reasoning over market state; the stochastic control
> chooses side by fair coin flip. Nothing is calibrated from LLM behavior. No distribution
> matching is required.

---

## 0. Repository layout (create this structure)

```
llm-market-experiment/
├── config/
│   ├── experiment.yaml          # master config (Section 2)
│   ├── market.yaml              # ABIDES market + background agents
│   └── shock.yaml               # shock regime spec
├── agents/
│   ├── fixed_wrapper.py         # shared mechanics for BOTH arms (Section 3)
│   ├── llm_policy.py            # side chooser: Gemma 3 4B via Ollama
│   ├── coin_policy.py           # side chooser: seeded RNG coin flip
│   └── prompt_template.py       # frozen prompt + parser
├── runner/
│   ├── run_cell.py              # run one (condition, regime, seed) → logs
│   ├── run_matrix.py            # orchestrate all cells × seeds
│   └── seeds.py                 # seed management (Section 5)
├── logging_/
│   ├── schema.py                # log record definitions (Section 7)
│   └── writers.py
├── analysis/
│   ├── metrics.py               # metric definitions (Section 6)
│   ├── paired_diffs.py          # per-seed differences + CIs
│   ├── event_study.py           # shock-centered trajectories
│   └── validation.py            # gates in Section 8
├── output/
│   ├── raw/{cell_id}/{seed}/    # per-run logs
│   └── results/                 # tables, figures
└── README.md
```

---

## 1. Experimental grid — 10 cells

5 agent conditions × 2 regimes. One "treatment slot" in the market is occupied by the
condition's agent; all background agents identical across conditions within a seed.

| cell_id | condition | wake_interval_s | policy       | regime |
|---------|-----------|-----------------|--------------|--------|
| C1-N    | ZI-canonical baseline | native ZI arrival | canonical ZI | normal |
| C2-N    | coin control          | 60   | coin flip    | normal |
| C3-N    | LLM                   | 60   | Gemma 3 4B   | normal |
| C4-N    | coin control          | 300  | coin flip    | normal |
| C5-N    | LLM                   | 300  | Gemma 3 4B   | normal |
| C1-S    | ZI-canonical baseline | native | canonical ZI | shock |
| C2-S    | coin control          | 60   | coin flip    | shock  |
| C3-S    | LLM                   | 60   | Gemma 3 4B   | shock  |
| C4-S    | coin control          | 300  | coin flip    | shock  |
| C5-S    | LLM                   | 300  | Gemma 3 4B   | shock  |

**C1 uses the stock ABIDES ZeroIntelligenceAgent, untouched** (native arrival process, native
pricing, no fixed wrapper). It is a reference market, not the causal comparison.

**Key contrasts (used in analysis):**
- Policy effect @60s: `C3 − C2` (within seed)
- Policy effect @300s: `C5 − C4`
- Frequency interaction: `(C3 − C2) − (C5 − C4)`
- Footprint effect: `C2 − C1`, `C4 − C1`
- Total effect: `C3 − C1`, `C5 − C1`

---

## 2. Master config (`config/experiment.yaml`) — values marked TODO must be set by the
## researcher before the freeze; suggested defaults given

```yaml
experiment:
  name: llm_policy_effect_v1
  simulator: ABIDES
  session:
    open: "09:30:00"
    close: "16:00:00"
    warmup_min: 30            # treatment agent inactive; metrics excluded
  ticks:
    tick_size: 0.01           # TODO confirm from pilot
    lot_size: 100             # TODO confirm; FIXED for both arms

market:                        # freeze at pilot values
  fundamental:
    process: mean_reverting_OU
    r_bar: 100000              # TODO from pilot (cents)
    kappa: 1.67e-13            # TODO
    sigma_s: 0                 # TODO
  background_agents:           # TODO: exact census from pilot, e.g.
    zi_agents: 50
    noise_agents: 100
    value_agents: 10

shock:                         # applies only to *-S cells
  type: fundamental_jump
  time: "12:30:00"             # fixed, mid-session, TODO confirm
  magnitude_sigma: 8           # jump = 8 × stationary sigma of fundamental; TODO confirm
  direction: up                # fixed for all cells; mirror-pair extension optional later
  event_window_min: 30         # ± window for event study

treatment_agent:
  wrapper:                     # IDENTICAL for LLM and coin arms — see Section 3
    cancel_all_on_wake: true
    order_type: limit
    size: ${experiment.ticks.lot_size}     # fixed, never chosen by policy
    placement: at_touch        # BUY at best bid + 0? at best ask? -> LOCKED RULE:
                               # BUY posts at current best bid (join the bid)
                               # SELL posts at current best ask (join the ask)
                               # TODO: researcher may instead choose midpoint±k ticks;
                               # whatever is chosen applies to BOTH arms identically
    forced_action: true        # every wake produces exactly one order; no hold
  llm:
    server: ollama
    model: gemma3:4b-instruct  # pin exact tag + digest at freeze
    temperature: 0.0           # TODO confirm; recommend 0 for reproducibility
    max_tokens: 200
    prompt_version: v_freeze   # frozen from pilot Experiment 3 winner
    memory_version: v_freeze   # frozen from pilot Experiment 4 winner
    invalid_action_fallback: coin_flip   # see Section 4.3
  coin:
    p_buy: 0.5                 # fair coin; NOT calibrated from LLM

seeds:
  technical_pilot: [1001, 1002, 1003]         # validation only, discarded from analysis
  final: range(2001, 2001 + N)                # N: TODO after variance check; start 30
```

---

## 3. Fixed wrapper (`agents/fixed_wrapper.py`) — SHARED BY BOTH ARMS

One class, two injectable policies. The wrapper owns ALL mechanics; the policy owns ONLY the
side choice.

```
class FixedWrapperAgent(TradingAgent):
    init(policy, wake_interval_s, wrapper_cfg)

    on_wakeup(t):
        1. snapshot market state S_t  (L1 book, last trades, own inventory, own PnL,
           recent history per frozen memory design)
        2. cancel ALL resting orders (log each cancellation)
        3. side = policy.choose_side(S_t)        # "BUY" | "SELL", nothing else
        4. price = placement_rule(side, book)    # deterministic, from wrapper_cfg
        5. submit limit order (side, price, size=lot_size)  (log)
        6. schedule next wake at t + wake_interval_s        # fixed, no jitter
```

**Hard requirements:**
- The policy interface is exactly `choose_side(state) -> {"BUY","SELL"}`. If the LLM policy
  returns anything else, the fallback in Section 4.3 fires. The wrapper must make it
  IMPOSSIBLE for a policy to influence size, price, timing, or cancellation.
- Bit-identical wrapper code path for both arms (same class, only `policy` differs).
- Position/risk checks from the existing validation layer remain, but if a check blocks an
  order, log it AND apply the same rule in both arms (it's deterministic given state, so
  paired seeds keep this fair).

---

## 4. Policies

### 4.1 Coin policy (`agents/coin_policy.py`)
```
choose_side(state):
    return "BUY" if rng_policy.random() < 0.5 else "SELL"
```
`rng_policy` is a dedicated RNG stream seeded from (seed, "policy") — see Section 5.

### 4.2 LLM policy (`agents/llm_policy.py`)
- Build prompt from S_t using the FROZEN template (pin the exact pilot winner: structured /
  JSON-oriented output; frozen memory design).
- Required model output (strict): `{"side": "BUY"}` or `{"side": "SELL"}` (JSON). The prompt
  must instruct JSON-only. Parser: strict JSON extract; strip code fences; validate against
  the two-value enum.
- Log per call: full prompt, raw completion, parsed side, latency_ms, prompt_tokens,
  completion_tokens, valid (bool).

### 4.3 Invalid output handling (LOCKED RULE)
If parse fails or side ∉ {BUY, SELL}:
- log `invalid_action = true`
- side = coin flip from the SAME dedicated policy RNG stream
- an order is still submitted → participation stays 100% in both arms by construction
- report invalid-action rate as a model-quality metric; it does NOT affect matching

### 4.4 Retry policy
No retries against the model (retries would make effective decision latency state-dependent).
One call per wake-up. Timeout ⇒ treated as invalid (4.3). Log timeouts separately.

---

## 5. Seeding (`runner/seeds.py`)

Per (seed, cell):
- `rng_market(seed)`         → fundamental path + background agents. IDENTICAL across all 5
                                conditions for the same seed & regime. This is the pairing.
- `rng_policy(seed, cell)`   → coin flips / fallback flips only. Independent stream so agent
                                randomness never perturbs the shared background draw sequence.
- LLM temperature 0 ⇒ deterministic given prompt. If temperature > 0, seed Ollama per
  (seed, cell) and record it.

**Pairing invariant (MUST VERIFY, Section 8):** within a seed & regime, the fundamental path
and the background-agent event stream are byte-identical across all 5 conditions up to the
first treatment-agent action, and the fundamental path is identical throughout.

---

## 6. Metrics (`analysis/metrics.py`) — computed post-warmup only

### Primary
| metric | definition |
|---|---|
| `midpoint_error_tw` | time-weighted mean of \|midpoint_t − fundamental_t\| over session (cents) |
| `quoted_spread_tw`  | time-weighted mean of (ask − bid); log also median |
| `depth_at_touch_tw` | time-weighted mean of (bid_size + ask_size) at best quotes |
| `recovery_time_s`   | shock cells: first time post-shock at which midpoint stays within THRESH of the NEW fundamental for HOLD consecutive seconds. THRESH = 1 × pre-shock stationary sigma (TODO confirm); HOLD = 60 s (TODO confirm) |

### Secondary
`realized_vol` (5-min midpoint returns, annualization not needed — report per-session),
`overshoot` (max excursion beyond new fundamental in shock direction, shock cells),
`book_availability` (fraction of session with two-sided quotes),
`unique_trades`, `volume`, `submissions`, `cancellations`, `fill_rate` (treatment agent),
`inventory_path` (mean abs + terminal), `turnover`, `pnl` (marked to fundamental at close),
`invalid_action_rate`, `timeout_rate`, `tokens_total`, `latency_ms_p50/p95`.

All metric definitions FREEZE before the final run. Metric code must pass the hand-check in
Section 8.3 first.

---

## 7. Logging schema (`logging_/schema.py`) — one file set per (cell, seed)

- `decisions.parquet`: t_wake, state_snapshot_id, prompt_hash, raw_output, parsed_side,
  valid, fallback_used, latency_ms, tokens_in, tokens_out
- `orders.parquet`: order_id, t_submit, side, price, size, t_cancel|t_fill, fill_price,
  fill_size, lifecycle_status  ← the corrected order-lifecycle logging; every order MUST
  reach a terminal state in the log
- `book_l1.parquet`: event-driven L1 snapshots (t, bid, bid_sz, ask, ask_sz, midpoint)
- `trades.parquet`: all market trades (t, price, size, aggressor_side if available)
- `fundamental.parquet`: (t, value)
- `agent_state.parquet`: (t, inventory, cash, pnl_marked)
- `run_manifest.json`: full resolved config, git commit, model digest, seeds, wall-clock

---

## 8. Validation gates — ALL must pass on technical pilot seeds BEFORE the freeze

1. **Mechanics-identity audit (replaces distribution matching):** for each pilot seed,
   assert C2 vs C3 (and C4 vs C5) have IDENTICAL: number of wake-ups, number of submissions
   (= wake-ups), number of cancellations, all order sizes, and the placement rule applied.
   The ONLY permitted differences: the side sequence and (via fills) downstream book state.
   This is a hard assertion, not a statistical test — the design guarantees it, the audit
   proves the code implements the design.
2. **Pairing audit:** hash the fundamental path per (seed, regime): identical across all 5
   conditions. Hash background-agent order stream up to first treatment action: identical.
3. **Metric sanity:** run one tiny scripted market with known ground truth; verify
   midpoint_error, spread, depth, recovery_time by hand calculation.
4. **Order-lifecycle integrity:** zero orders without terminal state; fills reconcile with
   inventory changes; cancellations reconcile with wake-ups.
5. **LLM health:** invalid_action_rate on pilot seeds < 10% (else fix prompt BEFORE freeze —
   changing it after is protocol violation); timeout_rate < 1%.
6. **FREEZE:** tag git commit; pin model digest; write `FREEZE.md` recording every TODO
   resolution. After freeze, no changes to prompt, config, metrics, or code except fatal-bug
   fixes (documented).

---

## 9. Execution order (run_matrix.py)

1. Technical pilot: all 10 cells × pilot seeds → run all Section 8 gates.
2. Variance check: compute between-seed SD of primary metrics from pilot; confirm N=30 gives
   reasonable CI width for C3−C2 differences; adjust N if needed; record decision.
3. FREEZE.
4. Final run: all 10 cells × N final seeds. Order: iterate seeds outermost, conditions
   innermost, so partial completion still yields complete seed-pairs.
5. LLM cells are the bottleneck (one Ollama call per wake-up). Estimated calls per run:
   session 6.5 h = 23,400 s ⇒ ~390 calls @60s, ~78 calls @300s. Parallelize across seeds
   only if the Ollama server is replicated with pinned model digest; never share one model
   instance across concurrent runs if temperature > 0.

## 10. Analysis outputs (`analysis/`)

1. `paired_diffs.py`: for each primary & secondary metric — per-seed differences for the five
   key contrasts (Section 1); mean, 95% CI (t and BCa bootstrap over seeds), and a
   Wilcoxon signed-rank p as robustness. One table per regime.
2. `event_study.py`: shock cells — metric trajectories in 1-min bins over shock ± 30 min,
   aligned at shock time, averaged over seeds, plotted per condition with seed-level bands.
3. Decomposition figure: total (C3−C1) split into footprint (C2−C1) + policy (C3−C2), per
   frequency, per regime, for each primary metric.
4. Side-quality diagnostic (descriptive, not primary): P(LLM side is fundamental-correcting)
   vs 0.5 for the coin, overall and within the shock window.
