import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from loss_distribution_exit_train_gate import assess


def cell(cagr, sharpe, pf=1.5, trades=35, trim=.2, exit_pf=1.2):
    return {
        "summary": {"cagr_pct": cagr},
        "trade_stats": {"trades": trades, "profit_factor": pf},
        "distribution_trade_stats": {"profit_factor": exit_pf},
        "drop_top_5": {"expectancy_pct": trim},
        "robustness": {"risk_adjusted": {"sharpe": sharpe}},
    }


def test_train_gate_requires_loss_exit_attribution():
    assert assess(cell(3, .9), cell(2, .6))["pass"]
    result = assess(cell(3, .9, exit_pf=.8), cell(2, .6))
    assert not result["pass"]
    assert not result["checks"]["loss_distribution_exit_pf>1.0"]
