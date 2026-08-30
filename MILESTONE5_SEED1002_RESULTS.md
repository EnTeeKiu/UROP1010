# Milestone 5 Seed-1002 Market-Impact Results

**Seed:** 1002  
**Matrix:** five conditions x normal/shock regimes = 10 cells  
**Analysis window:** 10:00–16:00; 09:30–10:00 warmup excluded  
**Status:** technical-pilot diagnostic, not an estimate of the population effect

## 1. Question answered by this analysis

This experiment does not primarily ask whether Gemma is a good trader. It asks how replacing
a random side-selection policy with an LLM side-selection policy changes the **market**, after
holding wake frequency, order size, placement, and cancellation mechanics fixed.

The analysis therefore separates three effects at each frequency:

- **Footprint:** coin wrapper minus canonical ZI (`C2-C1` or `C4-C1`).
- **Policy:** LLM wrapper minus matched coin wrapper (`C3-C2` or `C5-C4`).
- **Total:** LLM wrapper minus canonical ZI (`C3-C1` or `C5-C1`).

By construction, `footprint + policy = total`. Frequency and regime interactions are then
used to ask whether the policy effect changes with participation frequency or market shock.

## 2. Data and metric integrity

The clean matrix completed all 10 simulations and all extractions. A minor validator bug involving
terminal cancellation contracts at exactly market close was fixed, after which the validator passed
**150/150 checks**. This includes identical fundamental paths, matched pre-treatment background streams,
perfectly matched wrapper mechanics (cadence, side logic, size, exact 100% pairing), terminal order 
lifecycle completeness, and 0 crossed quotes in L1 snapshots.

Metric conventions:

- Midpoint error, spread, and depth are time-weighted over intervals where the required
  two-sided L1 state exists.
- Book availability is the fraction of the session with both a bid and an ask.
- Midpoint error and spread are in cents; depth is displayed shares.
- Lower midpoint error, spread, and volatility are better. Higher depth and availability
  generally indicate better liquidity.
- Five-minute realized volatility is `sqrt(sum(log-return^2))`, reported in basis points.
  Missing five-minute bins break the return chain rather than being silently bridged.

## 3. Per-condition market outcomes

| Cell | Midpoint error | Spread | Depth | Availability | RV (bps) | Valid 5m returns |
|---|---:|---:|---:|---:|---:|---:|
| C1-N: canonical baseline | 205.15 | 63.66 | 146.40 | 80.12% | 38.45 | 62 |
| C2-N: coin 60s | 194.20 | 89.65 | 212.87 | 88.98% | 54.51 | 68 |
| C3-N: LLM 60s | 223.36 | 125.86 | 211.59 | 80.91% | 60.85 | 62 |
| C4-N: coin 300s | 204.05 | 127.48 | 196.76 | 90.02% | 87.58 | 66 |
| C5-N: LLM 300s | 235.33 | 149.38 | 237.62 | 85.78% | 50.10 | 65 |
| C1-S: canonical baseline | 835.47 | 221.78 | 134.11 | 93.56% | 377.53 | 70 |
| C2-S: coin 60s | 1264.78 | 1246.67 | 217.08 | 78.04% | 647.54 | 63 |
| C3-S: LLM 60s | 545.40 | 344.48 | 224.37 | 73.08% | 79.08 | 54 |
| C4-S: coin 300s | 974.33 | 669.12 | 224.44 | 87.28% | 704.02 | 64 |
| C5-S: LLM 300s | 937.54 | 281.37 | 219.00 | 86.42% | 364.76 | 64 |

## 4. Effect decomposition

All entries below are within-seed differences. Availability differences are percentage points. 
For error and spread, negative means improvement; for depth and availability, positive generally means improvement.

### Normal regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-N - C1-N | -10.95 | +25.99 | +66.47 | +8.86 pp |
| 60s | Policy | C3-N - C2-N | +29.16 | +36.21 | -1.28 | -8.07 pp |
| 60s | Total | C3-N - C1-N | +18.21 | +62.20 | +65.19 | +0.79 pp |
| 300s | Footprint | C4-N - C1-N | -1.10 | +63.82 | +50.36 | +9.90 pp |
| 300s | Policy | C5-N - C4-N | +31.28 | +21.90 | +40.86 | -4.24 pp |
| 300s | Total | C5-N - C1-N | +30.18 | +85.72 | +91.22 | +5.66 pp |

In calm conditions, the footprint reduced error but widened spreads and improved book availability.
Adding the LLM policy worsened midpoint error and spreads at both frequencies.

### Shock regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-S - C1-S | +429.31 | +1024.89 | +82.97 | -15.52 pp |
| 60s | Policy | C3-S - C2-S | -719.38 | -902.19 | +7.29 | -4.96 pp |
| 60s | Total | C3-S - C1-S | -290.07 | +122.70 | +90.26 | -20.48 pp |
| 300s | Footprint | C4-S - C1-S | +138.86 | +447.34 | +90.33 | -6.28 pp |
| 300s | Policy | C5-S - C4-S | -36.79 | -387.75 | -5.44 | -0.86 pp |
| 300s | Total | C5-S - C1-S | +102.07 | +59.59 | +84.89 | -7.14 pp |

The full-session averages suggest a huge LLM policy improvement in the shock regime at 60s (-719 error, -902 spread).
However, this is heavily confounded by missing book conditions, especially in the C3-S shock window (see section 6).

