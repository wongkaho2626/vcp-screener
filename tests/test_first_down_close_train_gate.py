import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from first_down_close_train_gate import assess


def cell(cagr, sharpe, pf=1.5, trades=35, trim=.2):
    return {
        "summary": {"cagr_pct": cagr},
        "trade_stats": {"trades": trades, "profit_factor": pf},
        "drop_top_5": {"expectancy_pct": trim},
        "robustness": {"risk_adjusted": {"sharpe": sharpe}},
    }


def test_train_gate_rejects_outlier_fragility():
    assert assess(cell(3, .9), cell(2, .6))["pass"]
    result = assess(cell(3, .9, trim=-.01), cell(2, .6))
    assert not result["pass"]
    assert not result["open_validation"]
