# Milestone 5 Seed-1001 Market-Impact Results

**Seed:** 1001  
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

The clean matrix completed all 10 simulations and all extractions. The validator passed
**150/150 checks**, including identical fundamental paths, identical pre-treatment background
streams, matched wrapper mechanics, complete order lifecycles, inventory reconciliation,
non-crossed L1 books, metric fixtures, and LLM health.

Each regime used one identical 23,401-point fundamental path across C1–C5. Each cell has
23,400 one-second order-book snapshots. All canonical trades were reconstructed from paired
ABIDES execution legs; no unmatched leg was found.

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
| C1-N: canonical baseline | 208.59 | 61.40 | 142.58 | 81.40% | 37.34 | 62 |
| C2-N: coin 60s | 200.66 | 90.20 | 206.79 | 87.69% | 50.86 | 70 |
| C3-N: LLM 60s | 245.91 | 142.01 | 218.12 | 86.54% | 61.95 | 66 |
| C4-N: coin 300s | 201.00 | 114.77 | 207.58 | 82.57% | 50.46 | 61 |
| C5-N: LLM 300s | 209.54 | 93.68 | 191.94 | 91.88% | 48.14 | 69 |
| C1-S: canonical baseline | 646.66 | 120.83 | 161.18 | 81.69% | 320.58 | 62 |
| C2-S: coin 60s | 938.53 | 443.14 | 215.18 | 76.38% | 588.12 | 65 |
| C3-S: LLM 60s | 276.36 | 126.65 | 191.78 | 62.73% | 34.94 | 46 |
| C4-S: coin 300s | 471.41 | 251.92 | 199.24 | 78.43% | 130.80 | 57 |
| C5-S: LLM 300s | 494.33 | 191.77 | 219.51 | 72.88% | 196.57 | 55 |

The low full-session C3-S error and volatility cannot be read alone: C3-S had substantially
less two-sided-book coverage, especially immediately after the shock. Its volatility also
uses only 46 adjacent five-minute returns, fewer than every other cell.

## 4. Effect decomposition

All entries below are within-seed differences. Availability differences are percentage
points. For error and spread, negative means improvement; for depth and availability,
positive generally means improvement.

### Normal regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-N - C1-N | -7.93 | +28.80 | +64.21 | +6.29 pp |
| 60s | Policy | C3-N - C2-N | +45.25 | +51.80 | +11.33 | -1.15 pp |
| 60s | Total | C3-N - C1-N | +37.32 | +80.60 | +75.54 | +5.14 pp |
| 300s | Footprint | C4-N - C1-N | -7.59 | +53.37 | +65.00 | +1.17 pp |
| 300s | Policy | C5-N - C4-N | +8.54 | -21.09 | -15.64 | +9.31 pp |
| 300s | Total | C5-N - C1-N | +0.95 | +32.28 | +49.36 | +10.48 pp |

For this seed, the wrapper footprint in a normal market slightly reduced midpoint error and
added depth/availability, but widened spreads. The 60-second LLM policy then worsened error
and spread relative to its matched coin. At 300 seconds, the LLM was close on error, narrowed
spread, and improved availability, but reduced depth.

### Shock regime

| Frequency | Effect | Contrast | Error | Spread | Depth | Availability |
|---:|---|---|---:|---:|---:|---:|
| 60s | Footprint | C2-S - C1-S | +291.86 | +322.31 | +54.00 | -5.31 pp |
| 60s | Policy | C3-S - C2-S | -662.17 | -316.49 | -23.41 | -13.65 pp |
| 60s | Total | C3-S - C1-S | -370.31 | +5.82 | +30.60 | -18.96 pp |
| 300s | Footprint | C4-S - C1-S | -175.25 | +131.09 | +38.06 | -3.26 pp |
| 300s | Policy | C5-S - C4-S | +22.92 | -60.14 | +20.27 | -5.55 pp |
| 300s | Total | C5-S - C1-S | -152.33 | +70.95 | +58.33 | -8.81 pp |

The full-session conditional averages suggest a large C3-S policy improvement in error and
spread. The shock-window analysis below shows why that apparent improvement is incomplete:
the market was usually one-sided when the shock was most severe. At 300 seconds, the LLM
narrowed spread and increased depth relative to coin, but error and availability worsened.

## 5. Frequency and regime interactions

The frequency interaction is `(policy effect at 60s) - (policy effect at 300s)`. The regime
interaction is `(policy effect under shock) - (policy effect under normal conditions)`.

| Interaction | Error | Spread | Depth | Availability |
|---|---:|---:|---:|---:|
| Frequency interaction, normal | +36.71 | +72.89 | +26.97 | -10.46 pp |
| Frequency interaction, shock | -685.10 | -256.34 | -43.68 | -8.10 pp |
| Shock-minus-normal policy interaction, 60s | -707.42 | -368.29 | -34.73 | -12.51 pp |
| Shock-minus-normal policy interaction, 300s | +14.38 | -39.05 | +35.91 | -14.86 pp |

These signs indicate strong state and frequency dependence in seed 1001, but they are not
stable-effect estimates. In particular, interactions involving conditional midpoint error
must be interpreted with the simultaneous availability interaction.

## 6. Shock resilience and event-window behavior

The shock is an upward fundamental jump at 12:30. The 30-minute window covers 12:30–13:00.
Recovery is the first time the midpoint remains within **216.69 cents** of the evolving
fundamental for 60 continuous seconds. The threshold is one empirical pre-shock fundamental
standard deviation and is **provisional**, because the blueprint threshold is not frozen.

