"""Tests for the prespecified Fibonacci-retracement Pocket Pivot experiment."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from fib_pocket_pivot_experiment import (
    ROBUSTNESS_VARIANTS,
    RULES,
    SEGMENTS,
    run_experiment,
)
from portfolio_backtest import Config


def empty_result() -> dict:
    return {
        "summary": {
            "signals": 0,
            "trades": 0,
            "end_value": 100_000.0,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "rejected": {},
        },
        "trades": [],
        "equity_curve": [],
    }


def test_experiment_freezes_hypothesis_and_runs_all_rules_and_robustness():
    cfg = Config(commission_bps=7.0, slippage_bps=9.0)
    with patch(
        "fib_pocket_pivot_experiment.run_portfolio",
        side_effect=lambda *args, **kwargs: empty_result(),
    ) as run:
        result = run_experiment({}, {}, cfg)

    expected_calls = len(RULES) * (1 + len(SEGMENTS)) + len(ROBUSTNESS_VARIANTS)
    assert run.call_count == expected_calls
    assert {call.kwargs["entry_rule"] for call in run.call_args_list} == set(RULES)
    assert all(call.args[2] is cfg for call in run.call_args_list)

    robustness_params = [
        call.kwargs["entry_params"]
        for call in run.call_args_list
        if call.kwargs.get("entry_params")
    ]
    assert robustness_params == [params for _, params in ROBUSTNESS_VARIANTS]

    hypothesis = result["frozen_hypothesis"]
    assert hypothesis["retracement"] == 0.382
    assert hypothesis["wait_window_sessions"] == 10
    assert hypothesis["no_touch_means_no_trade"] is True
    assert hypothesis["forward_outcome_used"] is False
    assert hypothesis["threshold_sweep"] is False
    assert list(result["segments"]) == [name for name, _, _ in SEGMENTS]
    assert list(result["robustness_not_adopted"]) == [
        label for label, _ in ROBUSTNESS_VARIANTS
    ]
