"""Focused tests for the frozen MA10–60 grid and sequential gates."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma10_60_3r_trailing_grid_experiment import (  # noqa: E402
    MA_PERIODS,
    final_decision,
    select_train_candidate,
    validation_passes,
)


def _cell(period, *, trades=20, cagr=5, excess=1, pf=1.5, mdd=-20, trim=1):
    return {
        "ma_period": period,
        "metrics": {
            "summary": {"trades": trades, "cagr_pct": cagr,
                        "max_drawdown_pct": mdd},
            "exposure_matched_excess_cagr_pct": excess,
            "trade_metrics": {"net_profit_factor": pf,
                              "drop_best_five_net_expectancy_pct": trim},
        },
    }


def test_grid_is_exactly_ma10_through_ma60_by_ten():
    assert MA_PERIODS == (10, 20, 30, 40, 50, 60)


def test_train_selection_requires_every_gate_and_breaks_ties_shorter():
    cells = [
        _cell(10, excess=2),
        _cell(20, excess=2),
        _cell(30, trades=14, excess=9),
        _cell(40, trim=-0.1, excess=8),
    ]
    qualified, selected = select_train_candidate(cells)
    assert [row["ma_period"] for row in qualified] == [10, 20]
    assert selected["ma_period"] == 10


def test_validation_requires_thirty_trades_and_positive_robust_metrics():
    assert validation_passes(_cell(10, trades=30)) is True
    assert validation_passes(_cell(10, trades=29)) is False
    assert validation_passes(_cell(10, trades=30, mdd=-30.01)) is False


def test_final_decision_compares_selected_oos_with_frozen_ma60_incumbent():
    incumbent = _cell(60, trades=99, cagr=6, excess=-5, mdd=-23)
    challenger = _cell(20, trades=40, cagr=7, excess=-4, mdd=-24, trim=1)
    result = final_decision(incumbent, challenger, {"cagr_pct": 1})
    assert result["verdict"] == "IMPROVES"
    assert all(result["checks"].values())


def test_final_decision_is_inconclusive_when_outlier_gate_fails():
    incumbent = _cell(60, trades=99, cagr=6, excess=-5, mdd=-23)
    challenger = _cell(20, trades=40, cagr=7, excess=-4, mdd=-24, trim=-1)
    result = final_decision(incumbent, challenger, {"cagr_pct": 1})
    assert result["verdict"] == "INCONCLUSIVE"
