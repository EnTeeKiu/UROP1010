# Experiment Implementation Roadmap & Milestone Progress Report

> **Project:** Fixed-Wrapper LLM Policy Market Experiment (UROP1010)  
> **Date:** August 30, 2026  
> **Status:** Milestones 1–4 Completed & Verified  

---

## Executive Summary

To isolate the causal effect of **AI reasoning** from mechanical activity confounds (wake-up frequency, order size, quote placement, cancel-all behavior), the experiment utilizes a **Fixed-Wrapper Design**. Both treatment arms (LLM and Coin Control) share a single `FixedWrapperAgent` execution wrapper. The only degree of freedom provided to any policy is the **order side (`BUY` vs `SELL`)**.

This document outlines the **6-Milestone Construction Roadmap** and documents the implementation and verification details of **Milestones 1–4**.

---

## Master Construction Roadmap (Milestones 1–6)

```
[Milestone 1: Non-LLM Baseline & Wrapper Engine]  <-- COMPLETED & VERIFIED
       │
       ▼
[Milestone 2: LLM Policy & Ollama Integration]     <-- COMPLETED & VERIFIED
       │
       ▼
[Milestone 3: Shock Regime Oracle (-S)]            <-- COMPLETED & VERIFIED
       │
       ▼
[Milestone 4: Structured Parquet Logging Engine]   <-- COMPLETED & VERIFIED
       │
       ▼
[Milestone 5: Technical Pilot & Validation Gates]       <-- CONSTRUCTED (AWAITING RUN)
       │
       ▼
[Milestone 6: Full Matrix Execution & Statistical Analysis]
```

---

## Detailed Milestone Status & Roadmap

### 🟢 Milestone 1: Non-LLM Baseline & Wrapper Engine (COMPLETED)

#### Goal
Build the core infrastructure, fixed wrapper, coin policy, deterministic seeding, dynamic config builder, and single-cell runner. Verify non-LLM cells (`C1-N`, `C2-N`, `C4-N`).

#### Files Constructed & Modified

