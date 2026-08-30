# Market Impact of an LLM Directional Policy in an ABIDES Limit-Order Market

## Technical Pilot Report

**Authors:** Nguyen Quy Tu and Nguyen Minh Nghia  
**Date:** 31 August 2026  
**Study stage:** Milestone 5 technical pilot  
**Pilot seeds:** 1001, 1002, and 1003

## Abstract

This technical pilot evaluates whether a language-model trading policy changes market
quality after its mechanical behavior is held fixed. A Gemma 3 4B policy and a fair-coin
policy were placed inside the same wrapper, which fixed wake frequency, cancellation,
order size, quote placement, and mandatory participation. Five agent conditions were run
under normal and fundamental-shock regimes for three paired seeds, producing 30 simulated
market sessions. The primary estimand was the within-seed LLM-minus-coin policy effect at
60-second and 300-second decision intervals.

All three seed reports record complete 10-cell matrices and 150/150 validation checks. Across
2,592 model calls, no invalid response, fallback, or timeout occurred. In normal markets,
the mean 60-second LLM policy effect was +21.75 cents on midpoint error, +26.91 cents on
spread, and -7.35 percentage points on two-sided availability; all corresponding 95%
intervals included zero. At 300 seconds the normal-market effects were smaller and mixed.
Under shock, full-session conditional averages favored the LLM on error and spread, but
these averages omitted periods without two-sided quotes. During the first 30 minutes after
the shock, the 60-second LLM increased error by 391.68 cents and reduced availability by
17.50 points on average, with extreme between-seed variation: seeds 1001 and 1002 suffered
severe availability loss, whereas seed 1003 retained full availability. The pilot therefore
validates the implementation but does not establish a stable beneficial or harmful LLM
effect. Its main scientific result is that market impact must be assessed jointly with
availability and across many paired seeds. A frozen 30-seed final experiment remains
necessary.

## 1. Research question

The study asks:

> After controlling for decision frequency, cancellation behavior, order size, and quote
> placement, how does an LLM-based directional policy affect liquidity, price efficiency,
> volatility, and recovery from a fundamental-value shock?

The outcome is market quality, not the treatment agent's profit. The LLM controls only the
choice between `BUY` and `SELL`. Its schedule and order mechanics are identical to those of
the matched fair-coin control.

## 2. Experimental design

### 2.1 Conditions

| Condition | Agent in treatment slot | Frequency | Directional policy |
|---|---|---:|---|
| C1 | Canonical ABIDES ZI agent | Native | Canonical ZI |
| C2 | Fixed wrapper | 60 s | Fair coin |
| C3 | Fixed wrapper | 60 s | Gemma 3 4B |
| C4 | Fixed wrapper | 300 s | Fair coin |
| C5 | Fixed wrapper | 300 s | Gemma 3 4B |

Each condition was run in a normal regime (`-N`) and in a regime with an upward fundamental
jump at 12:30 (`-S`). Treatment activity began after a 09:30–10:00 warmup, and outcomes were
measured from 10:00 through 16:00.

### 2.2 Causal contrasts

For each seed and regime, effects were calculated before averaging across seeds:

- **Footprint:** `C2-C1` at 60 seconds or `C4-C1` at 300 seconds.
- **Policy:** `C3-C2` at 60 seconds or `C5-C4` at 300 seconds.
- **Total:** `C3-C1` at 60 seconds or `C5-C1` at 300 seconds.
- **Frequency interaction:** `(C3-C2) - (C5-C4)`.
- **Regime interaction:** policy effect under shock minus policy effect under normal
  conditions.

The policy contrast is the headline estimand because the wrapper mechanics are identical
between its treatment and control arms. C1 is a reference market used to decompose the
mechanical footprint; it is not the causal control for the LLM policy.

### 2.3 Outcomes

Primary outcomes were time-weighted absolute midpoint error, quoted spread, depth at the
touch, two-sided book availability, and provisional recovery time after shock. Midpoint
error and spread are reported in cents; depth is displayed shares; availability is a
percentage; and recovery is minutes after the shock.

Secondary outcomes were five-minute realized volatility, trades, volume, treatment fill
rate, inventory, marked PnL, directional-policy quality, and LLM operational health.

Midpoint error, spread, and depth require a two-sided book. They are therefore conditional
on quote availability. A low conditional error is not favorable if the market is one-sided
during its most impaired periods.

## 3. Data provenance and statistical method

