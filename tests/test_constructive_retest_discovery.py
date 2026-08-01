"""Selection-gate tests for constructive-retest discovery."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from constructive_retest_discovery import eligible


def cell(trades=30, cagr=2, sharpe=.8, pf=1.5, trim=.2):
    return {
        "summary": {"cagr_pct": cagr},
        "trade_stats": {"trades": trades, "profit_factor": pf},
        "drop_top_5": {"expectancy_pct": trim},
        "robustness": {"risk_adjusted": {"sharpe": sharpe}},
    }


def test_eligible_requires_every_prespecified_gate():
    ok, failed = eligible(cell(), baseline_sharpe=.5)
    assert ok and failed == []

    ok, failed = eligible(cell(trim=-.1), baseline_sharpe=.5)
    assert not ok
    assert failed == ["drop_top_5_expectancy>0"]
