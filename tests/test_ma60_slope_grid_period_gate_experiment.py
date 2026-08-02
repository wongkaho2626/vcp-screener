"""Focused tests for the frozen MA60 slope-window grid."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma60_slope_grid_period_gate_experiment import (  # noqa: E402
    SLOPE_WINDOWS,
    select_train_slope,
    validation_passes,
)


def _cell(slope, *, trades=20, cagr=5, excess=1, pf=1.5, mdd=-20, trim=1):
    return {
        "slope_sessions": slope,
        "metrics": {
            "summary": {"trades": trades, "cagr_pct": cagr,
                        "max_drawdown_pct": mdd},
            "exposure_matched_excess_cagr_pct": excess,
            "trade_metrics": {"net_profit_factor": pf,
                              "drop_best_five_net_expectancy_pct": trim},
        },
    }


def test_grid_is_exactly_ten_twenty_thirty_forty():
    assert SLOPE_WINDOWS == (10, 20, 30, 40)


def test_train_selection_requires_all_gates_and_breaks_ties_shorter():
    cells = [
        _cell(10, excess=2),
        _cell(20, excess=2),
        _cell(30, trades=14, excess=9),
        _cell(40, trim=-1, excess=8),
    ]
    qualified, selected = select_train_slope(cells)
    assert [row["slope_sessions"] for row in qualified] == [10, 20]
    assert selected["slope_sessions"] == 10


def test_validation_requires_thirty_trades_and_every_economic_gate():
    assert validation_passes(_cell(20, trades=30)) is True
    assert validation_passes(_cell(20, trades=29)) is False
    assert validation_passes(_cell(20, trades=30, excess=-0.01)) is False
