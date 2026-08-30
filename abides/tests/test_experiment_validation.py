import unittest

import numpy as np
import pandas as pd
import requests

from agent.experiment.llm_policy import LLMPolicy
from agent.experiment.paired_oracle import PairedFundamentalOracle
from analysis.validation import gate_metric_sanity
from analysis.metrics import time_weighted_mean


def _symbol_config(seed):
    return {
        "JPM": {
            "r_bar": 100000,
            "kappa": 1.67e-12,
            "fund_vol": 1e-8,
            "megashock_lambda_a": 2.77778e-13,
            "megashock_mean": 1e3,
            "megashock_var": 5e4,
            "random_state": np.random.RandomState(seed),
        }
    }


class ExperimentValidationTests(unittest.TestCase):
    def test_metric_fixture_passes(self):
        self.assertTrue(gate_metric_sanity().passed)

    def test_time_weighted_mean_excludes_missing_intervals(self):
        start = pd.Timestamp("2019-06-28 10:00:00")
        times = [start + pd.Timedelta(seconds=i) for i in range(4)]
        observed = time_weighted_mean(
            times, [10.0, None, 20.0, 20.0], start=start, end=times[-1]
        )
        self.assertEqual(observed, 15.0)

    def test_paired_oracle_is_query_independent_and_repeatable(self):
        market_open = pd.Timestamp("2019-06-28 09:30:00")
        market_close = market_open + pd.Timedelta(minutes=5)
        shock_time = market_open + pd.Timedelta(minutes=2)
        first = PairedFundamentalOracle(
            market_open, market_close, _symbol_config(123),
            shock_time=shock_time, shock_magnitude=8000,
        )
        second = PairedFundamentalOracle(
            market_open, market_close, _symbol_config(123),
            shock_time=shock_time, shock_magnitude=8000,
        )
        # Query only one instance at arbitrary times; its fixed path cannot change.
        before = first.fundamentals["JPM"].copy()
        first.observePrice("JPM", market_open + pd.Timedelta(seconds=17), sigma_n=0)
        first.observePrice("JPM", market_open + pd.Timedelta(seconds=91), sigma_n=0)
        pd.testing.assert_series_equal(before, first.fundamentals["JPM"])
        pd.testing.assert_series_equal(first.fundamentals["JPM"], second.fundamentals["JPM"])
        jump = int(first.fundamentals["JPM"].loc[shock_time] - first.fundamentals["JPM"].loc[shock_time - pd.Timedelta(seconds=1)])
        self.assertGreater(jump, 7000)

    def test_llm_json_and_timeout_helpers(self):
        self.assertEqual(LLMPolicy._parse_json('{"side": "BUY"}'), {"side": "BUY"})
        fenced = "```json\n{\"side\": \"SELL\"}\n```"
        self.assertEqual(LLMPolicy._parse_json(fenced), {"side": "SELL"})
        self.assertTrue(LLMPolicy._is_timeout(requests.exceptions.Timeout()))


if __name__ == "__main__":
    unittest.main()
