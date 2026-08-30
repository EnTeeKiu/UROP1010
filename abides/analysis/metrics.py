"""Primary metric primitives used by validation and later analysis.

The functions in this module deliberately operate on event-driven observations.  A
value is treated as constant until the next observation, which is the convention
needed for time-weighted market-quality metrics.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def time_weighted_mean(
    times: Iterable,
    values: Iterable,
    *,
    start=None,
    end=None,
) -> float:
    """Return the stepwise time-weighted mean over ``[start, end]``.

    Observations with missing values are ignored.  There must be an observation at
    or before ``start`` so that the value at the beginning of the interval is known.
    """
    frame = pd.DataFrame({
        "time": pd.to_datetime(list(times)),
        "value": pd.to_numeric(list(values), errors="coerce"),
    }).dropna(subset=["time"]).sort_values("time")

    if frame.empty or not frame["value"].notna().any():
        raise ValueError("time_weighted_mean requires at least one valid observation")

    start_ts = pd.Timestamp(start) if start is not None else frame["time"].iloc[0]
    end_ts = pd.Timestamp(end) if end is not None else frame["time"].iloc[-1]
    if end_ts <= start_ts:
        raise ValueError("end must be later than start")

    prior = frame[frame["time"] <= start_ts].tail(1)
    if prior.empty:
        raise ValueError("an observation at or before start is required")

    interior = frame[(frame["time"] > start_ts) & (frame["time"] < end_ts)]
    window = pd.concat([prior.assign(time=start_ts), interior], ignore_index=True)
    next_times = window["time"].shift(-1)
    next_times.iloc[-1] = end_ts
    durations_ns = (next_times - window["time"]).dt.total_seconds().to_numpy()
    values_arr = window["value"].to_numpy(dtype=float)
    valid = np.isfinite(values_arr)
    duration = durations_ns[valid].sum()
    if duration <= 0:
        raise ValueError("metric window has zero valid duration")
    return float(np.dot(values_arr[valid], durations_ns[valid]) / duration)


def midpoint_error_tw(book_l1: pd.DataFrame, fundamental: pd.DataFrame, *, start, end) -> float:
    """Time-weighted absolute midpoint error against the latest fundamental."""
    book = book_l1[["time", "midpoint"]].sort_values("time")
    fund = fundamental[["time", "value"]].dropna().sort_values("time")
    aligned = pd.merge_asof(book, fund, on="time", direction="backward")
    aligned["error"] = (aligned["midpoint"] - aligned["value"]).abs()
    return time_weighted_mean(aligned["time"], aligned["error"], start=start, end=end)


def quoted_spread_tw(book_l1: pd.DataFrame, *, start, end) -> float:
    """Time-weighted best-ask minus best-bid spread."""
    book = book_l1.copy()
    spread = book["best_ask"].astype(float) - book["best_bid"].astype(float)
    return time_weighted_mean(book["time"], spread, start=start, end=end)


def depth_at_touch_tw(book_l1: pd.DataFrame, *, start, end) -> float:
    """Time-weighted combined displayed size at the best bid and ask."""
    book = book_l1.copy()
    depth = book["best_bid_sz"].astype(float) + book["best_ask_sz"].astype(float)
    return time_weighted_mean(book["time"], depth, start=start, end=end)


def recovery_time_s(
    times: Iterable,
    midpoints: Iterable,
    *,
    shock_time,
    new_fundamental: float,
    threshold: float,
    hold_s: float,
) -> Optional[float]:
    """Return seconds from shock until price enters and continuously holds the band.

    The event-driven midpoint is considered constant until the next observation.
    ``None`` is returned when the observed data never proves a full hold interval.
    """
    frame = pd.DataFrame({
        "time": pd.to_datetime(list(times)),
        "midpoint": pd.to_numeric(list(midpoints), errors="coerce"),
    }).dropna().sort_values("time")
    shock_ts = pd.Timestamp(shock_time)
    frame = frame[frame["time"] >= shock_ts].reset_index(drop=True)
    if len(frame) < 2:
        return None

    within_start = None
    for idx in range(len(frame) - 1):
        current_time = frame.loc[idx, "time"]
        next_time = frame.loc[idx + 1, "time"]
        within = abs(float(frame.loc[idx, "midpoint"]) - new_fundamental) <= threshold
        if within:
            if within_start is None:
                within_start = current_time
            if (next_time - within_start).total_seconds() >= hold_s:
                return float((within_start - shock_ts).total_seconds())
        else:
            within_start = None
    return None
