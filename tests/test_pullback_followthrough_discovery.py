from pullback_followthrough_discovery import (
    entry_name,
    entry_variants,
    holdout_gate,
    select_stage_a,
    select_stage_b,
)


def cell(*, trades=40, cagr=10, pf=1.5, trim=1, mdd=-5, sharpe=1, calmar=2):
    return {
        "summary": {"cagr_pct": cagr, "max_drawdown_pct": mdd},
        "trade_stats": {"trades": trades, "profit_factor": pf},
        "drop_top_5": {"expectancy_pct": trim},
        "robustness": {
            "risk_adjusted": {"sharpe": sharpe, "calmar": calmar},
            "risk": {"max_drawdown": mdd / 100},
        },
    }


def test_entry_family_has_exactly_sixteen_unique_prespecified_cells():
    variants = entry_variants()
    assert len(variants) == 16
    assert len({entry_name(row) for row in variants}) == 16
    assert variants[0] == {
        "lookback": 3, "max_depth_pct": 8.0,
        "confirmation": "up_close", "volume_expansion": False,
    }


def test_stage_a_tie_within_point_zero_five_prefers_simpler_order():
    order = ["simple", "complex"]
    cells = {"simple": cell(calmar=1.97), "complex": cell(calmar=2.0)}
    assert select_stage_a(cells, order)["selected"] == "simple"


def test_stage_b_requires_improvement_over_entry_baseline():
    baseline = cell(cagr=10, sharpe=1)
    cells = {
        "ft5_sma10": cell(cagr=9, sharpe=1.1),
        "ft5_sma20": cell(cagr=11, sharpe=.9),
        "ft10_sma20": cell(cagr=11, sharpe=1.1),
    }
    assert select_stage_b(cells, baseline)["selected"] == "ft10_sma20"


def test_holdout_gate_enforces_cagr_sharpe_and_trade_floor():
    assert holdout_gate(cell(cagr=15, sharpe=.75, trades=25))["passed"]
    assert not holdout_gate(cell(cagr=14.99, sharpe=.75, trades=25))["passed"]
    assert not holdout_gate(cell(cagr=15, sharpe=.74, trades=25))["passed"]
    assert not holdout_gate(cell(cagr=15, sharpe=.75, trades=24))["passed"]
