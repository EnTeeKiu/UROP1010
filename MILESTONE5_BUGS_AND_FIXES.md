# Milestone 5 Seed-1001 Bug and Fix Report

**Date:** August 30, 2026  
**Scope:** strict validator repair, one-seed 10-cell technical pilot, iterative fixes  
**Final status:** all 10 cells ran successfully; all 150 strict validation checks passed

## Summary

The original Milestone 5 implementation could execute simulations, but its validator was
not strong enough to establish the blueprint's invariants. The work therefore included both
validator hardening and fixes to logging, orchestration, the fundamental oracle, and L1 book
extraction. A diagnostic matrix exposed experiment-level defects, after which a clean matrix
was run from scratch with the corrected code.

## Bugs encountered and resolutions

| # | Bug | Evidence / impact | Resolution | Verification |
|---|---|---|---|---|
| 1 | Missing outputs were treated as successful validation checks. | The old validator returned PASS when both paired files were absent or when fewer than two cells had data. An incomplete pilot could therefore report success. | Added Gate 0 and changed all missing manifests, Parquet files, empty required datasets, and missing paired cells to hard failures. | A deliberate no-data run failed every data-dependent gate and produced a report instead of passing. |
| 2 | Missing-file error reporting crashed. | The new strictness test raised `TypeError` because a manually constructed `FileNotFoundError` had no `.filename`. | Raised the exception with errno, message, and path so `.filename` is populated. | The repeated no-data test completed and listed missing files without a traceback. |
| 3 | The original gates only partially represented the blueprint. | Mechanics checked only decision counts/quantity; pairing checked only an initial value; metric hand-check, timeout enforcement, inventory reconciliation, and strict completeness were absent. | Rebuilt `analysis/validation.py` with completeness, mechanics, exact pairing, market-data integrity, metric sanity, lifecycle/inventory, and LLM health gates. | Final result: 150/150 checks passed. |
| 4 | Required diagnostic fields were not logged. | Placement, timeouts, token use, actual submit/cancel requests, and treatment inventory state could not be audited. | Added snapshot best quotes, timeout/tokens, separate lifecycle and placement timestamps, `treatment_requests.parquet`, and `agent_state.parquet`. Empty standardized outputs are now written too. | All 10 cells produced all required standardized files and passed schema-dependent gates. |
| 5 | The OpenAI SDK silently retried model calls. | A cold live request took about 74 seconds despite a 30-second timeout, violating the one-call/no-retry protocol. | Constructed the client with `max_retries=0` and a fixed 30-second timeout; added explicit timeout classification. | All 864 clean LLM decisions used one call each; fallback and timeout rates were both 0%. |
| 6 | Windows console encoding crashed the matrix before its first run. | CP1252 could not encode Unicode box-drawing/status characters in `run_matrix.py`. | Replaced runner console output with portable ASCII. | Both subsequent 10-cell matrices completed normally. |
| 7 | Matrix extraction failures did not fail the matrix. | `extract_logs()` returned `False`, but the failure counter was not incremented. | Recorded `extraction_success` and count extraction failure as a matrix failure. | The clean summary reports 10/10 simulation and extraction successes. |
| 8 | Final seed constants contradicted the configuration. | `run_matrix.py` used 1001–1030 for final runs while the configuration and blueprint reserve final seeds beginning at 2001. | Changed final seeds to 2001–2030. | Runner and validator now use the same final range. |
| 9 | The validator equated submissions with `ORDER_ACCEPTED`. | C2-N had 360 decisions but only 353 acceptances because immediately executed orders may never emit an accepted event. | Extracted the treatment agent's actual `ORDER_SUBMITTED` events and matched them chronologically to wrapper decisions. | Every wrapper cell has one matching submission for each of its 360 or 72 decisions. |
| 10 | Exact timestamp/cancellation-count assumptions were invalid. | Decision timestamps differed by at most 50 ns due to message latency. Successful cancel counts differed when one policy's prior order filled before the next wake. | Applied a 1-microsecond schedule tolerance and validate cancel-all behavior per arm: unique prior submitted order, at most one cancellation request per wake, no duplicate request. | All paired wake counts/schedules, submission counts, and per-arm cancellation contracts passed. |
| 11 | Resting orders had no terminal lifecycle event at market close. | Five accepted orders remained unresolved in early C1-N and C2-N checks even though fill-to-inventory reconciliation was exact. | The extractor now reconstructs remaining quantity and records it as `EXPIRED` at session end. | Every accepted order in all 10 cells is executed, cancelled, or expired; all treatment inventories reconcile exactly. |
| 12 | The sparse oracle violated paired fundamentals. | First-pass fundamental rows and hashes differed across conditions because the oracle advanced its RNG on agent queries. Treatment-driven event differences therefore changed the exogenous path. | Added `PairedFundamentalOracle`, which precomputes a one-second path before the simulation and applies the fixed shock at 12:30. | Each regime now has an identical 23,401-row hash across C1–C5; pre-treatment background streams also match. |
| 13 | L1 extraction retained stale quotes and created impossible crossed books. | Event reconstruction produced negative spreads (for example 163 crossed observations in first-pass C3-S) because ABIDES does not emit an event when one side becomes empty. | Rebuilt L1 extraction from the complete one-second order-book depth snapshot: highest negative-volume quote is best bid; lowest positive-volume quote is best ask. Added a hard market-data gate. | Every cell has 23,400 ordered unique snapshots, correct midpoint arithmetic, and zero crossed observations. |
| 14 | Time-weighted metrics carried values across missing-book intervals. | Dropping `NA` observations before weighting treated a previous spread/midpoint as valid while the book was one-sided. | The metric primitive now preserves interval boundaries and excludes undefined intervals from the weighted denominator. | Hand-calculated metric tests and a dedicated missing-interval regression test pass. |
| 15 | Seed summary failed on nullable coin diagnostics. | Coin rows contain standardized LLM fields filled with `NA`; Pandas could not cast their empty mean to `float`. | LLM statistics are calculated only when non-null diagnostics exist. | The reproducible 10-cell seed summary completes successfully. |

## Final verification

- Clean matrix: **10/10 cells succeeded**, with Parquet extraction for every cell.
- Output completeness: **20/20**.
- Mechanics identity: **64/64**.
- Pairing audit: **6/6**.
- Market-data integrity: **20/20**.
- Hand-calculated metric sanity: **4/4**.
- Lifecycle and inventory integrity: **20/20**.
- LLM health: **16/16**.
- Regression tests: **4/4**.

The machine-readable validation result is `abides/output/results/validation_report_custom.json`.

## Scope note

This report covers the requested one-seed integration pilot. The blueprint's full technical
pilot still requires seeds 1002 and 1003, followed by variance review and the formal freeze.

