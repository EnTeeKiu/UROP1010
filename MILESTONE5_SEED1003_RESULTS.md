# Milestone 5 Seed-1003 Market-Impact Results

**Seed:** 1003  
**Matrix:** five conditions x normal/shock regimes = 10 cells  
**Analysis window:** 10:00–16:00; 09:30–10:00 warmup excluded  
**Status:** technical-pilot diagnostic, not an estimate of the population effect

## 1. Research question and estimands

The experiment asks how an LLM directional policy affects the **market**, after holding
decision frequency, cancellation behavior, order size, and quote placement fixed. It does
not primarily ask whether Gemma is a profitable trader.

The analysis separates three effects at each frequency:

- **Footprint:** coin wrapper minus canonical ZI (`C2-C1` or `C4-C1`).
- **Policy:** LLM wrapper minus matched coin wrapper (`C3-C2` or `C5-C4`).
- **Total:** LLM wrapper minus canonical ZI (`C3-C1` or `C5-C1`).

The frequency interaction is `(C3-C2) - (C5-C4)`. The regime interaction compares a policy
effect under shock with the corresponding policy effect under normal conditions.

## 2. Data and validation integrity

All 10 simulations and Parquet extractions completed. The strict validator passed
**150/150 checks**. In particular:

- fundamental paths were identical across C1–C5 within each regime;
- pre-treatment background streams matched;
- wrapper cadence, size, placement, and forced submissions matched exactly;
- all order lifecycles were terminal and fills reconciled with inventory;
- all 234,000 L1 snapshots were ordered and no crossed quote was observed; and
- all 864 LLM responses were valid, with no fallback or timeout.

Metric conventions:

- midpoint error, spread, and depth are time-weighted over valid two-sided L1 intervals;
- availability is the session fraction with both a bid and an ask;
- midpoint error and spread are cents, while depth is displayed shares; and
- five-minute realized volatility is `sqrt(sum(log-return^2))` in basis points, with missing
  bins breaking the return chain.

Because the primary conditional metrics omit one-sided intervals, they must always be read
together with book availability.

## 3. Per-condition market outcomes

| Cell | Midpoint error | Spread | Depth | Availability | RV (bps) | Valid 5m returns |
|---|---:|---:|---:|---:|---:|---:|
| C1-N: canonical baseline | 265.84 | 156.24 | 141.88 | 90.58% | 67.03 | 70 |
| C2-N: coin 60s | 226.03 | 176.17 | 210.62 | 88.66% | 99.75 | 69 |
| C3-N: LLM 60s | 220.99 | 188.90 | 222.91 | 76.51% | 80.72 | 61 |
| C4-N: coin 300s | 249.56 | 212.67 | 214.09 | 91.06% | 91.77 | 70 |
| C5-N: LLM 300s | 224.29 | 178.36 | 223.41 | 91.56% | 64.69 | 67 |
| C1-S: canonical baseline | 1,086.54 | 549.90 | 154.56 | 90.39% | 494.99 | 69 |
| C2-S: coin 60s | 1,183.62 | 899.92 | 230.85 | 73.94% | 634.59 | 55 |
| C3-S: LLM 60s | 1,015.28 | 360.87 | 230.08 | 80.60% | 449.67 | 62 |
| C4-S: coin 300s | 1,383.58 | 1,036.07 | 232.44 | 88.61% | 871.07 | 64 |
| C5-S: LLM 300s | 1,116.38 | 491.81 | 214.93 | 91.25% | 377.56 | 70 |

## 4. Effect decomposition

Negative differences improve midpoint error and spread. Positive differences generally
improve depth and availability. Availability differences are percentage points.

### Normal regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-N - C1-N | -39.81 | +19.93 | +68.74 | -1.93 pp |
| 60s | Policy | C3-N - C2-N | -5.04 | +12.73 | +12.29 | -12.14 pp |
| 60s | Total | C3-N - C1-N | -44.85 | +32.66 | +81.03 | -14.07 pp |
| 300s | Footprint | C4-N - C1-N | -16.28 | +56.43 | +72.21 | +0.48 pp |
| 300s | Policy | C5-N - C4-N | -25.27 | -34.30 | +9.33 | +0.49 pp |
| 300s | Total | C5-N - C1-N | -41.55 | +22.13 | +81.53 | +0.97 pp |

At 60 seconds, the LLM slightly reduced conditional error and added depth, but widened the
spread and caused a large 12.14-point availability loss. The 300-second policy improved all
four displayed outcomes for this seed.

### Shock regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-S - C1-S | +97.08 | +350.03 | +76.29 | -16.45 pp |
| 60s | Policy | C3-S - C2-S | -168.33 | -539.05 | -0.78 | +6.67 pp |
| 60s | Total | C3-S - C1-S | -71.26 | -189.03 | +75.51 | -9.79 pp |
| 300s | Footprint | C4-S - C1-S | +297.04 | +486.17 | +77.87 | -1.78 pp |
| 300s | Policy | C5-S - C4-S | -267.20 | -544.26 | -17.51 | +2.64 pp |
| 300s | Total | C5-S - C1-S | +29.84 | -58.09 | +60.36 | +0.86 pp |

Unlike seeds 1001 and 1002, the 60-second LLM policy did not collapse availability after the
shock in seed 1003. Both LLM frequencies substantially narrowed the full-session shock
spread and reduced midpoint error relative to their matched coin controls. The 300-second
policy traded some depth for these improvements.

## 5. Frequency and regime interactions