| File Path | Description / Responsibility |
|---|---|
| [`abides/config/experiment.yaml`](file:///d:/VinUni-UROP/abides/config/experiment.yaml) | Master experiment configuration (session hours 09:30–16:00, 30m warmup, tick/lot size, fundamental parameters, seed definitions). |
| [`abides/config/shock.yaml`](file:///d:/VinUni-UROP/abides/config/shock.yaml) | Shock regime specifications (12:30 fundamental jump, 8σ magnitude). |
| [`abides/agent/experiment/__init__.py`](file:///d:/VinUni-UROP/abides/agent/experiment/__init__.py) | Package initialization file for experimental agents. |
| [`abides/agent/experiment/fixed_wrapper.py`](file:///d:/VinUni-UROP/abides/agent/experiment/fixed_wrapper.py) | **`FixedWrapperAgent`**: Shared execution wrapper handling schedule, `cancelOrders()`, `getCurrentSpread()`, `at_touch` limit price placement, position limit clamping ($\pm 10$ lots), and order submission. |
| [`abides/agent/experiment/coin_policy.py`](file:///d:/VinUni-UROP/abides/agent/experiment/coin_policy.py) | **`CoinPolicy`**: Fair 50/50 `BUY`/`SELL` side decision chooser. |
| [`abides/agent/experiment/seeds.py`](file:///d:/VinUni-UROP/abides/agent/experiment/seeds.py) | **Seeding Engine**: Implements the pairing invariant (shared `market`, `oracle`, `exchange`, `background`, `latency` seeds per master seed; independent `policy` seed per cell). |
| [`abides/agent/experiment/build_config.py`](file:///d:/VinUni-UROP/abides/agent/experiment/build_config.py) | **`build_experiment_config()`**: Dynamic builder constructing the 11-agent simulation environment for cells C1–C5 and regimes N/S. |
| [`abides/run_cell.py`](file:///d:/VinUni-UROP/abides/run_cell.py) | **CLI Runner**: Script to execute any single `(cell_id, regime, seed)` simulation and emit raw logs + `run_manifest.json`. |

#### Empirical Verification Results

Three test runs were executed on master seed `1001`:

```bash
python run_cell.py --cell C1-N --seed 1001
python run_cell.py --cell C2-N --seed 1001
python run_cell.py --cell C4-N --seed 1001
```

| Cell ID | Condition Description | Messages Processed | Runtime | Output Directory | Status |
|---|---|---|---|---|---|
| **`C1-N`** | Stock ZeroIntelligence baseline (no wrapper) | 2,361 | 3.80s | [`abides/output/raw/C1-N/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C1-N/1001/) | ✅ SUCCESS |
| **`C2-N`** | CoinControl @ 60s wake interval | 6,111 | 4.99s | [`abides/output/raw/C2-N/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C2-N/1001/) | ✅ SUCCESS |
| **`C4-N`** | CoinControl @ 300s wake interval | 2,857 | 3.22s | [`abides/output/raw/C4-N/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C4-N/1001/) | ✅ SUCCESS |

Each run generated complete ABIDES binary logs (`.bz2`), order book depth snapshots, agent event logs, and `run_manifest.json`.

---

### 🟢 Milestone 2: LLM Policy & Ollama Integration (COMPLETED)

#### Goal
Implement the LLM policy module and frozen prompt template to connect `FixedWrapperAgent` to Gemma 3 4B via Ollama.

#### Files Constructed & Modified
- [`abides/agent/experiment/prompt_template.py`](file:///d:/VinUni-UROP/abides/agent/experiment/prompt_template.py): Frozen system prompt and user state serializer.
- [`abides/agent/experiment/llm_policy.py`](file:///d:/VinUni-UROP/abides/agent/experiment/llm_policy.py): `LLMPolicy` class querying local Ollama (`gemma3:4b`), parsing JSON output (`{"side": "BUY" \| "SELL"}`), handling fallbacks seamlessly.

#### Empirical Verification Results

The 300s wake-interval LLM condition (`C5-N`) was executed with live Ollama `gemma3:4b` inference:

```bash
python run_cell.py --cell C5-N --seed 1001
```

| Cell ID | Condition Description | Messages Processed | Runtime | Output Directory | Status |
|---|---|---|---|---|---|
| **`C5-N`** | LLMPolicy @ 300s wake interval (Ollama) | 2,882 | 234.78s | [`abides/output/raw/C5-N/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C5-N/1001/) | ✅ SUCCESS |

The LLM agent successfully processed state snapshots, generated JSON responses, placed trades, and generated structured metadata without breaking ABIDES.

---

### 🟢 Milestone 3: Shock Regime Oracle (-S) (COMPLETED)

#### Goal
Implement the deterministic shock oracle for testing market resilience following a mid-session fundamental jump.

#### Files Constructed & Modified
- [`abides/agent/experiment/shock_oracle.py`](file:///d:/VinUni-UROP/abides/agent/experiment/shock_oracle.py): `ShockOracle` extending `SparseMeanRevertingOracle` to apply an $80 (8000 cents) deterministic fundamental shift exactly at 12:30:00, and shift the mean-reversion anchor so the price remains high.
- [`abides/agent/experiment/build_config.py`](file:///d:/VinUni-UROP/abides/agent/experiment/build_config.py): Already configured to deploy `ShockOracle` for `-S` regimes.

#### Empirical Verification Results

Simulations were run for the shock regime (`-S`):

```bash
python run_cell.py --cell C1-S --seed 1001   # Baseline + Shock
python run_cell.py --cell C2-S --seed 1001   # Coin @ 60s + Shock
```

| Cell ID | Condition Description | Messages Processed | Runtime | Output Directory | Status |
|---|---|---|---|---|---|
| **`C1-S`** | Stock ZI Baseline + Shock | 2,308 | 4.56s | [`abides/output/raw/C1-S/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C1-S/1001/) | ✅ SUCCESS |
| **`C2-S`** | CoinControl @ 60s + Shock | 5,919 | 4.02s | [`abides/output/raw/C2-S/1001/`](file:///d:/VinUni-UROP/abides/output/raw/C2-S/1001/) | ✅ SUCCESS |

The oracle successfully injected the shock exactly at 12:30:00 without disrupting the event queue or the underlying Ornstein-Uhlenbeck processes.

---

### 🟢 Milestone 4: Structured Parquet Logging Engine (COMPLETED)

#### Goal
Extract raw ABIDES `.bz2` binary logs into standardized Pandas/Parquet datasets for downstream metric calculation.

#### Files Constructed & Modified
- [`abides/logging_/schema.py`](file:///d:/VinUni-UROP/abides/logging_/schema.py): Strict pyarrow data types enforced for five downstream schemas (`DECISIONS`, `ORDERS`, `TRADES`, `BOOK_L1`, `FUNDAMENTAL`).
- [`abides/logging_/writers.py`](file:///d:/VinUni-UROP/abides/logging_/writers.py): Extraction script mapping internal ABIDES log payloads to standardized datasets.

#### Empirical Verification Results

The extraction script was run on the `C2-S/1001` test simulation directory:

```bash
python -m logging_.writers output/raw/C2-S/1001
```

| Generated Parquet File | Schema Validated | Row Count (C2-S) | Description |
|---|---|---|---|
| `decisions.parquet` | ✅ `DECISIONS_SCHEMA` | 360 | Extract of treatment policy calls, LLM metadata, final limit prices. |
| `orders.parquet` | ✅ `ORDERS_SCHEMA` | 1688 | Extract of limit orders submitted to exchange, split by direction. |
| `trades.parquet` | ✅ `TRADES_SCHEMA` | 722 | Trade fill executions mapping buyers and sellers. |
| `book_l1.parquet` | ✅ `BOOK_L1_SCHEMA` | 1561 | Top-of-book (best bid/ask) state reconstructed from market depth. |
| `fundamental.parquet`| ✅ `FUNDAMENTAL_SCHEMA`| 210 | Sub-second tracking of the fundamental value (including shocks). |

---

### 🟡 Milestone 5: Technical Pilot & Validation Gates (CONSTRUCTED — AWAITING RUN)

#### Goal
Run all 10 experimental cells across 3 technical pilot seeds (`1001`, `1002`, `1003`) and verify the 4 mechanical/statistical validation gates.

#### Files Constructed
- [`abides/run_matrix.py`](file:///d:/VinUni-UROP/abides/run_matrix.py): Orchestrator script that loops over seeds × cells, runs each simulation via `run_cell.py`, automatically invokes the Parquet log extractor, and writes a JSON summary to `output/results/`.
- [`abides/analysis/validation.py`](file:///d:/VinUni-UROP/abides/analysis/validation.py): Automated validation gate checker implementing 4 gates:
  1. **Gate 1 — Mechanics-Identity Audit**: Asserts C2 vs C3 (and C4 vs C5) have identical decision counts and order quantities.
  2. **Gate 2 — Pairing Audit**: Verifies fundamental value path consistency across conditions within a seed/regime.
  3. **Gate 3 — Order Lifecycle Integrity**: Every ORDER_ACCEPTED must resolve to EXECUTED or CANCELLED.
  4. **Gate 4 — LLM Health Check**: LLM parse-failure/fallback rate must be < 10%.

#### How To Run (for your teammate)

**Step 1: Run the pilot matrix** (3 seeds × 10 cells = 30 runs; LLM cells require Ollama running locally):
```bash
cd abides
python run_matrix.py --phase pilot
```

**Step 2: Run the validation gates:**
```bash
python -m analysis.validation --phase pilot
```

> **⚠ Note:** LLM cells (C3 and C5) require a local Ollama instance serving `gemma3:4b`. Non-LLM cells (C1, C2, C4) complete in ~4–5 seconds each. LLM cells take ~60–240 seconds each depending on wake interval.

---

### ⚪ Milestone 6: Full Matrix Execution & Statistical Analysis

#### Goal
Run the full 300-run experimental matrix (30 seeds × 10 cells), compute primary and secondary market metrics, and perform paired difference analysis.

#### Deliverables To Build
- `abides/analysis/metrics.py`: Computes time-weighted spread, midpoint error, depth at touch, recovery time.
- `abides/analysis/paired_diffs.py`: Calculates paired differences (`C3-C2`, `C5-C4`, etc.), 95% CIs, and Wilcoxon tests.
- `abides/analysis/event_study.py`: Shock trajectory event study plots.

#### Verification Commands
```bash
python run_matrix.py --phase final
python -m analysis.metrics abides/output/raw/ abides/output/results/
python -m analysis.paired_diffs abides/output/results/
```