All three seeds were recomputed from their committed or locally generated Parquet logs using
the same analysis code. The pushed `seed1002_summary.json` was also compared with an
independent recomputation from seed-1002 Parquet files; every common numeric field matched.
The raw logs are therefore the authoritative source for the aggregate.

Each reported effect was computed within seed and then summarized across the three seeds.
The tables give the arithmetic mean and a two-sided 95% Student-t interval with two degrees
of freedom. With only three paired observations, these intervals are necessarily wide and
should be interpreted as pilot precision diagnostics. Confirmatory p-values and BCa
bootstrap intervals are not reported: at this sample size they would imply unjustified
inferential precision. The pilot seeds were designated for validation and variance planning,
not for the final hypothesis test.

## 4. Validation results

Each seed completed all ten cells. The seed reports record **150/150 validation checks per
seed**, covering:

- required outputs and manifest identity;
- exact wrapper cadence, fixed order size, at-touch placement, and forced submission;
- matched schedules and submission counts between coin and LLM arms;
- identical within-regime fundamental paths and matched pre-treatment background streams;
- ordered, unique, non-crossed L1 snapshots and correct midpoint arithmetic;
- hand-calculated metric fixtures;
- complete terminal order lifecycles and inventory reconciliation; and
- LLM response validity, fallback consistency, and timeouts.

The checks were reproduced locally from raw data for all three seeds.

## 5. Per-condition market outcomes

Values are three-seed means. Availability is the mean percentage of the measured session
with both a bid and an ask.

| Cell | Midpoint error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| C1-N | 229.79 | 120.70 | 143.82 | 89.21% |
| C2-N | 209.39 | 144.71 | 205.58 | 88.14% |
| C3-N | 231.14 | 171.62 | 219.29 | 80.79% |
| C4-N | 218.20 | 151.64 | 206.14 | 87.88% |
| C5-N | 223.05 | 140.47 | 217.66 | 89.74% |
| C1-S | 856.22 | 297.50 | 149.95 | 88.55% |
| C2-S | 1,128.97 | 863.24 | 221.04 | 76.12% |
| C3-S | 612.34 | 277.33 | 215.41 | 72.14% |
| C4-S | 943.11 | 652.37 | 218.71 | 84.77% |
| C5-S | 849.42 | 321.65 | 217.81 | 83.51% |

The shock-regime C3 mean appears favorable on conditional error and spread, but it combines
low values from valid two-sided intervals with the lowest mean availability in the matrix.
It cannot be interpreted independently of the event-window results in Section 8.

## 6. Paired decomposition in the normal regime

Each entry is `mean [95% CI]`. Negative error and spread favor the first-named treatment;
positive depth and availability generally favor it. Availability is in percentage points.

| Effect | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Footprint 60s | -20.40 [-62.71, 21.92] | +24.01 [12.88, 35.13] | +61.76 [40.70, 82.81] | -1.07 [-18.40, 16.26] pp |
| Policy 60s | +21.75 [-41.12, 84.62] | +26.91 [-26.81, 80.63] | +13.71 [5.44, 21.99] | -7.35 [-21.33, 6.64] pp |
| Total 60s | +1.35 [-103.05, 105.76] | +50.92 [-13.51, 115.34] | +75.47 [61.58, 89.36] | -8.42 [-37.73, 20.89] pp |
| Footprint 300s | -11.58 [-22.48, -0.69] | +30.94 [-72.22, 134.10] | +62.32 [33.86, 90.79] | -1.33 [-10.62, 7.97] pp |
| Policy 300s | +4.85 [-65.84, 75.54] | -11.17 [-84.16, 61.82] | +11.51 [-58.82, 81.85] | +1.85 [-15.22, 18.93] pp |
| Total 300s | -6.74 [-85.44, 71.97] | +19.77 [-14.59, 54.14] | +73.84 [19.98, 127.70] | +0.53 [-24.76, 25.82] pp |

The most stable normal-regime result is mechanical: the wrapper increased depth and widened
spread relative to canonical C1 at both frequencies. The LLM policy contribution was much
less stable. At 60 seconds its mean direction was worse for error, spread, and availability;
at 300 seconds the mean effects were smaller and mixed. Error, spread, and availability
policy intervals included zero at both frequencies. The 60-second depth interval was
positive, but this did not offset its simultaneous spread and availability directions.

## 7. Paired decomposition in the shock regime

