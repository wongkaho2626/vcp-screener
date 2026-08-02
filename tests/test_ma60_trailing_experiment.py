import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma60_trailing_experiment import decide


def _partition(cagr, excess, trades=100, drop5=1.0, mdd=-10):
    return {
        "metrics": {
            "summary": {"cagr_pct": cagr, "trades": trades,
                        "max_drawdown_pct": mdd},
            "exposure_matched_excess_cagr_pct": excess,
            "trade_metrics": {"drop_best_five_net_expectancy_pct": drop5},
        }
    }


def test_decision_requires_every_frozen_improvement_gate():
    result = decide(
        _partition(5, -5), _partition(8, -2, trades=50, drop5=1, mdd=-11),
        {"cagr_pct": 1},
    )
    assert result["verdict"] == "IMPROVES"
    assert all(result["checks"].values())


def test_decision_worsens_when_cagr_and_excess_both_decline():
    result = decide(
        _partition(5, -5), _partition(4, -6, trades=50, drop5=1, mdd=-11),
        {"cagr_pct": 1},
    )
    assert result["verdict"] == "WORSENS"


def test_decision_is_inconclusive_for_mixed_evidence():
    result = decide(
        _partition(5, -5), _partition(8, -6, trades=50, drop5=1, mdd=-11),
        {"cagr_pct": 1},
    )
    assert result["verdict"] == "INCONCLUSIVE"
