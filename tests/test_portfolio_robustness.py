import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_robustness import (
    analyze,
    effective_sample_size,
    load_returns,
    max_drawdown,
    probabilistic_sharpe,
    sharpe,
)


def test_core_metrics_on_constant_gain():
    returns = [0.001] * 30
    mdd, duration, drawdowns = max_drawdown(returns)
    assert mdd == 0
    assert duration == 0
    assert all(x == 0 for x in drawdowns)
    assert sharpe(returns) is None


def test_drawdown_magnitude_and_duration():
    mdd, duration, _ = max_drawdown([0.10, -0.20, 0.05, 0.20])
    assert mdd == pytest.approx(-0.20)
    assert duration == 2


def test_effective_sample_penalizes_positive_autocorrelation():
    persistent = [x for value in ([0.01, -0.01] * 25) for x in (value, value)]
    n_eff, _ = effective_sample_size(persistent)
    assert 1 < n_eff < len(persistent)


def test_probabilistic_sharpe_uses_daily_not_annualized_scale():
    returns = [0.004, -0.004, 0.003, -0.003] * 100 + [0.0001]
    psr = probabilistic_sharpe(returns)
    assert psr is not None
    assert 0.45 < psr < 0.65


def test_analysis_is_reproducible_and_complete():
    returns = [0.004, -0.002, 0.003, -0.001] * 40
    dates = pd.Series(pd.date_range("2020-01-01", periods=len(returns), freq="B"))
    one = analyze(dates, returns, trials=12, iterations=20, block_size=4, seed=7, split=.7)
    two = analyze(dates, returns, trials=12, iterations=20, block_size=4, seed=7, split=.7)
    assert one == two
    assert one["performance"]["cagr"] > 0
    assert one["risk"]["max_drawdown"] < 0
    assert one["significance"]["approximate_dsr"]["benchmark_sharpe"] > 0
    assert 0 <= one["stability"]["positive_months"] <= 1


def test_load_equity_converts_to_returns(tmp_path):
    path = tmp_path / "equity.csv"
    pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"], "equity": [100, 110, 99]}).to_csv(path, index=False)
    dates, returns = load_returns(str(path), "date", None, "equity")
    assert len(dates) == 2
    assert returns == pytest.approx([.1, -.1])