| Effect | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Footprint 60s | +272.75 [-141.95, 687.45] | +565.74 [-422.64, 1,554.12] | +71.09 [33.41, 108.77] | -12.43 [-27.79, 2.94] pp |
| Policy 60s | -516.63 [-1,269.29, 236.03] | -585.91 [-1,320.36, 148.53] | -5.63 [-45.16, 33.90] | -3.98 [-29.31, 21.34] pp |
| Total 60s | -243.88 [-628.38, 140.63] | -20.17 [-411.37, 371.02] | +65.45 [-11.74, 142.65] | -16.41 [-30.78, -2.04] pp |
| Footprint 300s | +86.88 [-510.30, 684.06] | +354.87 [-128.96, 838.69] | +68.75 [0.93, 136.58] | -3.77 [-9.47, 1.92] pp |
| Policy 300s | -93.69 [-474.27, 286.89] | -330.72 [-944.41, 282.97] | -0.89 [-48.83, 47.04] | -1.26 [-11.47, 8.95] pp |
| Total 300s | -6.81 [-332.47, 318.85] | +24.15 [-153.33, 201.62] | +67.86 [31.14, 104.58] | -5.03 [-17.87, 7.80] pp |

The full-session conditional means suggest that the LLM reduced error and spread relative
to coin under shock, especially at 60 seconds. However, the mean 60-second policy also
reduced availability. The event window shows that the apparent error advantage is partly a
selection effect: high-error one-sided periods are omitted from conditional averages.

## 8. Shock resilience

### 8.1 Three-seed condition means

The event window covers the first 30 minutes after the upward shock. Recovery uses each
seed's provisional threshold of one empirical pre-shock fundamental standard deviation and
requires 60 continuous seconds inside that threshold.

| Cell | First-30m error | First-30m availability | Recovery | Overshoot |
|---|---:|---:|---:|---:|
| C1-S | 5,564.39 | 88.00% | 86.8 min | 0.00 |
| C2-S | 6,866.75 | 56.22% | 96.4 min | 0.00 |
| C3-S | 7,258.43 | 38.74% | 86.5 min | 0.00 |
| C4-S | 6,270.27 | 56.54% | 92.2 min | 0.00 |
| C5-S | 5,538.75 | 77.31% | 89.1 min | 0.00 |

No condition overshot above the evolving fundamental. The dominant failure mode was delayed
adjustment or temporary loss of a two-sided market, not excessive movement beyond value.

### 8.2 Matched LLM-minus-coin shock-window effects

| Frequency | Outcome | Seed 1001 | Seed 1002 | Seed 1003 | Mean [95% CI] |
|---:|---|---:|---:|---:|---:|
| 60s | Error (cents) | +623.33 | +1,314.12 | -762.41 | +391.68 [-2,235.21, 3,018.58] |
| 60s | Availability | -50.50 pp | -35.22 pp | +33.28 pp | -17.50 [-128.30, 93.40] pp |
| 60s | Recovery | -6.6 min | 0.0 min | -23.1 min | -9.9 [-39.5, 19.7] min |
| 300s | Error (cents) | +925.91 | -3,054.72 | -65.74 | -731.52 [-5,879.02, 4,415.98] |
| 300s | Availability | +3.00 pp | +59.33 pp | 0.00 pp | +20.78 [-62.20, 103.80] pp |
| 300s | Recovery | +1.5 min | +11.6 min | -22.6 min | -3.2 [-46.7, 40.4] min |

The 60-second result changes sign across seeds. Seeds 1001 and 1002 show severe immediate
LLM-associated availability loss and worse price tracking; seed 1003 shows the opposite.
The 300-second LLM maintained or improved immediate availability in all three seeds, but its
error and recovery effects were still inconsistent. With (n=3), neither frequency supports
a general shock-resilience claim.

## 9. Frequency and regime interactions

| Interaction | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Frequency, normal | +16.90 [-36.93, 70.73] | +38.08 [-61.41, 137.57] | +2.20 [-60.31, 64.70] | -9.20 [-19.64, 1.24] pp |
| Frequency, shock | -422.94 [-1,545.52, 699.64] | -255.19 [-900.63, 390.25] | -4.74 [-88.65, 79.18] | -2.72 [-18.08, 12.63] pp |
| Shock-minus-normal, 60s | -538.38 [-1,346.62, 269.86] | -612.82 [-1,308.60, 82.95] | -19.34 [-52.64, 13.96] | +3.37 [-35.54, 42.27] pp |
| Shock-minus-normal, 300s | -98.54 [-423.57, 226.50] | -319.55 [-935.72, 296.62] | -12.41 [-119.13, 94.31] | -3.11 [-28.44, 22.21] pp |

