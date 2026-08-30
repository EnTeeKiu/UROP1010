"""Produce descriptive (non-inferential) metrics for one technical-pilot seed."""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from analysis.metrics import (
    depth_at_touch_tw,
    midpoint_error_tw,
    quoted_spread_tw,
    time_weighted_mean,
)
from analysis.validation import CELLS


SESSION_START = pd.Timestamp("2019-06-28 10:00:00")
SESSION_END = pd.Timestamp("2019-06-28 16:00:00")
SHOCK_TIME = pd.Timestamp("2019-06-28 12:30:00")
SHOCK_WINDOW_END = SHOCK_TIME + pd.Timedelta(minutes=30)
STARTING_CASH = 10_000_000


def _read(directory, name):
    return pd.read_parquet(os.path.join(directory, name))


def _side_quality(decisions: pd.DataFrame, fundamental: pd.DataFrame):
    if decisions.empty:
        return None, None
    frame = decisions.copy().sort_values("time")
    frame["midpoint"] = (
        frame["snapshot_best_bid"].astype("Float64")
        + frame["snapshot_best_ask"].astype("Float64")
    ) / 2
    fund = fundamental[["time", "value"]].sort_values("time")
    frame = pd.merge_asof(frame, fund, on="time", direction="backward").dropna(subset=["midpoint", "value"])
    non_equal = frame[frame["midpoint"] != frame["value"]].copy()
    if non_equal.empty:
        return None, None
    correct = (
        ((non_equal["midpoint"] < non_equal["value"]) & non_equal["policy_side"].eq("BUY"))
        | ((non_equal["midpoint"] > non_equal["value"]) & non_equal["policy_side"].eq("SELL"))
    )
    shock_window = non_equal[
        non_equal["time"].between(SHOCK_TIME - pd.Timedelta(minutes=30), SHOCK_TIME + pd.Timedelta(minutes=30))
    ]
    shock_correct = correct.loc[shock_window.index]
    return float(correct.mean()), float(shock_correct.mean()) if len(shock_correct) else None


def _realized_volatility_bps(book: pd.DataFrame):
    """Per-session realized volatility from five-minute log midpoint returns."""
    midpoint = book.set_index("time")["midpoint"].astype(float)
    midpoint = midpoint.loc[SESSION_START:SESSION_END].resample("5min").last()
    # Missing bins break the return chain; do not bridge a one-sided interval.
    returns = np.log(midpoint).diff().dropna()
    return float(np.sqrt(np.square(returns).sum()) * 10_000), len(returns)


