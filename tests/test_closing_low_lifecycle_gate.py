import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from closing_low_lifecycle_gate import assess


def cell(*, trades=60, cagr=10, sharpe=.5, pf=1.21, mdd=-10, trim=.1):
    return {
        "summary": {"cagr_pct": cagr, "max_drawdown_pct": mdd},
        "trade_stats": {"trades": trades, "profit_factor": pf},
        "drop_top_5": {"expectancy_pct": trim},
        "robustness": {"risk_adjusted": {"sharpe": sharpe}},
    }


def test_discovery_gate_enforces_frozen_thresholds():
    assert assess(cell())["passed"]
    assert not assess(cell(cagr=9.99))["passed"]
    assert not assess(cell(trades=59))["passed"]


def test_internal_holdout_uses_stricter_thresholds():
    assert assess(cell(trades=30, cagr=15, sharpe=.75), holdout=True)["passed"]
    assert not assess(cell(trades=29, cagr=15, sharpe=.75), holdout=True)["passed"]