The mean error and spread interactions suggest that state-contingent LLM behavior may matter
more under shock, especially at 60 seconds. None of the pilot intervals excludes zero, and
the availability interaction does not establish a corresponding resilience improvement.

## 10. Secondary market and agent outcomes

Values are three-seed means. PnL is marked to the closing fundamental and remains a
secondary treatment-agent diagnostic.

| Cell | RV (bps) | Trades | Volume | Fill rate | Mean abs. inventory | Terminal inventory | Marked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1-N | 63.14 | 138.0 | 2,052.3 | 16.36% | 105.43 | +71.0 | -$412.07 |
| C2-N | 75.08 | 387.7 | 3,914.0 | 3.27% | 297.08 | -403.3 | +$382.34 |
| C3-N | 78.46 | 363.3 | 3,626.3 | 2.38% | 216.42 | +555.3 | +$2,544.63 |
| C4-N | 76.60 | 176.0 | 2,637.7 | 9.97% | 143.17 | -206.0 | +$599.13 |
| C5-N | 54.31 | 181.0 | 2,666.3 | 10.82% | 135.63 | +394.0 | +$2,411.12 |
| C1-S | 397.70 | 140.3 | 2,278.0 | 21.44% | 122.99 | +120.7 | +$8,098.52 |
| C2-S | 623.41 | 354.7 | 4,436.3 | 4.79% | 531.43 | -1,017.3 | -$44,945.97 |
| C3-S | 187.89 | 330.3 | 3,530.0 | 1.80% | 84.11 | +178.0 | +$5,129.63 |
| C4-S | 568.63 | 174.0 | 2,812.0 | 11.98% | 318.05 | -722.3 | -$23,200.78 |
| C5-S | 312.96 | 169.0 | 2,465.7 | 7.65% | 81.82 | -38.7 | +$3,353.00 |

The high-frequency wrapper accounts for most of the increase in trades and volume relative
to C1. Under shock, the coin controls accumulated large negative inventory and PnL on
average, while the LLM arms carried less absolute inventory. These agent outcomes are
consistent with different directional behavior but do not substitute for market-quality
outcomes.

Realized volatility is especially sensitive to missing two-sided-book observations. The low
C3-S mean must not be described as unconditionally low volatility because seeds 1001 and
1002 had fewer valid adjacent five-minute returns in that cell.

## 11. Directional-policy and operational diagnostics

### 11.1 Fundamental-correcting side choices

The entries below are unweighted means of each seed's LLM-minus-coin correcting-side rate.

| Regime and frequency | Whole session | ±30-minute shock window |
|---|---:|---:|
| Normal, 60s | +0.47 pp | — |
| Normal, 300s | +2.31 pp | — |
| Shock, 60s | -0.34 pp | -8.66 pp |
| Shock, 300s | +8.34 pp | -3.70 pp |

There is no consistent evidence that the LLM chose a more fundamental-correcting direction
during the shock window. This helps explain why operationally valid outputs did not produce
a stable resilience benefit.

### 11.2 LLM health

| Cell | Calls across seeds | Invalid/fallback | Timeout | Mean seed p50 | Mean seed p95 | Total tokens |
|---|---:|---:|---:|---:|---:|---:|
| C3-N | 1,080 | 0% | 0% | 1,561 ms | 1,655 ms | 159,151 |
| C5-N | 216 | 0% | 0% | 1,549 ms | 1,622 ms | 31,734 |
| C3-S | 1,080 | 0% | 0% | 1,551 ms | 1,668 ms | 159,427 |
| C5-S | 216 | 0% | 0% | 1,553 ms | 1,734 ms | 31,962 |
| **Total** | **2,592** | **0%** | **0%** | — | — | **382,274** |

The latency columns average the seed-level cell percentiles so each seed receives equal
weight; they are not pooled-call percentiles. Model delivery was fully reliable, so market
heterogeneity cannot be attributed to parse failures or timeouts.

## 12. Pilot precision and the planned final sample

Using the pilot standard deviation of each paired policy effect, the projected 95% CI
half-width for 30 final seeds is:

| Regime | Frequency | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|---:|
| Normal | 60s | 9.45 cents | 8.07 cents | 1.24 shares | 2.10 pp |
| Normal | 300s | 10.62 cents | 10.97 cents | 10.57 shares | 2.57 pp |
| Shock | 60s | 113.12 cents | 110.39 cents | 5.94 shares | 3.81 pp |
| Shock | 300s | 57.20 cents | 92.24 cents | 7.20 shares | 1.53 pp |