| Interaction | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Frequency interaction, normal | +20.23 | +47.03 | +2.96 | -12.63 pp |
| Frequency interaction, shock | +98.87 | +5.20 | +16.73 | +4.03 pp |
| Shock-minus-normal policy interaction, 60s | -163.29 | -551.78 | -13.06 | +18.80 pp |
| Shock-minus-normal policy interaction, 300s | -241.93 | -509.96 | -26.84 | +2.15 pp |

For seed 1003, LLM policy effects were more favorable under shock than in the normal regime,
especially for spread. This is a single-seed interaction and cannot establish a stable
effect.

## 6. Shock resilience and event-window behavior

The upward fundamental shock occurs at 12:30. The event window below is 12:30–13:00.
Recovery is the first time the midpoint stays within **328.36 cents** of the evolving
fundamental for 60 consecutive seconds. The threshold is one empirical pre-shock
fundamental standard deviation and remains **provisional**.

| Cell | Error, first 30m | Two-sided availability, first 30m | Recovery | Upward overshoot |
|---|---:|---:|---:|---:|
| C1-S | 6,764.04 | 100.00% | 78.5 min | 0.00 |
| C2-S | 6,555.46 | 66.72% | 101.5 min | 0.00 |
| C3-S | 5,793.05 | 100.00% | 78.4 min | 0.00 |
| C4-S | 6,952.04 | 100.00% | 101.5 min | 0.00 |
| C5-S | 6,886.30 | 100.00% | 78.9 min | 0.00 |

- At 60 seconds, the LLM reduced first-30-minute error by 762.41 cents, increased
  availability by 33.28 points, and met the provisional recovery criterion 23.1 minutes
  earlier than the coin control.
- At 300 seconds, both books remained continuously two-sided. The LLM reduced error by
  65.74 cents and met the provisional criterion 22.6 minutes earlier.
- Overshoot was zero in every condition; the market underreacted to the upward shock rather
  than moving above the evolving fundamental.

These favorable seed-1003 event-window results conflict with the poor C3-S event windows in
seeds 1001 and 1002. That heterogeneity is itself a central pilot finding.

## 7. Volatility, activity, inventory, and PnL

| Cell | RV bps (obs.) | Market trades | Market volume | Treatment fill rate | Mean abs. inventory | Terminal inventory | Marked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1-N | 67.03 (70) | 137 | 2,776 | 22.36% | 186.14 | +371 | -$625.33 |
| C2-N | 99.75 (69) | 395 | 5,028 | 3.20% | 152.55 | -101 | +$633.23 |
| C3-N | 80.72 (61) | 352 | 4,659 | 3.06% | 312.16 | +642 | -$651.41 |
| C4-N | 91.77 (70) | 165 | 3,168 | 11.56% | 115.26 | -372 | -$129.62 |
| C5-N | 64.69 (67) | 165 | 2,674 | 7.24% | 74.70 | +143 | +$216.15 |
| C1-S | 494.99 (69) | 137 | 3,161 | 36.28% | 273.47 | +545 | +$28,364.37 |
| C2-S | 634.59 (55) | 359 | 5,551 | 5.19% | 389.03 | -1,028 | -$8,003.87 |
| C3-S | 449.67 (62) | 376 | 4,806 | 2.72% | 66.94 | +245 | +$6,627.72 |
| C4-S | 871.07 (64) | 174 | 3,682 | 13.19% | 255.01 | -750 | -$10,582.86 |
| C5-S | 377.56 (70) | 169 | 2,951 | 9.83% | 91.41 | -214 | +$1,497.90 |

The active wrapper again produced most of the trading-volume increase relative to C1.
Within the wrapper, the LLM reduced volatility relative to coin in all four matched pairs in
this seed. PnL is included only as a treatment-agent diagnostic and is not a primary outcome.

## 8. Directional-policy diagnostic

| Pair | Coin | LLM | LLM - coin |
|---|---:|---:|---:|
| Normal, 60s | 52.38% | 68.08% | +15.70 pp |
| Normal, 300s | 49.18% | 60.61% | +11.43 pp |
| Shock, 60s, whole session | 49.62% | 52.78% | +3.16 pp |
| Shock, 60s, ±30m | 37.50% | 25.00% | -12.50 pp |
| Shock, 300s, whole session | 46.77% | 62.12% | +15.35 pp |
| Shock, 300s, ±30m | 33.33% | 58.33% | +25.00 pp |

The LLM was more fundamental-correcting overall in all four matched comparisons, but not in
the 60-second shock window. Side quality is a mechanism diagnostic, not the outcome itself.

## 9. LLM operational diagnostics

| Cell | Calls | Invalid/fallback | Timeout | Latency p50 | Latency p95 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| C3-N | 360 | 0% | 0% | 839 ms | 931 ms | 52,955 |
| C5-N | 72 | 0% | 0% | 806 ms | 875 ms | 10,576 |
| C3-S | 360 | 0% | 0% | 824 ms | 938 ms | 53,080 |
| C5-S | 72 | 0% | 0% | 814 ms | 1,223 ms | 10,667 |

All 864 calls were valid. Operational health establishes that the treatment was delivered as
designed; it does not by itself demonstrate beneficial market impact.

## 10. Seed-1003 conclusion

Seed 1003 shows favorable LLM policy effects under shock at both frequencies: conditional
error and spread fell, immediate availability was maintained or restored, and provisional
recovery occurred earlier. In the normal regime, the 300-second LLM was broadly favorable,
whereas the 60-second LLM caused a large availability loss despite slightly improving
conditional error.

The contrast with seeds 1001 and 1002 is crucial. In those seeds, C3-S lost most immediate
post-shock two-sided availability; in seed 1003 it maintained 100%. Accordingly, seed 1003
must not be presented as proof that the LLM improves resilience. The three technical-pilot
seeds should be aggregated as paired observations to quantify this instability and plan the
frozen final experiment.
