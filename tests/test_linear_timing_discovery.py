import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from linear_timing_discovery import (
    FEATURE_NAMES,
    best_future_return,
    causal_features,
    fit_ridge,
    fit_quadratic_ridge,
    fixed_horizon_return,
    fixed_horizon_survival,
    fit_logistic_ridge,
    score_features,
    signals_from_rows,
    signals_with_decay,
    lifecycle_signals_with_decay,
    signals_with_loss_decay,
)
from portfolio_backtest import Config


def bars(values):
    return [
        {"date": f"d{i:02}", "open": value, "high": value + 1,
         "low": value - 1, "close": value, "volume": 1000 + i}
        for i, value in enumerate(values)
    ]


def test_features_are_strictly_invariant_to_appended_future_bars():
    history = bars(list(range(80, 105)))
    original = causal_features(history, 20, 5, 100, 90, 75)
    extended = causal_features(history + bars([500, 600]), 20, 5, 100, 90, 75)
    assert len(original) == len(FEATURE_NAMES) == 15
    assert original == extended


def test_future_label_cannot_look_past_first_hard_stop():
    history = [
        {"date": "d0", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d1", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d2", "open": 99, "high": 100, "low": 89, "close": 90},
        {"date": "d3", "open": 200, "high": 201, "low": 199, "close": 200},
    ]
    value = best_future_return(
        history, 0, 90, Config(commission_bps=0, slippage_bps=0),
    )
    assert value == pytest.approx(-.01)


