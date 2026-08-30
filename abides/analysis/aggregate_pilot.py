"""Aggregate technical-pilot metrics across raw logs for seeds 1001--1003."""

from __future__ import annotations

import argparse
import json
import math
import os

import pandas as pd

from analysis.summarize_seed import summarize_seed


CELLS = [
    "C1-N", "C2-N", "C3-N", "C4-N", "C5-N",
    "C1-S", "C2-S", "C3-S", "C4-S", "C5-S",
]

PRIMARY = [
    "midpoint_error_tw",
    "quoted_spread_tw",
    "depth_at_touch_tw",
    "book_availability",
]

SECONDARY = [
    "realized_volatility_5m_bps",
    "unique_trades",
    "market_volume",
    "treatment_fill_rate",
    "treatment_mean_abs_inventory",
    "treatment_terminal_inventory",
    "treatment_pnl_cents",
]

CONTRASTS = {
    "footprint_60": ("C2", "C1"),
    "policy_60": ("C3", "C2"),
    "total_60": ("C3", "C1"),
    "footprint_300": ("C4", "C1"),
    "policy_300": ("C5", "C4"),
    "total_300": ("C5", "C1"),
}

T_CRITICAL_DF2_95 = 4.3026527297


def load_pilot(log_root: str) -> pd.DataFrame:
    frames = []
    for seed in (1001, 1002, 1003):
        frame = summarize_seed(log_root, seed)
        frame["seed"] = seed
        frame["provenance"] = "raw parquet"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False)


def _mean_sd_ci(values: pd.Series) -> dict[str, float | int]:
    values = pd.to_numeric(values, errors="coerce").dropna()
    n = len(values)
    mean = float(values.mean())
    sd = float(values.std(ddof=1)) if n > 1 else math.nan
    half = T_CRITICAL_DF2_95 * sd / math.sqrt(n) if n == 3 else math.nan
    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "ci95_low": mean - half,
        "ci95_high": mean + half,
    }


def _cell_index(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    return frame[frame["seed"] == seed].set_index("cell")


def contrast_values(frame: pd.DataFrame, regime: str, contrast: str, metric: str) -> pd.Series:
    treatment, control = CONTRASTS[contrast]
    values = {}
    for seed in sorted(frame["seed"].unique()):
        indexed = _cell_index(frame, seed)
        values[seed] = indexed.loc[f"{treatment}-{regime}", metric] - indexed.loc[f"{control}-{regime}", metric]
    return pd.Series(values, name=metric)


def aggregate(log_root: str) -> dict:
    frame = load_pilot(log_root)
    cell_summary = {}
    for cell in CELLS:
        subset = frame[frame["cell"] == cell]
        cell_summary[cell] = {
            metric: _mean_sd_ci(subset[metric]) for metric in PRIMARY + SECONDARY
        }

    contrasts = {}
    for regime in ("N", "S"):
        contrasts[regime] = {}
        for name in CONTRASTS:
            contrasts[regime][name] = {
                metric: {
                    **_mean_sd_ci(contrast_values(frame, regime, name, metric)),
                    "seed_values": contrast_values(frame, regime, name, metric).to_dict(),
                }
                for metric in PRIMARY
            }

    interactions = {}
    for regime in ("N", "S"):
        interactions[f"frequency_{regime}"] = {}
        for metric in PRIMARY:
            values = contrast_values(frame, regime, "policy_60", metric) - contrast_values(
                frame, regime, "policy_300", metric
            )
            interactions[f"frequency_{regime}"][metric] = {
                **_mean_sd_ci(values), "seed_values": values.to_dict()
            }
    for frequency in ("60", "300"):
        interactions[f"shock_minus_normal_{frequency}"] = {}
        for metric in PRIMARY:
            values = contrast_values(frame, "S", f"policy_{frequency}", metric) - contrast_values(
                frame, "N", f"policy_{frequency}", metric
            )
            interactions[f"shock_minus_normal_{frequency}"][metric] = {
                **_mean_sd_ci(values), "seed_values": values.to_dict()
            }

    shock = {}
    for cell in ["C1-S", "C2-S", "C3-S", "C4-S", "C5-S"]:
        subset = frame[frame["cell"] == cell]
        shock[cell] = {
            metric: _mean_sd_ci(subset[metric])
            for metric in [
                "shock_30m_midpoint_error_tw",
                "shock_30m_book_availability",
                "recovery_time_s_provisional",
                "shock_30m_overshoot_cents",
            ]
        }

    shock_policy = {}
    for frequency, treatment, control in (("60", "C3-S", "C2-S"), ("300", "C5-S", "C4-S")):
        shock_policy[frequency] = {}
        for metric in [
            "shock_30m_midpoint_error_tw",
            "shock_30m_book_availability",
            "recovery_time_s_provisional",
        ]:
            values = {}
            for seed in sorted(frame["seed"].unique()):
                indexed = _cell_index(frame, seed)
                values[seed] = indexed.loc[treatment, metric] - indexed.loc[control, metric]
            series = pd.Series(values)
            shock_policy[frequency][metric] = {
                **_mean_sd_ci(series), "seed_values": series.to_dict()
            }

    side_quality = {}
    for regime, frequency, treatment, control in (
        ("N", "60", "C3-N", "C2-N"),
        ("N", "300", "C5-N", "C4-N"),
        ("S", "60", "C3-S", "C2-S"),
        ("S", "300", "C5-S", "C4-S"),
    ):
        key = f"{regime}_{frequency}"
        side_quality[key] = {}
        for metric in [
            "fundamental_correcting_rate",
            "fundamental_correcting_rate_shock_window",
        ]:
            values = {}
            for seed in sorted(frame["seed"].unique()):
                indexed = _cell_index(frame, seed)
                treatment_value = indexed.loc[treatment, metric]
                control_value = indexed.loc[control, metric]
                if pd.notna(treatment_value) and pd.notna(control_value):
                    values[seed] = treatment_value - control_value
            series = pd.Series(values, dtype=float)
            side_quality[key][metric] = {
                **_mean_sd_ci(series), "seed_values": series.to_dict()
            }

    llm_diagnostics = {}
    for cell in ("C3-N", "C5-N", "C3-S", "C5-S"):
        subset = frame[frame["cell"] == cell]
        llm_diagnostics[cell] = {
            metric: _mean_sd_ci(subset[metric])
            for metric in [
                "fallback_rate", "timeout_rate", "latency_ms_p50",
                "latency_ms_p95", "tokens_total",
            ]
        }

    return {
        "provenance": {
            "1001": "raw parquet",
            "1002": "raw parquet",
            "1003": "raw parquet",
        },
        "cell_summary": cell_summary,
        "contrasts": contrasts,
        "interactions": interactions,
        "shock": shock,
        "shock_policy": shock_policy,
        "side_quality_policy_difference": side_quality,
        "llm_diagnostics": llm_diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="output/raw")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = aggregate(args.log_root)
    payload = json.dumps(result, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
