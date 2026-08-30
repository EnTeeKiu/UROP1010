# Milestone 5 Seed-1002 Market-Impact Results

**Seed:** 1002  
**Matrix:** five conditions x normal/shock regimes = 10 cells  
**Analysis window:** 10:00–16:00; 09:30–10:00 warmup excluded  
**Status:** technical-pilot diagnostic, not an estimate of the population effect
**Data source:** recomputed directly from the committed seed-1002 Parquet logs

## 1. Research question and estimands

The experiment asks how replacing a random directional policy with an LLM directional
policy changes the **market**, after holding wake frequency, cancellation, size, placement,
and mandatory participation fixed. It does not primarily ask whether Gemma is profitable.

The analysis separates three effects at each frequency:

- **Footprint:** coin wrapper minus canonical ZI (`C2-C1` or `C4-C1`).
- **Policy:** LLM wrapper minus matched coin wrapper (`C3-C2` or `C5-C4`).
- **Total:** LLM wrapper minus canonical ZI (`C3-C1` or `C5-C1`).

The frequency interaction is `(C3-C2) - (C5-C4)`. The regime interaction compares a policy
effect under shock with the corresponding normal-regime effect.

## 2. Data and validation integrity

All 10 simulations and Parquet outputs are present. Independent validation of the newly
committed logs passed **150/150 checks**, including output completeness, identical
fundamental paths, paired pre-treatment background streams, matched wrapper mechanics,
complete terminal order lifecycles, inventory reconciliation, non-crossed L1 snapshots,
metric fixtures, and LLM health.

The committed `seed1002_summary.json` and an independent rerun of
`analysis.summarize_seed` agree numerically on every common field. This version supersedes
the earlier seed-1002 Markdown, whose C1-N through C3-N values did not match the subsequently
committed raw logs.

Metric conventions:

- midpoint error, spread, and depth are time-weighted over valid two-sided L1 intervals;
- availability is the fraction of the session with both a bid and an ask;
- midpoint error and spread are cents, while depth is displayed shares; and
- five-minute realized volatility is `sqrt(sum(log-return^2))` in basis points, with missing
  bins breaking the return chain.

Conditional market metrics must be interpreted jointly with availability.

## 3. Per-condition market outcomes

| Cell | Midpoint error | Spread | Depth | Availability | RV (bps) | Valid 5m returns |
|---|---:|---:|---:|---:|---:|---:|
| C1-N: canonical baseline | 214.93 | 144.46 | 146.99 | 95.65% | 85.06 | 72 |
| C2-N: coin 60s | 201.49 | 167.75 | 199.32 | 88.06% | 74.63 | 70 |
| C3-N: LLM 60s | 226.53 | 183.95 | 216.84 | 79.31% | 92.71 | 60 |
| C4-N: coin 300s | 204.05 | 127.48 | 196.76 | 90.02% | 87.58 | 66 |
| C5-N: LLM 300s | 235.33 | 149.38 | 237.62 | 85.78% | 50.10 | 65 |
| C1-S: canonical baseline | 835.47 | 221.78 | 134.11 | 93.56% | 377.53 | 70 |
| C2-S: coin 60s | 1,264.78 | 1,246.67 | 217.08 | 78.04% | 647.54 | 63 |
| C3-S: LLM 60s | 545.40 | 344.48 | 224.37 | 73.08% | 79.08 | 54 |
| C4-S: coin 300s | 974.33 | 669.12 | 224.44 | 87.28% | 704.02 | 64 |
| C5-S: LLM 300s | 937.54 | 281.37 | 219.00 | 86.42% | 364.76 | 64 |

The favorable full-session C3-S error, spread, and volatility cannot be read alone. C3-S
had materially less two-sided coverage, especially immediately after the shock.

## 4. Effect decomposition

Negative differences improve midpoint error and spread. Positive differences generally
improve depth and availability. Availability differences are percentage points.

### Normal regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-N - C1-N | -13.45 | +23.29 | +52.33 | -7.58 pp |
| 60s | Policy | C3-N - C2-N | +25.04 | +16.20 | +17.52 | -8.75 pp |
| 60s | Total | C3-N - C1-N | +11.59 | +39.49 | +69.84 | -16.33 pp |
| 300s | Footprint | C4-N - C1-N | -10.88 | -16.98 | +49.76 | -5.63 pp |
| 300s | Policy | C5-N - C4-N | +31.28 | +21.89 | +40.86 | -4.24 pp |
| 300s | Total | C5-N - C1-N | +20.40 | +4.91 | +90.62 | -9.87 pp |

In this seed, the wrapper footprint reduced conditional midpoint error and added depth but
reduced availability. The 60-second LLM then worsened error and spread and removed another
8.75 points of availability. The 300-second LLM also worsened error, spread, and
availability while increasing displayed depth.

### Shock regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-S - C1-S | +429.31 | +1,024.89 | +82.96 | -15.52 pp |
| 60s | Policy | C3-S - C2-S | -719.38 | -902.20 | +7.29 | -4.96 pp |
| 60s | Total | C3-S - C1-S | -290.07 | +122.69 | +90.25 | -20.48 pp |
| 300s | Footprint | C4-S - C1-S | +138.86 | +447.34 | +90.33 | -6.28 pp |
| 300s | Policy | C5-S - C4-S | -36.79 | -387.76 | -5.44 | -0.86 pp |
| 300s | Total | C5-S - C1-S | +102.07 | +59.58 | +84.89 | -7.14 pp |

Full-session conditional averages suggest large error and spread improvements from the
60-second LLM. Section 6 shows that the immediate shock window was instead worse and mostly
one-sided, so the conditional average is incomplete.

## 5. Frequency and regime interactions