def test_fixed_horizon_label_stops_before_later_winner():
    history = [
        {"date": "d0", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d1", "open": 100, "high": 101, "low": 99, "close": 100},
        {"date": "d2", "open": 99, "high": 100, "low": 89, "close": 90},
        {"date": "d3", "open": 200, "high": 201, "low": 199, "close": 200},
    ]
    value = fixed_horizon_return(
        history, 0, 90, horizon=3,
        cfg=Config(commission_bps=0, slippage_bps=0),
    )
    assert value == pytest.approx(-.08)


def test_fixed_horizon_survival_is_binary_and_rejects_open_below_stop():
    history = bars([100] * 25)
    assert fixed_horizon_survival(
        history, 0, 90, horizon=20,
        cfg=Config(commission_bps=0, slippage_bps=0),
    ) == 1.0
    history[5]["low"] = 91
    assert fixed_horizon_survival(
        history, 0, 92, horizon=20,
        cfg=Config(commission_bps=0, slippage_bps=0),
    ) == 0.0
    history[1]["open"] = 89
    assert fixed_horizon_survival(
        history, 0, 90, horizon=20,
        cfg=Config(commission_bps=0, slippage_bps=0),
    ) is None


def test_weighted_ridge_fits_and_scores_without_future_fields():
    rows = [
        {"setup_id": "a", "features": [0.0] * 15, "label": 0.0},
        {"setup_id": "b", "features": [1.0] * 15, "label": .2},
    ]
    model = fit_ridge(rows, ridge_lambda=10)
    assert model["fit_rows"] == 2
    assert score_features([1.0] * 15, model) > score_features([0.0] * 15, model)


def test_quadratic_ridge_has_fixed_thirty_term_shape_and_scores():
    rows = [
        {"setup_id": "a", "features": [-1.0] * 15, "label": .2},
        {"setup_id": "b", "features": [0.0] * 15, "label": 0.0},
        {"setup_id": "c", "features": [1.0] * 15, "label": .2},
    ]
    model = fit_quadratic_ridge(rows)
    assert model["model_type"] == "quadratic"
    assert len(model["coefficients"]) == len(model["feature_names"]) == 30
    assert score_features([1.0] * 15, model) > score_features([0.0] * 15, model)


def test_logistic_ridge_scores_positive_class_higher():
    rows=[{"setup_id":"a","features":[-1.0]*15,"label":0.0},
          {"setup_id":"b","features":[0.0]*15,"label":0.0},
          {"setup_id":"c","features":[1.0]*15,"label":.2}]
    model=fit_logistic_ridge(rows,label_threshold=.1)
    assert model["positive_rows"] == 1
    assert score_features([1.0]*15,model) > score_features([-1.0]*15,model)


def test_signal_selector_takes_first_threshold_crossing_per_setup():
    model = {
        "mean": [0.0] * 15, "std": [1.0] * 15,
        "intercept": 0.0, "coefficients": [1.0] + [0.0] * 14,
    }
    common = {
        "symbol": "AAA", "sector": "Tech", "edge_rank": 80,
        "pattern_stop": 90, "pivot": 100,
    }
    rows = [
        {**common, "setup_id": "a", "signal_date": "d1", "fill_date": "d2",
         "fill_idx": 2, "features": [0.4] + [0.0] * 14},
        {**common, "setup_id": "a", "signal_date": "d2", "fill_date": "d3",
         "fill_idx": 3, "features": [0.8] + [0.0] * 14},
        {**common, "setup_id": "a", "signal_date": "d3", "fill_date": "d4",
         "fill_idx": 4, "features": [1.0] + [0.0] * 14},
    ]
    selected = signals_from_rows(rows, model, .75)
    assert len(selected) == 1
    assert selected[0]["signal_date"] == "d2"


def test_score_decay_exit_is_next_open_after_later_low_score_close():
    model = {
        "mean": [0.0] * 15, "std": [1.0] * 15,
        "intercept": 0.0, "coefficients": [1.0] + [0.0] * 14,
    }
    common = {
        "symbol": "AAA", "sector": "Tech", "edge_rank": 80,
        "pattern_stop": 90, "pivot": 100, "setup_id": "a",
    }
    rows = [
        {**common, "signal_date": "d1", "fill_date": "d2", "fill_idx": 2,
         "features": [.9] + [0.0] * 14},
        {**common, "signal_date": "d2", "fill_date": "d3", "fill_idx": 3,
         "features": [.7] + [0.0] * 14},
        {**common, "signal_date": "d3", "fill_date": "d4", "fill_idx": 4,
         "features": [.4] + [0.0] * 14},
    ]
    selected = signals_with_decay(rows, model, .85, .5)
    assert selected[0]["fill_idx"] == 2
    assert selected[0]["model_exit_idx"] == 4


def test_score_lifecycle_requires_decay_before_second_high_cycle():
    model={"mean":[0.0]*15,"std":[1.0]*15,"intercept":0.0,"coefficients":[1.0]+[0.0]*14}
    common={"symbol":"AAA","sector":"Tech","edge_rank":80,"pattern_stop":90,"pivot":100,"setup_id":"a"}
    scores=[.9,.8,.4,.6,.9,.8,.4]
    rows=[{**common,"signal_date":f"d{i}","fill_date":f"d{i+1}","fill_idx":i+1,
           "features":[score]+[0.0]*14} for i,score in enumerate(scores)]
    selected=lifecycle_signals_with_decay(rows,model,.85,.5,cooldown=2,max_cycles=3)
    assert [row["fill_idx"] for row in selected] == [1,5]
    assert [row["model_exit_idx"] for row in selected] == [3,7]


def test_loss_decay_ignores_low_score_until_close_below_entry_open():
    model={"mean":[0.0]*15,"std":[1.0]*15,"intercept":0.0,"coefficients":[1.0]+[0.0]*14}
    common={"symbol":"AAA","sector":"Tech","edge_rank":80,"pattern_stop":90,"pivot":100,"setup_id":"a"}
    values=[(.9,100,101),(.4,100,102),(.3,100,99)]
    rows=[{**common,"signal_date":f"d{i}","fill_date":f"d{i+1}","fill_idx":i+1,
           "fill_open":op,"close":close,"features":[score]+[0.0]*14}
          for i,(score,op,close) in enumerate(values)]
    selected=signals_with_loss_decay(rows,model,.85,.5)
    assert selected[0]["model_exit_idx"] == 3
