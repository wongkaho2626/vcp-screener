from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from forward20_chandelier_discovery import chandelier_signals
from forward20_knn_discovery import analogue_score, fit_analogue_model
from dual_momentum_lifecycle_discovery import (
    entry_state as dual_momentum_entry_state,
    lifecycle_signals as dual_momentum_lifecycle_signals,
    momentum as dual_momentum,
    next_sma20_exit,
)
from sec_form4_purchase_coverage import open_market_purchases
from sec_filing_window_discovery import filing_window_signals, qualifying_event
from prove_it_lifecycle_discovery import lifecycle_signals
from rsi2_lifecycle_discovery import lifecycle_signals as rsi_lifecycle_signals, rsi2
from sma20_open_recovery_discovery import (
    lifecycle_signals as sma20_recovery_signals,
    opening_limit_trigger,
    recovery_exit_index,
)
from undercut_reclaim_discovery import undercut_signals


def _row(setup: str, signal_date: str, fill_idx: int, feature: float = 1.0) -> dict:
    return {
        "setup_id": setup, "symbol": "A", "sector": "Tech",
        "signal_date": signal_date, "fill_date": f"F{fill_idx}",
        "fill_idx": fill_idx, "fill_open": 100.0, "close": 100.0,
        "edge_rank": 80.0, "pattern_stop": 92.0, "pivot": 105.0,
        "features": [feature],
    }


def test_filing_window_is_strictly_after_filing_and_next_open_fixed_exit():
    events = {"A": [{"filed": "2020-01-02", "accession": "x", "form": "10-Q",
                     "eps_growth": .3, "revenue_growth": .2}]}
    same_day = _row("s", "2020-01-02", 5)
    next_day = _row("s", "2020-01-03", 6)
    assert qualifying_event(same_day, events) is None
    assert qualifying_event(next_day, events)["age_days"] == 1
    signals = filing_window_signals([same_day, next_day], events)
    assert signals[0]["signal_date"] == "2020-01-03"
    assert signals[0]["model_exit_idx"] == 26


def test_analogue_score_gives_each_setup_one_vote():
    rows = [
        {**_row("many", f"2020-01-{i:02d}", i, 0.0), "label": 0.0}
        for i in range(1, 11)
    ] + [{**_row("one", "2020-02-01", 20, 1.0), "label": 1.0}]
    model = fit_analogue_model(rows, k=2)
    assert analogue_score([0.5], model) == .5