| Interaction | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Frequency interaction, normal | -6.24 | -5.69 | -23.34 | -4.51 pp |
| Frequency interaction, shock | -682.59 | -514.44 | +12.73 | -4.10 pp |
| Shock-minus-normal policy interaction, 60s | -744.42 | -918.40 | -10.23 | +3.79 pp |
| Shock-minus-normal policy interaction, 300s | -68.07 | -409.65 | -46.30 | +3.38 pp |

The conditional error and spread interactions look more favorable under shock, but they do
not establish resilience because the corresponding event-window availability was poor.

## 6. Shock resilience and event-window behavior

The upward shock occurs at 12:30. The event window covers 12:30–13:00. Recovery is the first
time the midpoint stays within **306.54 cents** of the evolving fundamental for 60
continuous seconds. The threshold is one empirical pre-shock fundamental standard deviation
and remains **provisional**.

| Cell | Error, first 30m | Two-sided availability, first 30m | Recovery | Upward overshoot |
|---|---:|---:|---:|---:|
| C1-S | 4,826.39 | 95.11% | 86.8 min | 0.00 |
| C2-S | 6,600.45 | 47.11% | 92.6 min | 0.00 |
| C3-S | 7,914.57 | 11.89% | 92.6 min | 0.00 |
| C4-S | 7,975.35 | 40.67% | 81.0 min | 0.00 |
| C5-S | 4,920.63 | 100.00% | 92.6 min | 0.00 |

- C3-S increased first-30-minute error by 1,314.12 cents relative to C2-S and reduced
  availability by 35.22 percentage points. Their provisional recovery times were equal.
- C5-S reduced error by 3,054.72 cents and increased availability by 59.33 points relative
  to C4-S, although it reached the provisional recovery condition 11.6 minutes later.
- Overshoot was zero in every condition; the impairment was underreaction or missing
  two-sided quotes rather than movement above the evolving fundamental.

## 7. Volatility, activity, inventory, and PnL

| Cell | RV bps (obs.) | Market trades | Market volume | Treatment fill rate | Mean abs. inventory | Terminal inventory | Marked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1-N | 85.06 (72) | 158 | 1,943 | 11.22% | 92.18 | -97 | -$10.48 |
| C2-N | 74.63 (70) | 374 | 3,346 | 3.14% | 452.49 | -845 | +$2,413.69 |
| C3-N | 92.71 (60) | 350 | 3,032 | 1.25% | 123.92 | +287 | -$752.90 |
| C4-N | 87.58 (66) | 186 | 2,507 | 12.14% | 256.56 | -278 | +$1,092.07 |
| C5-N | 50.10 (65) | 176 | 2,233 | 7.21% | 137.34 | +379 | -$1,130.96 |
| C1-S | 377.53 (70) | 153 | 2,228 | 18.78% | 52.55 | -93 | -$4,814.73 |
| C2-S | 647.54 (63) | 354 | 3,720 | 4.00% | 636.74 | -991 | -$52,968.07 |
| C3-S | 79.08 (54) | 316 | 2,776 | 0.61% | 88.94 | +55 | +$9,832.30 |
| C4-S | 704.02 (64) | 188 | 2,642 | 13.51% | 458.82 | -827 | -$29,953.49 |
| C5-S | 364.76 (64) | 180 | 2,245 | 4.67% | 79.15 | +98 | +$9,271.11 |

The wrapper produced most of the increase in activity relative to C1. PnL and inventory are
secondary agent diagnostics, not the study's market-quality outcomes. C3-S volatility is
also conditional on only 54 valid adjacent five-minute returns and must be interpreted with
its low availability.

## 8. Directional-policy diagnostic

| Pair | Coin | LLM | LLM - coin |
|---|---:|---:|---:|
| Normal, 60s | 53.00% | 48.18% | -4.83 pp |
| Normal, 300s | 52.38% | 54.24% | +1.86 pp |
| Shock, 60s, whole session | 54.23% | 49.60% | -4.63 pp |
| Shock, 60s, ±30m | 53.33% | 50.00% | -3.33 pp |
| Shock, 300s, whole session | 48.33% | 53.33% | +5.00 pp |
| Shock, 300s, ±30m | 77.78% | 66.67% | -11.11 pp |

The LLM did not consistently choose the more fundamental-correcting side. It was worse than
coin in the 60-second normal and shock comparisons and in both shock windows.

## 9. LLM operational diagnostics

| Cell | Calls | Invalid/fallback | Timeout | Latency p50 | Latency p95 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| C3-N | 360 | 0% | 0% | 2,985 ms | 3,087 ms | 53,141 |
| C5-N | 72 | 0% | 0% | 2,982 ms | 3,029 ms | 10,611 |
| C3-S | 360 | 0% | 0% | 2,964 ms | 3,062 ms | 53,091 |
| C5-S | 72 | 0% | 0% | 2,988 ms | 3,041 ms | 10,622 |

All 864 model calls were valid with no fallback or timeout. Operational health confirms
that the treatment was delivered as designed; it does not demonstrate beneficial policy
content.

## 10. Seed-1002 conclusion

Seed 1002 reinforces the need to analyze market quality jointly. In the 60-second shock arm,
C3-S appears favorable on full-session conditional error and spread, but its immediate
shock-window error was worse than coin and two-sided availability fell to 11.89%. At 300
seconds, C5-S maintained full immediate availability and much lower event-window error than
C4-S, but recovered later under the provisional criterion.

Normal-regime raw logs show that both LLM frequencies worsened midpoint error, spread, and
availability relative to their matched coin controls for this seed. No conclusion should be
drawn from seed 1002 alone. Its role is technical validation and paired-variance assessment
with seeds 1001 and 1003 before the frozen final experiment.
