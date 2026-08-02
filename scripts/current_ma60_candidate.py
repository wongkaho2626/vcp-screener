"""Canonical user-directed MA60 research candidate.

This module deliberately does not alter the frozen Trial 542/544/551 scripts.
The active research override uses a 10-session MA60 slope despite its known
Trial 569-572 validation failure. It is not a validated live strategy.
"""

from __future__ import annotations

from ma60_only_experiment import (
    build_standalone_signals,
    calculate_ma60_only_signal,
)
from ma60_period_gate_experiment import WINDOWS, filter_entry_windows

MA_PERIOD = 60
SLOPE_SESSIONS = 10
INITIAL_STOP_PCT = 8.0
TRIGGER_R = 3.0
TRAILING_PCT = 24.0
MAX_HOLD_SESSIONS = None
EXIT_RULE = "armed_trailing_stop"
EXIT_PARAMS = {
    "trigger_r": TRIGGER_R,
    "trailing_pct": TRAILING_PCT,
    "holding_windows": WINDOWS,
}
STATUS = "USER_DIRECTED_EXPERIMENTAL_OVERRIDE_VALIDATION_FAILED"


def calculate_current_buy_signal(
    stock_bars: list[dict], spy_bars: list[dict], as_of_date: str,
) -> dict | None:
    """Calculate the current MA60/10-session condition causally."""
    return calculate_ma60_only_signal(
        stock_bars, spy_bars, as_of_date,
        ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS,
    )


def build_current_buy_signals(
    prices: dict[str, list[dict]],
    membership: dict[str, list[tuple[str, str]]],
    sectors: dict[str, str], start: str, end: str,
) -> tuple[list[dict], dict[str, int]]:
    """Build false-to-true orders and apply the supplied fill-date calendar."""
    signals, counts = build_standalone_signals(
        prices, membership, sectors, start, end,
        ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS,
    )
    gated = filter_entry_windows(signals)
    output_counts = dict(counts)
    output_counts["calendar_excluded_signals"] = len(signals) - len(gated)
    output_counts["emitted_after_calendar"] = len(gated)
    return gated, dict(sorted(output_counts.items()))


def in_qqq_risk_on_session(date: str) -> bool:
    """QQQ is risk-on after the start open but exits at the finite end open."""
    return any(start <= date and (end is None or date < end)
               for start, end in WINDOWS)


def build_qqq_synchronized_buy_signals(
    prices: dict[str, list[dict]],
    membership: dict[str, list[tuple[str, str]]],
    sectors: dict[str, str], start: str, end: str,
) -> tuple[list[dict], dict[str, int]]:
    """Build current signals using QQQ's actual next-open IN/OUT state."""
    signals, counts = build_standalone_signals(
        prices, membership, sectors, start, end,
        ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS,
    )
    gated = [dict(row) for row in signals
             if in_qqq_risk_on_session(row["fill_date"])]
    output_counts = dict(counts)
    output_counts["calendar_excluded_signals"] = len(signals) - len(gated)
    output_counts["emitted_after_calendar"] = len(gated)
    return gated, dict(sorted(output_counts.items()))


def current_candidate_spec() -> dict:
    """Return a machine-readable snapshot without exposing mutable constants."""
    return {
        "status": STATUS,
        "ma_period": MA_PERIOD,
        "slope_sessions": SLOPE_SESSIONS,
        "entry_transition": "false_to_true",
        "calendar_windows": [list(window) for window in WINDOWS],
        "initial_stop_pct": INITIAL_STOP_PCT,
        "trigger_r": TRIGGER_R,
        "trailing_pct": TRAILING_PCT,
        "timeout_sessions": MAX_HOLD_SESSIONS,
        "exit_rule": EXIT_RULE,
        "exit_params": {
            "trigger_r": TRIGGER_R,
            "trailing_pct": TRAILING_PCT,
            "holding_windows": [list(window) for window in WINDOWS],
        },
        "force_exit_outside_calendar": True,
        "period_exit_timing": "first_ticker_open_outside_all_windows",
    }