def _canonical_trade_activity(trades: pd.DataFrame):
    """Collapse the two ABIDES execution legs emitted for each market trade."""
    groups = (
        trades.groupby(["time", "price", "quantity"], dropna=False)
        .size()
        .rename("legs")
        .reset_index()
    )
    if (groups["legs"] % 2 != 0).any():
        raise ValueError("trade execution legs do not reconcile into pairs")
    unique_trades = int((groups["legs"] // 2).sum())
    volume = int((groups["quantity"] * groups["legs"] // 2).sum())
    return unique_trades, volume


def _dynamic_recovery_time(book: pd.DataFrame, fundamental: pd.DataFrame, threshold: float):
    """First post-shock time with error inside threshold for 60 continuous seconds."""
    aligned = book[["time", "midpoint"]].merge(
        fundamental[["time", "value"]], on="time", how="left"
    )
    aligned = aligned[aligned["time"].between(SHOCK_TIME, SESSION_END)].copy()
    aligned["within"] = (
        aligned["midpoint"].notna()
        & ((aligned["midpoint"] - aligned["value"]).abs() <= threshold)
    )
    run_start = None
    previous_time = None
    for row in aligned.itertuples(index=False):
        contiguous = previous_time is not None and row.time - previous_time == pd.Timedelta(seconds=1)
        if row.within:
            if run_start is None or not contiguous:
                run_start = row.time
            if (row.time - run_start).total_seconds() >= 60:
                return float((run_start - SHOCK_TIME).total_seconds())
        else:
            run_start = None
        previous_time = row.time
    return None


def summarize_seed(log_root: str, seed: int):
    rows = []
    for cell in CELLS:
        directory = os.path.join(log_root, cell, str(seed))
        book = _read(directory, "book_l1.parquet")
        fundamental = _read(directory, "fundamental.parquet")
        decisions = _read(directory, "decisions.parquet")
        orders = _read(directory, "orders.parquet")
        trades = _read(directory, "trades.parquet")
        agent_state = _read(directory, "agent_state.parquet")
        requests = _read(directory, "treatment_requests.parquet")
        with open(os.path.join(directory, "run_manifest.json"), "r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        availability = book["best_bid"].notna() & book["best_ask"].notna()
        book_availability = time_weighted_mean(
            book["time"], availability.astype(float), start=SESSION_START, end=SESSION_END
        )
        treatment_exec = orders[(orders["agent_id"] == 10) & (orders["status"] == "EXECUTED")]
        correcting, correcting_shock = _side_quality(decisions, fundamental)
        unique_trades, market_volume = _canonical_trade_activity(trades)
        submissions = requests[requests["event_type"] == "ORDER_SUBMITTED"]
        submitted_quantity = int(submissions["quantity"].sum())
        treatment_turnover = int(treatment_exec["quantity"].sum())
        treatment_fill_rate = treatment_turnover / submitted_quantity if submitted_quantity else None
        terminal_inventory = int(agent_state["inventory"].iloc[-1]) if not agent_state.empty else 0
        terminal_cash = int(agent_state["cash"].iloc[-1]) if not agent_state.empty else STARTING_CASH
        close_fundamental = int(fundamental[fundamental["time"] <= SESSION_END]["value"].iloc[-1])
        treatment_pnl_cents = terminal_cash - STARTING_CASH + terminal_inventory * close_fundamental
        mean_abs_inventory = time_weighted_mean(
            agent_state["time"], agent_state["inventory"].abs(),
            start=SESSION_START, end=SESSION_END,
        ) if not agent_state.empty else 0.0

        recovery = None
        recovery_threshold = None
        shock_window_error = None
        shock_window_availability = None
        shock_overshoot = None
        if cell.endswith("-S"):
            pre_shock = fundamental[
                fundamental["time"].between(SESSION_START, SHOCK_TIME, inclusive="left")
            ]
            recovery_threshold = float(pre_shock["value"].std())
            recovery = _dynamic_recovery_time(book, fundamental, recovery_threshold)
            shock_window_error = midpoint_error_tw(
                book, fundamental, start=SHOCK_TIME, end=SHOCK_WINDOW_END
            )
            shock_book = book[book["time"].between(SHOCK_TIME, SHOCK_WINDOW_END)].copy()
            shock_availability_values = shock_book["best_bid"].notna() & shock_book["best_ask"].notna()
            shock_window_availability = time_weighted_mean(
                shock_book["time"], shock_availability_values.astype(float),
                start=SHOCK_TIME, end=SHOCK_WINDOW_END,
            )
            aligned_shock = shock_book[["time", "midpoint"]].merge(
                fundamental[["time", "value"]], on="time", how="left"
            ).dropna(subset=["midpoint", "value"])
            shock_overshoot = float(
                (aligned_shock["midpoint"] - aligned_shock["value"]).clip(lower=0).max()
            ) if not aligned_shock.empty else None

        llm_latency = decisions["llm_latency_ms"].dropna() if "llm_latency_ms" in decisions else pd.Series(dtype=float)
        fallback_values = decisions["llm_fallback_used"].dropna() if "llm_fallback_used" in decisions else pd.Series(dtype=bool)
        timeout_values = decisions["llm_timeout"].dropna() if "llm_timeout" in decisions else pd.Series(dtype=bool)
        has_llm_diagnostics = len(fallback_values) > 0
        realized_volatility, realized_volatility_observations = _realized_volatility_bps(book)
        rows.append({
            "cell": cell,
            "midpoint_error_tw": midpoint_error_tw(book, fundamental, start=SESSION_START, end=SESSION_END),
            "quoted_spread_tw": quoted_spread_tw(book, start=SESSION_START, end=SESSION_END),
            "depth_at_touch_tw": depth_at_touch_tw(book, start=SESSION_START, end=SESSION_END),
            "book_availability": book_availability,
            "decisions": len(decisions),
            "submissions": len(submissions),
            "cancel_requests": int((requests["event_type"] == "CANCEL_SUBMITTED").sum()),
            "treatment_fill_events": len(treatment_exec),
            "treatment_fill_quantity": treatment_turnover,
            "treatment_fill_rate": treatment_fill_rate,
            "treatment_mean_abs_inventory": mean_abs_inventory,
            "treatment_terminal_inventory": terminal_inventory,
            "treatment_pnl_cents": treatment_pnl_cents,
            "unique_trades": unique_trades,
            "market_volume": market_volume,
            "realized_volatility_5m_bps": realized_volatility,
            "realized_volatility_5m_observations": realized_volatility_observations,
            "runtime_s": float(manifest["wall_clock_seconds"]),
            "fallback_rate": float(fallback_values.mean()) if has_llm_diagnostics else None,
            "timeout_rate": float(timeout_values.mean()) if len(timeout_values) else None,
            "latency_ms_p50": float(llm_latency.median()) if len(llm_latency) else None,
            "latency_ms_p95": float(llm_latency.quantile(0.95)) if len(llm_latency) else None,
            "tokens_total": int(decisions["llm_tokens_in"].fillna(0).sum() + decisions["llm_tokens_out"].fillna(0).sum()) if has_llm_diagnostics else None,
            "fundamental_correcting_rate": correcting,
            "fundamental_correcting_rate_shock_window": correcting_shock,
            "recovery_time_s_provisional": recovery,
            "recovery_threshold_cents_provisional": recovery_threshold,
            "shock_30m_midpoint_error_tw": shock_window_error,
            "shock_30m_book_availability": shock_window_availability,
            "shock_30m_overshoot_cents": shock_overshoot,
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="output/raw")
    parser.add_argument("--seed", type=int, default=1001)
    args = parser.parse_args()
    frame = summarize_seed(args.log_root, args.seed)
    print(frame.to_json(orient="records", indent=2))


if __name__ == "__main__":
    main()
