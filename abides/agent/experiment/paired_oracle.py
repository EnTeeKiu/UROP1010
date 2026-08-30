"""Query-independent fundamental oracle for paired experimental runs.

ABIDES' sparse oracle advances its RNG whenever an agent asks for a value. Once
treatment policies create different event streams, that makes the fundamental path
condition-dependent. This oracle precomputes one value per second at construction,
so every condition with the same master seed observes the same exogenous path.
"""

from __future__ import annotations

from math import exp, sqrt

import numpy as np
import pandas as pd

from util.util import log_print


class PairedFundamentalOracle:
    def __init__(
        self,
        mkt_open,
        mkt_close,
        symbols,
        *,
        shock_time=None,
        shock_magnitude=0,
        frequency="1s",
    ):
        self.mkt_open = pd.Timestamp(mkt_open)
        self.mkt_close = pd.Timestamp(mkt_close)
        self.symbols = symbols
        self.shock_time = pd.Timestamp(shock_time) if shock_time is not None else None
        self.shock_magnitude = int(shock_magnitude)
        self.frequency = frequency
        self.fundamentals = {}
        self.f_log = {}

        for symbol, params in symbols.items():
            series = self._generate_path(params)
            self.fundamentals[symbol] = series
            self.f_log[symbol] = [
                {"FundamentalTime": timestamp, "FundamentalValue": int(value)}
                for timestamp, value in series.items()
            ]

        log_print(
            "PairedFundamentalOracle precomputed {} paths at {} frequency; shock_time={}, shock_magnitude={}",
            len(self.fundamentals), self.frequency, self.shock_time, self.shock_magnitude,
        )

    def _generate_path(self, params) -> pd.Series:
        rng = params["random_state"]
        index = pd.date_range(self.mkt_open, self.mkt_close, freq=self.frequency)
        values = np.empty(len(index), dtype=np.int64)
        base_mean = float(params["r_bar"])
        values[0] = int(round(base_mean))

        gamma = float(params.get("kappa", 0.0))
        theta = float(params.get("fund_vol", 0.0))
        shock_lambda = float(params.get("megashock_lambda_a", 0.0))
        shock_mean = float(params.get("megashock_mean", 0.0))
        shock_std = sqrt(float(params.get("megashock_var", 0.0)))
        next_megashock = None
        if shock_lambda > 0:
            wait_ns = rng.exponential(scale=1.0 / shock_lambda)
            next_megashock = self.mkt_open + pd.Timedelta(wait_ns, unit="ns")

        previous = float(values[0])
        previous_time = index[0]
        for position in range(1, len(index)):
            timestamp = index[position]
            adjustment = 0.0
            while next_megashock is not None and next_megashock <= timestamp:
                magnitude = rng.normal(loc=shock_mean, scale=shock_std)
                adjustment += magnitude if rng.randint(2) == 0 else -magnitude
                wait_ns = rng.exponential(scale=1.0 / shock_lambda)
                next_megashock = next_megashock + pd.Timedelta(wait_ns, unit="ns")

            active_mean = base_mean
            if self.shock_time is not None and timestamp >= self.shock_time:
                active_mean += self.shock_magnitude
                if previous_time < self.shock_time:
                    adjustment += self.shock_magnitude

            delta_ns = int((timestamp - previous_time) / np.timedelta64(1, "ns"))
            if gamma > 0:
                decay = exp(-gamma * delta_ns)
                location = active_mean + (previous - active_mean) * decay
                # Preserve the scale convention used by SparseMeanRevertingOracle.
                scale = (theta / (2 * gamma)) * (1 - exp(-2 * gamma * delta_ns))
            else:
                location = previous
                scale = 0.0

            value = rng.normal(loc=location, scale=scale) if scale > 0 else location
            previous = float(max(0, int(round(value + adjustment))))
            values[position] = int(previous)
            previous_time = timestamp

        return pd.Series(values, index=index)

    def getDailyOpenPrice(self, symbol, mkt_open=None):
        return int(self.fundamentals[symbol].iloc[0])

    def observePrice(self, symbol, currentTime, sigma_n=1000, random_state=None):
        query_time = min(max(pd.Timestamp(currentTime), self.mkt_open), self.mkt_close)
        series = self.fundamentals[symbol]
        position = int(series.index.searchsorted(query_time, side="right") - 1)
        true_value = int(series.iloc[max(position, 0)])
        if sigma_n == 0:
            observation = true_value
        else:
            if random_state is None:
                raise ValueError("random_state is required for noisy oracle observations")
            observation = int(round(random_state.normal(loc=true_value, scale=sqrt(sigma_n))))
        log_print("Oracle: current fundamental value is {} at {}", true_value, currentTime)
        return observation
