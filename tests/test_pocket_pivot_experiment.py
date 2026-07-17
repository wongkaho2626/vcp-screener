"""Tests for the prespecified pullback versus Pocket Pivot experiment."""

import os
import sys
import csv
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from pocket_pivot_experiment import SEGMENTS, _subset, _write_comparison, run_experiment
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


def test_subset_uses_as_of_date_and_inclusive_chronological_bounds():
    dets = {
        "AAA": [
            {"as_of_date": "2021-12-31", "forward_outcome": {"exit_date": "2022-02-01"}},
            {"as_of_date": "2022-01-01", "forward_outcome": {"exit_date": "2021-12-01"}},
        ]
    }
    out = _subset(dets, "2016-01-01", "2021-12-31")
    assert [row["as_of_date"] for row in out["AAA"]] == ["2021-12-31"]


def test_experiment_freezes_hypothesis_and_reuses_identical_config():
    cfg = Config(commission_bps=7.0, slippage_bps=9.0)
    with patch("pocket_pivot_experiment.run_portfolio", side_effect=lambda *args, **kwargs: empty_result()) as run:
        result = run_experiment({}, {}, cfg)

    assert run.call_count == 2 + 2 * len(SEGMENTS)
    assert {call.kwargs["entry_rule"] for call in run.call_args_list} == {"pullback", "pocket_pivot"}
    assert all(call.args[2] is cfg for call in run.call_args_list)
    hypothesis = result["frozen_hypothesis"]
    assert hypothesis["scan_window_sessions"] == 10
    assert hypothesis["entry"] == "next session open"
    assert hypothesis["forward_outcome_used_for_pocket_pivot"] is False
    assert hypothesis["threshold_sweep"] is False
    assert list(result["segments"]) == [name for name, _, _ in SEGMENTS]


def test_comparison_writer_aligns_dates_and_treats_missing_leg_as_cash(tmp_path):
    pullback = [{
        "date": "2020-01-02", "portfolio_return": 0.01,
        "exposure_matched_excess_return": 0.006,
    }]
    pocket_pivot = [{
        "date": "2020-01-03", "portfolio_return": 0.02,
        "exposure_matched_excess_return": 0.015,
    }]
    path = tmp_path / "comparison.csv"
    _write_comparison(path, pullback, pocket_pivot)
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert [row["date"] for row in rows] == ["2020-01-02", "2020-01-03"]
    assert float(rows[0]["return_lift"]) == -0.01
    assert float(rows[1]["excess_lift"]) == 0.015
