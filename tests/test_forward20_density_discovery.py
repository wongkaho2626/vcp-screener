import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
from forward20_density_discovery import assess, select


def cell(cagr=10, trades=40, sharpe=.75, pf=1.21, trim=.1, mdd=-5):
    return {"summary":{"cagr_pct":cagr,"max_drawdown_pct":mdd},
            "trade_stats":{"trades":trades,"profit_factor":pf},
            "drop_top_5":{"expectancy_pct":trim},
            "robustness":{"risk_adjusted":{"sharpe":sharpe}}}


def test_density_gate_and_tie_prefer_higher_percentile():
    assert assess(cell())["eligible"]
    cells={"p70":cell(cagr=12),"p75":cell(cagr=12.1),"p80":cell(cagr=11)}
    assert select(cells)["selected"] == "p75"


def test_density_gate_rejects_subten_cagr():
    assert not assess(cell(cagr=9.99))["eligible"]