These projections use a 30-seed t critical value and assume the pilot variance generalizes.
The shock outcomes require much wider intervals than the normal outcomes. Thirty seeds
would materially improve precision, but whether the projected half-width is scientifically
adequate cannot be decided until a minimally important effect is declared. The final design
should retain at least the planned 30 paired seeds and pre-register acceptable precision
before execution.

## 13. Discussion

### 13.1 Mechanical activity and directional reasoning are distinct

The most repeatable pilot pattern is the wrapper footprint: relative to the canonical ZI
market, fixed-frequency cancel-and-replace activity generally increased displayed depth,
spread, trades, and volume. Consequently, an unmatched C3-versus-C1 comparison would mix
mechanical churn with the LLM's directional policy. The coin control is essential.

### 13.2 Full-session shock averages can be misleading

The 60-second LLM appears to improve shock-regime error and spread in the full-session table.
Yet its immediate shock-window error was worse on average and its availability collapsed in
two of three seeds. Conditional market metrics selectively exclude exactly the intervals in
which a two-sided market disappeared. The final analysis should treat availability as a
co-primary outcome and add a pre-specified robustness metric that penalizes or otherwise
accounts for missing midpoints.

### 13.3 Lower frequency may be safer, but the evidence is preliminary

The 300-second LLM maintained or improved immediate shock-window availability in every pilot
seed and had a favorable mean shock-window error. However, recovery and error effects still
changed sign, and all corresponding intervals were very wide. The pilot motivates the
frequency interaction; it does not resolve it.

### 13.4 Valid model output is not equivalent to useful reasoning

All responses were valid and timely, but fundamental-correcting side rates were inconsistent.
The market differences therefore reflect genuine variation in the model's valid directional
choices and their interaction with the endogenous order book, rather than a broken output
parser.

## 14. Limitations

1. The sample contains only three paired seeds and was designated for technical validation.
2. Conditional midpoint, spread, depth, and volatility metrics can look favorable when the
   book is unavailable. Availability must be analyzed jointly.
3. The recovery threshold remains provisional and was derived separately from each seed's
   pre-shock fundamental variation.
4. The experiment uses one model, one prompt, one market configuration, one asset, and an
   upward shock only; external validity is therefore limited.
5. Three seeds are insufficient for the final BCa bootstrap, Wilcoxon robustness test, or a
   reliable event-study band.
6. PnL and inventory are endogenous agent diagnostics, not causal measures of market
   quality.

## 15. Protocol decisions before the final run

Before running seeds 2001–2030, the following items should be completed and frozen:

1. Archive all three validated pilot log sets and their checksums.
2. Freeze the recovery threshold and holding period.
3. Pre-specify how midpoint error and volatility handle one-sided-book intervals; retain
   availability as a co-primary outcome.
4. Record the exact model digest, prompt version, configuration, code commit, and metric
   definitions in `FREEZE.md`.
5. Declare minimally important effects or acceptable CI half-widths for sample-size review.
6. Run the final 30 paired seeds in seed-outermost order without changing the frozen policy
   or metric code.

## 16. Conclusion

Milestone 5 succeeds technically: the paired experiment runs, mechanics are matched, market
logs reconcile, metrics pass sanity checks, and the local LLM produces valid deterministic
actions. The pilot does not show a stable LLM benefit. Normal-market policy effects are
mixed, and shock-market conclusions depend strongly on seed, frequency, and whether missing
two-sided intervals are considered. The 60-second shock arm is particularly unstable,
ranging from severe availability collapse to full availability across only three seeds.

The defensible conclusion is therefore methodological rather than promotional: an LLM's
market impact cannot be inferred from agent profitability, valid response rates, or
conditional price error alone. It requires an activity-matched control, paired seeds,
joint analysis of price quality and book availability, and a sufficiently large frozen
experiment. The validated pilot supports proceeding to that final stage after the remaining
freeze decisions are documented.

## Reproducibility statement

Seed-level reports are stored in `MILESTONE5_SEED1001_RESULTS.md`,
`MILESTONE5_SEED1002_RESULTS.md`, and `MILESTONE5_SEED1003_RESULTS.md`. Raw logs for seeds
1001–1003 are under `abides/output/raw/<cell>/<seed>/`. The aggregation logic is in
`abides/analysis/aggregate_pilot.py`; its generated machine-readable result is
`abides/output/results/pilot_aggregate.json`.