def test_chandelier_exit_is_scheduled_after_close_confirmation():
    closes = [100.0] * 20 + [111.0, 120.0, 100.0, 100.0]
    bars = [{"date": f"D{i}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1_000_000}
            for i, close in enumerate(closes)]
    entry = _row("s", "D19", 20, 1.0)
    model = {"mean": [0.0], "std": [1.0], "intercept": 0.0,
             "coefficients": [1.0], "model_type": "linear"}
    signals = chandelier_signals([entry], model, {"A": bars}, .8, -.5)
    assert signals[0]["model_exit_idx"] == 23


def test_form4_parser_keeps_only_nonderivative_open_market_acquisitions(tmp_path):
    xml = """<ownershipDocument><nonDerivativeTable>
      <nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>100</value></transactionShares>
      <transactionPricePerShare><value>25.5</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts>
      </nonDerivativeTransaction>
      <nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>50</value></transactionShares>
      <transactionPricePerShare><value>30</value></transactionPricePerShare>
      <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts>
      </nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    path = tmp_path / "form4.xml"
    path.write_text(xml)
    assert open_market_purchases(path) == [{"shares": "100", "price": "25.5"}]


def test_undercut_reclaim_uses_shakeout_low_and_next_open():
    bars = [
        {"date": "d0", "open": 101, "high": 102, "low": 100, "close": 101,
         "volume": 1_000_000},
        {"date": "d1", "open": 101, "high": 102, "low": 98.5, "close": 100.5,
         "volume": 1_000_000},
        {"date": "d2", "open": 101, "high": 103, "low": 100, "close": 102,
         "volume": 1_000_000},
    ]
    detection = {"as_of_date": "d0", "sector": "Tech", "vcp_pattern": {
        "pivot_price": 105, "contractions": [{"low_price": 100}],
    }}
    with patch("undercut_reclaim_discovery.compute_edge_rank",
               return_value={("A", "d0"): {"edge_rank": 80}}):
        signals = undercut_signals({"A": [detection]}, {"A": bars})
    assert signals[0]["signal_date"] == "d1"
    assert signals[0]["fill_date"] == "d2"
    assert signals[0]["pattern_stop"] == 98.5


def test_prove_it_lifecycle_requires_reset_before_reentry():
    model = {"mean": [0.0], "std": [1.0], "intercept": 0.0,
             "coefficients": [1.0], "model_type": "linear"}
    scores = [1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    rows = []
    for i, score in enumerate(scores):
        rows.append({**_row("s", f"d{i}", i + 1, score),
                     "fill_date": f"d{i + 1}"})
    bars = [{"date": f"d{i}", "open": 100, "high": 101, "low": 98,
             "close": (99 if i == 5 else 100), "volume": 1_000_000}
            for i in range(15)]
    signals = lifecycle_signals(rows, model, {"A": bars}, .8, .2,
                                cooldown=5, max_attempts=3)
    assert len(signals) == 2
    assert signals[0]["model_exit_idx"] == 6
    assert signals[1]["fill_idx"] == 7


def test_rsi2_lifecycle_enters_oversold_and_exits_after_sma5_recovery():
    closes = [100, 95, 90, 92, 100, 101, 102]
    bars = [{"date": f"d{i}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1_000_000}
            for i, close in enumerate(closes)]
    row = {**_row("s", "d2", 3), "fill_date": "d3"}
    assert rsi2(bars, 2) == 0
    signals = rsi_lifecycle_signals([row], {"A": bars})
    assert len(signals) == 1
    assert signals[0]["fill_idx"] == 3
    assert signals[0]["model_exit_idx"] == 5


def test_dual_momentum_state_uses_12_1_and_fresh_five_day_cross():
    bars = []
    for i in range(260):
        close = 100 + i * .10
        bars.append({"date": f"d{i:03d}", "open": close, "high": close,
                     "low": close, "close": close, "volume": 1_000_000})
    bars[252]["close"] = bars[247]["close"]
    bars[253]["close"] = bars[248]["close"] + 1
    state = dual_momentum_entry_state(bars, 253)
    assert state is not None
    assert state["momentum_12_1"] > 0
    assert state["prior_momentum_5"] <= 0 < state["momentum_5"]
    assert dual_momentum(bars, 253, 5) == state["momentum_5"]


def test_dual_momentum_exit_and_lifecycle_fill_only_next_open():
    bars = []
    for i in range(280):
        close = 100 + i * .10
        bars.append({"date": f"d{i:03d}", "open": close, "high": close + .5,
                     "low": close - .5, "close": close, "volume": 1_000_000})
    bars[252]["close"] = bars[247]["close"]
    bars[253]["close"] = bars[248]["close"] + 1
    bars[257]["close"] = 90
    assert next_sma20_exit(bars, 254) == 258
    rows = [{"setup_id": "ABC|d200|0", "symbol": "ABC", "sector": "Tech",
             "signal_date": bars[i]["date"], "fill_date": bars[i + 1]["date"],
             "fill_idx": i + 1, "edge_rank": 80, "pattern_stop": 80,
             "pivot": 110} for i in range(252, 259)]
    signals = dual_momentum_lifecycle_signals(rows, {"ABC": bars})
    assert len(signals) == 1
    assert signals[0]["signal_date"] == "d253"
    assert signals[0]["fill_date"] == "d254"
    assert signals[0]["model_exit_idx"] == 258


def test_sma20_opening_limit_uses_only_prior_close_and_next_open():
    bars = [{"date": f"d{i:02d}", "open": 100, "high": 102, "low": 99,
             "close": 100, "volume": 1_000_000} for i in range(25)]
    bars[19]["close"] = 105
    bars[20]["open"] = 99
    row = {**_row("s", "d19", 20), "fill_date": "d20", "pattern_stop": 90}
    trigger = opening_limit_trigger(row, bars)
    assert trigger is not None
    assert trigger["limit_price"] == 100.25
    assert trigger["pre_gap_close"] == 105
    assert trigger["raw_entry_price"] == 99
    # The entry decision is unchanged by the entry day's later close/high/low.
    bars[20].update({"close": 1, "high": 500, "low": 1})
    assert opening_limit_trigger(row, bars) == trigger


def test_sma20_gap_recovery_exits_at_next_open_and_bounds_lifecycle():
    bars = [{"date": f"d{i:02d}", "open": 100, "high": 106, "low": 95,
             "close": 100, "volume": 1_000_000} for i in range(40)]
    bars[19]["close"] = 105
    bars[20]["open"] = 99
    bars[22]["close"] = 105
    assert recovery_exit_index(bars, 20, 105, 10) == 23
    rows = [{**_row("s", f"d{i:02d}", i + 1), "fill_date": f"d{i + 1:02d}",
             "pattern_stop": 90} for i in range(19, 25)]
    signals = sma20_recovery_signals(rows, {"A": bars})
    assert len(signals) == 2
    assert signals[0]["signal_date"] == "d19"
    assert signals[0]["fill_date"] == "d20"
    assert signals[0]["model_exit_idx"] == 23
    assert signals[0]["entry_day_stop"] is True