## 5. Frequency and regime interactions

| Interaction | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Frequency interaction, normal | -2.12 | +14.31 | -42.14 | -3.83 pp |
| Frequency interaction, shock | -682.59 | -514.44 | +12.73 | -4.10 pp |
| Shock-minus-normal policy interaction, 60s | -748.54 | -938.40 | +8.57 | +3.11 pp |
| Shock-minus-normal policy interaction, 300s | -68.07 | -409.65 | -46.30 | +3.38 pp |

## 6. Shock resilience and event-window behavior

The shock is an upward fundamental jump at 12:30. The 30-minute window covers 12:30–13:00.

| Cell | Error, first 30m | Two-sided availability, first 30m | Recovery | Upward overshoot |
|---|---:|---:|---:|---:|
| C1-S | 4,826.39 | 95.11% | 86.8 min | 0.00 |
| C2-S | 6,600.45 | 47.11% | 92.6 min | 0.00 |
| C3-S | 7,914.57 | 11.89% | 92.6 min | 0.00 |
| C4-S | 7,975.35 | 40.67% | 81.0 min | 0.00 |
| C5-S | 4,920.63 | 100.00% | 92.6 min | 0.00 |

Similar to seed 1001, C3-S (LLM 60s) completely lost market two-sided availability in the first 30 minutes after shock (only 11.89% availability). Its first-30-minute error was 1,314 cents *worse* than its coin counterpart (C2-S). The low full-session averages for C3-S in section 4 are an artifact of omitting this high-error missing-book period.

However, C5-S (LLM 300s) did exceptionally well at maintaining availability (100.00%) and kept shock-window error much lower than C4-S (4,920 vs 7,975), nearly matching the canonical baseline.

## 7. Volatility and trading activity

| Cell | RV bps (obs.) | Market trades | Market volume | Treatment fill rate | Mean abs. inventory | Terminal inventory | Marked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1-N | 38.45 (62) | 113 | 1,355 | 14.33% | 69.96 | -97 | -$627.91 |
| C2-N | 54.51 (68) | 378 | 3,389 | 3.74% | 572.84 | -845 | -$4,407.86 |
| C3-N | 60.85 (62) | 399 | 3,499 | 2.97% | 187.97 | +287 | +$1,716.94 |
| C4-N | 87.58 (66) | 186 | 2,507 | 12.14% | 256.56 | -278 | +$1,092.07 |
| C5-N | 50.10 (65) | 176 | 2,233 | 7.21% | 137.34 | +379 | -$1,130.96 |
| C1-S | 377.53 (70) | 153 | 2,228 | 18.78% | 52.55 | -93 | -$4,814.73 |
| C2-S | 647.54 (63) | 354 | 3,720 | 4.00% | 636.74 | -991 | -$52,968.07 |
| C3-S | 79.08 (54) | 316 | 2,776 | 0.61% | 88.94 | +55 | +$9,832.30 |
| C4-S | 704.02 (64) | 188 | 2,642 | 13.51% | 458.82 | -827 | -$29,953.49 |
| C5-S | 364.76 (64) | 180 | 2,245 | 4.67% | 79.15 | +98 | +$9,271.11 |

## 8. Directional-policy diagnostic

| Pair | Coin | LLM | LLM - coin |
|---|---:|---:|---:|
| Normal, 60s | 52.61% | 49.72% | -2.89 pp |
| Normal, 300s | 52.38% | 54.24% | +1.86 pp |
| Shock, 60s, whole session | 54.23% | 49.60% | -4.63 pp |
| Shock, 60s, +/-30m | 53.33% | 50.00% | -3.33 pp |
| Shock, 300s, whole session | 48.33% | 53.33% | +5.00 pp |
| Shock, 300s, +/-30m | 77.78% | 66.67% | -11.11 pp |

## 9. LLM operational diagnostics

| Cell | Calls | Invalid/fallback | Timeout | Latency p50 | Latency p95 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| C3-N | 360 | 0% | 0% | 2,924 ms | 3,004 ms | 52,968 |
| C5-N | 72 | 0% | 0% | 2,982 ms | 3,029 ms | 10,611 |
| C3-S | 360 | 0% | 0% | 2,964 ms | 3,062 ms | 53,091 |
| C5-S | 72 | 0% | 0% | 2,988 ms | 3,041 ms | 10,622 |

100% of LLM calls across all cells were valid, indicating stable extraction pipelines. Latencies are around ~3s per call, which is slightly higher than seed 1001 but entirely within the timeout constraints.

## 10. Seed-1002 conclusion

Seed 1002 echoes the core finding of seed 1001: high-frequency (60s) LLM intervention under shock (C3-S) results in a severe collapse of market availability immediately following the shock. Because metrics drop missing intervals, C3-S appears artificially superior in full-session averages, but its shock-window tracking error is disastrously high relative to the coin control.

Conversely, the 300s LLM wrapper under shock (C5-S) performed notably well in seed 1002, retaining full market availability and significantly reducing tracking error compared to its coin control. This highlights the importance of the frequency interaction: the LLM's value may be highly dependent on acting less frequently, allowing the market to digest quotes without freezing up.

The final evaluation requires paired differences and confidence intervals across all 30 seeds.