| Cell | Error, first 30m | Two-sided availability, first 30m | Recovery | Upward overshoot |
|---|---:|---:|---:|---:|
| C1-S | 5,102.75 | 68.89% | 95.2 min | 0.00 |
| C2-S | 7,444.33 | 54.83% | 95.1 min | 0.00 |
| C3-S | 8,067.66 | 4.33% | 88.5 min | 0.00 |
| C4-S | 3,883.41 | 28.94% | 94.3 min | 0.00 |
| C5-S | 4,809.32 | 31.94% | 95.8 min | 0.00 |

This is the most important correction to the earlier interpretation:

- C3-S did **not** improve immediate shock tracking relative to C2-S. Its first-30-minute
  error was 623.33 cents higher, and availability collapsed by 50.50 percentage points.
- C3-S eventually met the provisional recovery criterion about 6.5 minutes earlier than
  C2-S, but only after a very poor immediate shock window.
- C5-S also had worse first-30-minute error than C4-S (+925.91 cents), although its
  availability was 3.00 points higher and its spread was narrower over the full session.
- Overshoot was zero in every condition: the problem was underreaction to the upward
  fundamental jump, not price movement beyond it.

## 7. Volatility and trading activity

| Cell | RV bps (obs.) | Market trades | Market volume | Treatment fill rate | Mean abs. inventory | Terminal inventory | Marked PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| C1-N | 37.34 (62) | 119 | 1,438 | 15.50% | 37.96 | -61 | -$600.41 |
| C2-N | 50.86 (70) | 394 | 3,368 | 3.49% | 286.22 | -264 | -$1,899.90 |
| C3-N | 61.95 (66) | 388 | 3,188 | 2.83% | 213.18 | +737 | +$9,038.21 |
| C4-N | 50.46 (61) | 177 | 2,238 | 6.22% | 57.70 | +32 | +$834.95 |
| C5-N | 48.14 (69) | 202 | 3,092 | 18.03% | 194.87 | +660 | +$8,148.17 |
| C1-S | 320.58 (62) | 131 | 1,445 | 9.27% | 42.94 | -90 | +$745.91 |
| C2-S | 588.12 (65) | 351 | 4,038 | 5.19% | 568.52 | -1,033 | -$73,865.96 |
| C3-S | 34.94 (46) | 299 | 3,008 | 2.06% | 96.45 | +234 | -$1,071.13 |
| C4-S | 130.80 (57) | 160 | 2,112 | 9.22% | 240.32 | -590 | -$29,066.00 |
| C5-S | 196.57 (55) | 158 | 2,201 | 8.44% | 74.91 | 0 | -$710.00 |

The wrapper footprint produced much of the higher trading activity. For example, in normal
conditions C2-N versus C1-N added 275 trades and 1,930 shares of volume; the 60-second LLM
policy then changed that by only -6 trades and -180 shares. This illustrates why activity
must be decomposed rather than attributed directly to reasoning.

The unusually low C3-S volatility is not evidence of a calm market. It is calculated from
only 46 adjacent valid five-minute returns because the two-sided book disappeared frequently.
Availability and shock-window error show severe market impairment. PnL is included only as a
secondary treatment-agent diagnostic, not as the experiment's outcome.

## 8. Directional-policy diagnostic

This diagnostic measures whether the chosen side points toward fundamental value. It is a
possible mechanism, not a market-quality outcome.

| Pair | Coin | LLM | LLM - coin |
|---|---:|---:|---:|
| Normal, 60s | 53.22% | 43.75% | -9.47 pp |
| Normal, 300s | 48.28% | 41.94% | -6.34 pp |
| Shock, 60s, whole session | 52.48% | 52.91% | +0.44 pp |
| Shock, 60s, +/-30m | 51.52% | 41.38% | -10.14 pp |
| Shock, 300s, whole session | 46.30% | 50.98% | +4.68 pp |
| Shock, 300s, +/-30m | 75.00% | 50.00% | -25.00 pp |

Seed 1001 provides no consistent evidence that the LLM selected a more
fundamental-correcting side. The shock-window rates were lower than coin at both frequencies.

## 9. LLM operational diagnostics

| Cell | Calls | Invalid/fallback | Timeout | Latency p50 | Latency p95 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| C3-N | 360 | 0% | 0% | 858 ms | 946 ms | 53,055 |
| C5-N | 72 | 0% | 0% | 860 ms | 962 ms | 10,547 |
| C3-S | 360 | 0% | 0% | 866 ms | 1,003 ms | 53,256 |
| C5-S | 72 | 0% | 0% | 857 ms | 938 ms | 10,673 |

All 864 model calls were valid. This establishes implementation health; it does not establish
that the policy improved the market.

## 10. Seed-1001 conclusion

The main result of this technical seed is not “the LLM performed better” or “the LLM
performed worse.” It is that the market impact separates into a large mechanical footprint
and a policy component whose sign depends on frequency, regime, metric, and observation
availability.

Most notably, the initial full-session C3-S averages looked favorable until the shock window
and book availability were analyzed jointly. During the first 30 minutes after shock, C3-S
had worse price tracking than its matched coin and almost no two-sided market. This is exactly
why the experiment requires a multi-outcome market-quality analysis rather than a single LLM
score.

No scientific conclusion should be drawn from seed 1001 alone. Seeds 1002 and 1003 are needed
for pilot variance/design review, and final conclusions require paired differences across the
frozen final seeds with confidence intervals and event-study aggregation.
