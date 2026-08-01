import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_backtest import Config
from train_feasibility_audit import (
    best_open_exit,
    best_timed_baseline_signal,
    best_timed_signal,
    exposure_stats,
    standalone_signal_return,
)


def test_exposure_stats_reports_fixed_capital_hurdle():
    portfolio = {
        "summary": {"trades": 2},
        "equity_curve": [
            {"gross_exposure_pct": 0, "positions": 0},
            {"gross_exposure_pct": 10, "positions": 1},
        ],
    }
    result = exposure_stats(portfolio)
    assert result["average_exposure_pct"] == 5
    assert result["invested_sessions_pct"] == 50
    assert result["approx_exposed_capital_return_needed_for_20pct_cagr_pct"] == 400


def test_standalone_return_applies_next_open_costs_and_gap_stop():
    bars = [
        {"open": 100, "high": 101, "low": 99, "close": 100},
        {"open": 100, "high": 101, "low": 99, "close": 100},
        {"open": 90, "high": 91, "low": 89, "close": 90},
    ]
    signal = {"fill_idx": 1, "pattern_stop": 92}
    value = standalone_signal_return(signal, bars, Config())
    assert value == pytest.approx(89.91 / 100.1 - 1)


def test_best_open_exit_cannot_look_past_first_hard_stop():
    bars = [
        {"open": 100, "high": 101, "low": 99, "close": 100},
        {"open": 100, "high": 101, "low": 99, "close": 100},
        {"open": 105, "high": 106, "low": 100, "close": 104},
        {"open": 90, "high": 91, "low": 89, "close": 90},
        {"open": 120, "high": 121, "low": 119, "close": 120},
    ]
    signal = {"fill_idx": 1, "pattern_stop": 92}
    index, value = best_open_exit(signal, bars, Config(commission_bps=0, slippage_bps=0))
    assert index == 2
    assert value == pytest.approx(.05)


def test_best_timed_signal_can_delay_entry_but_not_cross_invalidation():
    bars = [
        {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d01", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d02", "open": 80, "high": 82, "low": 79, "close": 81},
        {"date": "d03", "open": 100, "high": 101, "low": 99, "close": 100},
    ]
    base = {"fill_idx": 1, "pattern_stop": 90, "signal_date": "d00", "fill_date": "d01"}
    signal, value = best_timed_signal(
        base, bars, Config(commission_bps=0, slippage_bps=0), entry_window=3,
    )
    assert signal["fill_idx"] == 2
    assert signal["diagnostic_exit_idx"] == 3
    assert value == pytest.approx(.25)

    invalidated = [bars[0], {**bars[1], "close": 89}, bars[2], bars[3]]
    signal, _ = best_timed_signal(
        base, invalidated, Config(commission_bps=0, slippage_bps=0), entry_window=3,
    )
    assert signal["fill_idx"] == 1


def test_best_timed_baseline_signal_keeps_ordinary_timeout_outcome():
    bars = [
        {"date": f"d{i:02}", "open": open_, "high": open_ + 1,
         "low": open_ - 1, "close": open_}
        for i, open_ in enumerate((100, 100, 80, 100, 100))
    ]
    base = {"fill_idx": 1, "pattern_stop": 70, "signal_date": "d00", "fill_date": "d01"}
    signal, value = best_timed_baseline_signal(
        base, bars, Config(commission_bps=0, slippage_bps=0, max_hold_bars=2),
        entry_window=2,
    )
    assert signal["fill_idx"] == 2
    assert value == pytest.approx(.25)
