from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from cross_sectional_leadership_discovery import (
    active_symbol_rows,
    discovery_backtest_score,
    leadership_states,
    lifecycle_signals,
)


def row(symbol: str, date: str, fill_date: str, fill_idx: int, features: list[float],
        *, setup: str | None = None, as_of: str = "2020-01-01", edge: float = 70,
        close: float = 110, stop: float = 90) -> dict:
    return {
        "setup_id": setup or f"{symbol}|{as_of}|0", "symbol": symbol,
        "sector": "Tech", "as_of_date": as_of, "signal_date": date,
        "fill_date": fill_date, "fill_idx": fill_idx, "edge_rank": edge,
        "pattern_stop": stop, "pivot": 100, "close": close,
        "features": features,
    }


def test_active_rows_deduplicate_symbol_to_latest_setup_then_edge() -> None:
    rows = [
        row("AAA", "2020-02-01", "2020-02-02", 10, [0] * 15,
            setup="old", as_of="2020-01-01", edge=90),
        row("AAA", "2020-02-01", "2020-02-02", 10, [0] * 15,
            setup="new-low", as_of="2020-01-15", edge=60),
        row("AAA", "2020-02-01", "2020-02-02", 10, [0] * 15,
            setup="new-high", as_of="2020-01-15", edge=80),
    ]
    assert active_symbol_rows(rows)[0]["setup_id"] == "new-high"


def test_leadership_uses_same_date_cross_section_and_singleton_is_half() -> None:
    # Feature positions 5 and 7 are ret_5 and ret_20 in the frozen row schema.
    a = [0.0] * 15
    b = [0.0] * 15
    a[5], a[7], a[9] = .10, .20, .05
    b[5], b[7], b[9] = -.10, -.20, -.05
    states = leadership_states([
        row("AAA", "2020-02-01", "2020-02-02", 10, a),
        row("BBB", "2020-02-01", "2020-02-02", 10, b),
        row("CCC", "2020-02-03", "2020-02-04", 12, a),
    ])
    by_symbol = {(x["signal_date"], x["symbol"]): x for x in states}
    assert by_symbol[("2020-02-01", "AAA")]["leadership"] == 1.0
    assert by_symbol[("2020-02-01", "BBB")]["leadership"] == 0.0
    assert by_symbol[("2020-02-03", "CCC")]["leadership"] == 0.5


def test_lifecycle_requires_fresh_cross_and_schedules_next_open_exit() -> None:
    states = []
    for i, (leadership, above_sma) in enumerate([
        (.60, True), (.75, True), (.80, True), (.35, False),
        (.75, True), (.35, False), (.75, True), (.35, False),
        (.75, True),
    ]):
        states.append({
            **row("AAA", f"2020-02-{i+1:02d}", f"2020-03-{i+1:02d}", i + 10,
                  [0] * 15, setup="one"),
            "leadership": leadership, "above_sma20": above_sma,
        })
    signals = lifecycle_signals(states, entry_threshold=.70, exit_threshold=.40,
                                max_attempts=3)
    assert [x["attempt"] for x in signals] == [1, 2, 3]
    assert [x["fill_idx"] for x in signals] == [11, 14, 16]
    assert [x["model_exit_idx"] for x in signals] == [13, 15, 17]


def test_appended_future_state_cannot_change_existing_signal() -> None:
    base = [
        {**row("AAA", "2020-02-01", "2020-02-02", 10, [0] * 15),
         "leadership": .60, "above_sma20": True},
        {**row("AAA", "2020-02-02", "2020-02-03", 11, [0] * 15),
         "leadership": .75, "above_sma20": True},
    ]
    future = {**row("AAA", "2020-02-03", "2020-02-04", 12, [0] * 15),
              "leadership": .80, "above_sma20": True}
    first = lifecycle_signals(base)
    extended = lifecycle_signals([*base, future])
    assert first[0] == extended[0]


def test_discovery_score_uses_reduced_denominator_and_no_oos_cap() -> None:
    cell = {
        "trade_stats": {"profit_factor": 1.35, "expectancy_pct": .78,
                        "win_rate": .42, "payoff_ratio": 1.86},
        "robustness": {
            "significance": {"t_statistic": .56, "psr_vs_zero": .71,
                             "effective_sample_size": 623,
                             "approximate_dsr": {"probability": .008}},
            "risk_adjusted": {"sharpe": .35, "sortino": .52, "calmar": .23},
            "risk": {"max_drawdown": -.038},
            "stability": {"positive_months": .36},
            "block_bootstrap": {"cagr": {"p05": -.01, "median": .008}},
        },
    }
    score = discovery_backtest_score(cell)
    assert score["measured_total"] == 27
    assert score["measured_denominator"] == 83
    assert score["reduced_denominator_normalized_raw_score"] == 33
    assert score["caps_applied"] == [
        {"reason": "unresolved survivorship bias / incomplete delisted coverage", "cap": 20},
        {"reason": "no formal out-of-sample or walk-forward segment", "cap": 55},
    ]
    assert score["final_score"] == 20
