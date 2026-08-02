#!/usr/bin/env python3
"""Daily-marked VCP portfolio simulation with conservative execution.

The strategy specification is intentionally frozen: a breakout must be followed
by an MA20 touch-and-hold within 15 sessions, then the order fills at the next
session's open.  Edge Rank v2 is computed from same-date detection features and
only affects capped position size.  The simulator enforces cash, concurrent-name,
sector and trailing-ADV constraints and charges costs on both sides.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_client import CSVClient  # noqa: E402
from edge_rank import DEFAULT_W_EXT, DEFAULT_W_RS, SIZING_MIN_EDGE, compute_edge_rank  # noqa: E402

LIVE_MA_PERIOD = 20
LIVE_WINDOW = 15
REBREAK_WINDOW = 60
POCKET_PIVOT_WINDOW = 10
POCKET_PIVOT_VOLUME_LOOKBACK = 10
FIB_RETRACEMENT = 0.382
FIB_WAIT_WINDOW = 10
FIB_LEG_LOOKBACK = 10
PIVOT_RETEST_WINDOW = 15
BREAKOUT_WINDOW = 60
DOWN_CLOSE_WINDOW = 10
PIVOT_UNDERCUT_WINDOW = 15
PIVOT_RECLAIM_WINDOW = 5
INSIDE_DAY_WINDOW = 10
STOP_REENTRY_WINDOW = 20
CLOSING_LOW_LOOKBACK = 5


def _normalise_holding_windows(
    value: object,
) -> tuple[tuple[str, str | None], ...] | None:
    """Validate optional inclusive ISO-date windows used for forced exits."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("holding_windows must be a non-empty list or tuple")
    windows: list[tuple[str, str | None]] = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("each holding window must contain start and end")
        start, end = item
        if not isinstance(start, str) or (end is not None and not isinstance(end, str)):
            raise ValueError("holding-window dates must be ISO strings or a None end")
        try:
            datetime.strptime(start, "%Y-%m-%d")
            if end is not None:
                datetime.strptime(end, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("holding-window dates must use YYYY-MM-DD") from exc
        if end is not None and end < start:
            raise ValueError("holding-window end cannot precede its start")
        windows.append((start, end))
    return tuple(windows)


def _in_holding_window(
    date: str, windows: tuple[tuple[str, str | None], ...],
) -> bool:
    """Return whether ``date`` lies in any inclusive holding window."""
    return any(start <= date and (end is None or date <= end)
               for start, end in windows)


def _plan_frozen_pullback(bars: list[dict], breakout_idx: int, stop: float) -> int | None:
    """MA20 touch-and-hold within 15 bars; matches pullback_experiment's rule."""
    for i in range(breakout_idx + 1, min(breakout_idx + 1 + LIVE_WINDOW, len(bars))):
        if bars[i]["close"] < stop:
            return None
        if i + 1 < LIVE_MA_PERIOD:
            continue
        ma = statistics.fmean(b["close"] for b in bars[i - LIVE_MA_PERIOD + 1:i + 1])
        if bars[i].get("low", bars[i]["close"]) <= ma <= bars[i]["close"]:
            return i
    return None


def _plan_rebreak_after_pullback(
    bars: list[dict], breakout_idx: int, stop: float, rebreak_window: int = REBREAK_WINDOW,
) -> int | None:
    """Close above the breakout-to-pullback high after a valid MA20 retest.

    The reference high is frozen on the pullback bar.  A close below the
    pattern stop invalidates the setup while waiting, and the rebreak must
    occur within ``rebreak_window`` sessions after the pullback.
    """
    pullback_idx = _plan_frozen_pullback(bars, breakout_idx, stop)
    if pullback_idx is None:
        return None
    prior_high = max(b.get("high", b["close"]) for b in bars[breakout_idx:pullback_idx + 1])
    end = min(pullback_idx + 1 + rebreak_window, len(bars))
    for i in range(pullback_idx + 1, end):
        if bars[i]["close"] < stop:
            return None
        if bars[i]["close"] > prior_high:
            return i
    return None


def _find_causal_breakout(
    bars: list[dict], as_of_idx: int, pivot: float, stop: float,
    window: int = BREAKOUT_WINDOW,
) -> int | None:
    """First post-detection close above a frozen pivot, without outcome labels."""
    if as_of_idx < 0 or pivot <= 0 or stop <= 0 or window <= 0:
        return None
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return None
    end = min(as_of_idx + 1 + window, len(bars))
    for i in range(as_of_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close > pivot:
            return i
        if close < stop:
            return None
    return None


def _plan_consecutive_breakout_closes(
    bars: list[dict], as_of_idx: int, pivot: float, stop: float,
    required_closes: int = 2, window: int = BREAKOUT_WINDOW,
) -> int | None:
    """Require consecutive closes above a frozen pivot, then signal at close.

    The first qualifying close is found without outcome labels.  Every
    immediately following session must also close strictly above the pivot;
    one failure rejects the setup permanently rather than restarting a later
    sequence.  The returned index is the final confirming close, so callers
    can fill no earlier than the next session's open.
    """
    if required_closes < 1:
        raise ValueError("required_closes must be at least 1")
    breakout_idx = _find_causal_breakout(
        bars, as_of_idx, pivot, stop, window=window,
    )
    if breakout_idx is None:
        return None
    signal_idx = breakout_idx + required_closes - 1
    if signal_idx >= len(bars):
        return None
    for i in range(breakout_idx + 1, signal_idx + 1):
        close = float(bars[i].get("close") or 0)
        if close < stop or close <= pivot:
            return None
    return signal_idx


def _plan_first_down_close(
    bars: list[dict], breakout_idx: int, stop: float,
    window: int = DOWN_CLOSE_WINDOW, pivot: float | None = None,
) -> int | None:
    """Signal on first post-breakout down-close, optionally only above pivot."""
    if breakout_idx < 0 or stop <= 0 or window <= 0:
        return None
    end = min(breakout_idx + 1 + window, len(bars))
    for i in range(breakout_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        prior_close = float(bars[i - 1].get("close") or 0)
        if close < prior_close:
            return i if pivot is None or close > pivot else None
    return None


def _plan_pivot_reclaim(
    bars: list[dict], breakout_idx: int, pivot: float, stop: float,
    undercut_window: int = PIVOT_UNDERCUT_WINDOW,
    reclaim_window: int = PIVOT_RECLAIM_WINDOW,
) -> int | None:
    """Signal on a close back above pivot after a post-breakout undercut."""
    if (breakout_idx < 0 or pivot <= 0 or stop <= 0
            or undercut_window <= 0 or reclaim_window <= 0):
        return None
    undercut_end = min(breakout_idx + 1 + undercut_window, len(bars))
    for i in range(breakout_idx + 1, undercut_end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        if close <= pivot:
            reclaim_end = min(i + 1 + reclaim_window, len(bars))
            for j in range(i + 1, reclaim_end):
                reclaim_close = float(bars[j].get("close") or 0)
                if reclaim_close < stop:
                    return None
                if reclaim_close > pivot:
                    return j
            return None
    return None


def _plan_post_breakout_inside_day(
    bars: list[dict], breakout_idx: int, pivot: float, stop: float,
    window: int = INSIDE_DAY_WINDOW,
) -> int | None:
    """Signal on first strict post-breakout inside day if it holds pivot."""
    if breakout_idx < 0 or pivot <= 0 or stop <= 0 or window <= 0:
        return None
    end = min(breakout_idx + 1 + window, len(bars))
    for i in range(breakout_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        high = float(bars[i].get("high", close) or 0)
        low = float(bars[i].get("low", close) or 0)
        prior_close = float(bars[i - 1].get("close") or 0)
        prior_high = float(bars[i - 1].get("high", prior_close) or 0)
        prior_low = float(bars[i - 1].get("low", prior_close) or 0)
        if high < prior_high and low > prior_low:
            return i if close > pivot else None
    return None


def _plan_stopout_pivot_reentry(
    bars: list[dict], stopout_idx: int, pivot: float,
    window: int = STOP_REENTRY_WINDOW,
) -> int | None:
    """First close above frozen pivot from the stopout session onward."""
    if stopout_idx < 0 or pivot <= 0 or window <= 0:
        return None
    end = min(stopout_idx + window, len(bars))
    for i in range(stopout_idx, end):
        if float(bars[i].get("close") or 0) > pivot:
            return i if i + 1 < len(bars) else None
    return None


def _plan_closing_low_pullback(
    bars: list[dict], as_of_idx: int, stop: float,
    lookback: int = CLOSING_LOW_LOOKBACK, window: int = BREAKOUT_WINDOW,
) -> int | None:
    """First post-detection close below every close in the prior lookback."""
    if as_of_idx < 0 or stop <= 0 or lookback <= 0 or window <= 0:
        return None
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return None
    end = min(as_of_idx + 1 + window, len(bars))
    for i in range(as_of_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        if i >= lookback and close < min(
            float(bar.get("close") or 0) for bar in bars[i - lookback:i]
        ):
            return i
    return None


def _plan_closing_low_lifecycle(
    bars: list[dict], as_of_idx: int, stop: float,
    lookback: int = 5, window: int = BREAKOUT_WINDOW,
    cooldown: int = 5, max_attempts: int = 3,
) -> list[int]:
    """Emit spaced closing-low signals while one frozen setup remains valid."""
    if (as_of_idx < 0 or stop <= 0 or lookback <= 0 or window <= 0
            or cooldown <= 0 or max_attempts <= 0):
        return []
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return []
    planned = []
    end = min(as_of_idx + 1 + window, len(bars))
    for i in range(as_of_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            break
        if i < lookback or close >= min(
            float(row.get("close") or 0) for row in bars[i - lookback:i]
        ):
            continue
        if planned and i - planned[-1] < cooldown:
            continue
        planned.append(i)
        if len(planned) >= max_attempts:
            break
    return planned


def _plan_closing_low_reversal(
    bars: list[dict], as_of_idx: int, stop: float,
    lookback: int = CLOSING_LOW_LOOKBACK, window: int = BREAKOUT_WINDOW,
    confirm_window: int = 3,
) -> int | None:
    """Confirm a five-day closing low with a later close above its high."""
    if confirm_window <= 0:
        return None
    low_idx = _plan_closing_low_pullback(
        bars, as_of_idx, stop, lookback=lookback, window=window,
    )
    if low_idx is None:
        return None
    reference_high = float(bars[low_idx].get("high", bars[low_idx]["close"]) or 0)
    end = min(low_idx + 1 + confirm_window, len(bars))
    for i in range(low_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        if close > reference_high:
            return i
    return None


def _plan_controlled_pullback_recovery(
    bars: list[dict], as_of_idx: int, pivot: float, stop: float,
    lookback: int = 3, max_depth_pct: float = 8.0,
    confirmation: str = "up_close", volume_expansion: bool = False,
    window: int = BREAKOUT_WINDOW,
) -> int | None:
    """Signal on the session immediately after a controlled closing-low pullback."""
    if (as_of_idx < 0 or pivot <= 0 or stop <= 0 or lookback <= 0
            or not 0 < max_depth_pct < 100 or window <= 1):
        return None
    if confirmation not in ("up_close", "prior_high"):
        raise ValueError(f"unknown recovery confirmation: {confirmation}")
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return None
    end = min(as_of_idx + 1 + window, len(bars))
    for low_idx in range(as_of_idx + 1, end - 1):
        pullback_close = float(bars[low_idx].get("close") or 0)
        if pullback_close < stop:
            return None
        if low_idx < lookback or pullback_close >= min(
            float(bar.get("close") or 0)
            for bar in bars[low_idx - lookback:low_idx]
        ):
            continue
        if not pivot * (1 - max_depth_pct / 100) <= pullback_close <= pivot:
            continue
        recovery_idx = low_idx + 1
        recovery_close = float(bars[recovery_idx].get("close") or 0)
        if recovery_close < stop:
            return None
        threshold = (
            pullback_close if confirmation == "up_close"
            else float(bars[low_idx].get("high", pullback_close) or 0)
        )
        if recovery_close <= threshold:
            continue
        if (volume_expansion
                and float(bars[recovery_idx].get("volume") or 0)
                <= float(bars[low_idx].get("volume") or 0)):
            continue
        return recovery_idx
    return None


def _plan_pivot_open_limit(
    bars: list[dict], as_of_idx: int, pivot: float, stop: float,
    window: int = BREAKOUT_WINDOW,
) -> int | None:
    """Return prior-close index for first valid opening print at/below pivot."""
    if as_of_idx < 0 or pivot <= 0 or stop <= 0 or window <= 0:
        return None
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return None
    end = min(as_of_idx + 1 + window, len(bars))
    for fill_idx in range(as_of_idx + 1, end):
        if float(bars[fill_idx - 1].get("close") or 0) < stop:
            return None
        opening = float(bars[fill_idx].get("open") or 0)
        if opening <= stop:
            return None
        if opening <= pivot:
            return fill_idx - 1
    return None


def _plan_contraction_limit(
    bars: list[dict], as_of_idx: int, pivot: float, stop: float,
    retracement: float = .25, window: int = BREAKOUT_WINDOW,
) -> tuple[int, float] | None:
    """Return prior-close index and raw fill for a frozen standing buy limit."""
    if (as_of_idx < 0 or pivot <= stop or stop <= 0
            or not 0 < retracement < 1 or window <= 0):
        return None
    if float(bars[as_of_idx].get("close") or 0) < stop:
        return None
    limit = pivot - retracement * (pivot - stop)
    end = min(as_of_idx + 1 + window, len(bars))
    for fill_idx in range(as_of_idx + 1, end):
        if float(bars[fill_idx - 1].get("close") or 0) < stop:
            return None
        opening = float(bars[fill_idx].get("open") or 0)
        if opening <= stop:
            return None
        low = float(bars[fill_idx].get("low") or opening)
        if low <= limit:
            return fill_idx - 1, min(opening, limit)
    return None


def _plan_pivot_retest(
    bars: list[dict], breakout_idx: int, pivot: float, stop: float,
    window: int = PIVOT_RETEST_WINDOW, mode: str = "baseline",
    clv_threshold: float = 0.60, confirm_window: int = 3,
) -> int | None:
    """First post-breakout bar that touches and closes above the frozen pivot."""
    if breakout_idx < 0 or pivot <= 0 or stop <= 0 or window <= 0:
        return None
    end = min(breakout_idx + 1 + window, len(bars))
    for i in range(breakout_idx + 1, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        low = float(bars[i].get("low", close) or 0)
        if low <= pivot <= close:
            if mode == "bullish_retest" and (
                i == 0 or close <= float(bars[i - 1].get("close") or 0)
            ):
                return None
            if mode == "strong_close_clv60":
                high = float(bars[i].get("high", close) or close)
                span = high - low
                clv = (close - low) / span if span > 0 else 1.0
                if clv < clv_threshold:
                    return None
            if mode == "retest_high_confirm3":
                if confirm_window <= 0:
                    return None
                retest_high = float(bars[i].get("high", close) or close)
                confirm_end = min(i + 1 + confirm_window, len(bars))
                for j in range(i + 1, confirm_end):
                    confirm_close = float(bars[j].get("close") or 0)
                    if confirm_close < stop:
                        return None
                    if confirm_close > retest_high:
                        return j
                return None
            if mode not in (
                "baseline", "breakout_no_gap_1pct", "bullish_retest",
                "strong_close_clv60", "retest_high_confirm3",
            ):
                raise ValueError(f"unknown pivot retest mode: {mode}")
            return i
    return None


def _sma(bars: list[dict], index: int, period: int) -> float | None:
    """Return the close SMA ending at ``index``, or ``None`` during warm-up."""
    start = index - period + 1
    if start < 0:
        return None
    return statistics.fmean(float(bar["close"]) for bar in bars[start:index + 1])


def _plan_pocket_pivot(
    bars: list[dict], as_of_idx: int, stop: float, pivot: float,
    window: int = POCKET_PIVOT_WINDOW,
    volume_lookback: int = POCKET_PIVOT_VOLUME_LOOKBACK,
    max_ma_extension_pct: float = 3.0,
    max_pivot_extension_pct: float = 3.0,
) -> int | None:
    """Find the first frozen Pocket Pivot signal at or after VCP detection.

    The scan contains ``window`` sessions including the as-of bar.  Each
    candidate uses only data available at that close: it must be an up day,
    exceed every down-day volume in the preceding ten sessions, have bullish
    SMA10/SMA50/SMA200 alignment, and close from SMA10 through the smaller of
    3% above SMA10 or 3% above the as-of VCP pivot.  A close below the frozen
    last-contraction low invalidates the setup immediately.
    """
    if (window <= 0 or volume_lookback <= 0 or as_of_idx < 0
            or stop <= 0 or pivot <= 0 or max_ma_extension_pct < 0
            or max_pivot_extension_pct < 0):
        return None
    end = min(as_of_idx + window, len(bars))
    for i in range(as_of_idx, end):
        close = float(bars[i].get("close") or 0)
        if close < stop:
            return None
        if i < 1 or close <= float(bars[i - 1].get("close") or 0):
            continue

        down_volumes = [
            float(bars[j].get("volume") or 0)
            for j in range(max(1, i - volume_lookback), i)
            if float(bars[j].get("close") or 0) < float(bars[j - 1].get("close") or 0)
        ]
        if not down_volumes or float(bars[i].get("volume") or 0) <= max(down_volumes):
            continue

        sma10, sma50, sma200 = (_sma(bars, i, period) for period in (10, 50, 200))
        if sma10 is None or sma50 is None or sma200 is None:
            continue
        if not (sma10 > sma50 > sma200):
            continue
        if (close < sma10
                or close > sma10 * (1 + max_ma_extension_pct / 100)
                or close > pivot * (1 + max_pivot_extension_pct / 100)):
            continue
        return i
    return None


def _plan_pocket_pivot_fib(
    bars: list[dict], as_of_idx: int, stop: float, pivot: float,
    retracement: float = FIB_RETRACEMENT,
    wait_window: int = FIB_WAIT_WINDOW,
    leg_lookback: int = FIB_LEG_LOOKBACK,
) -> int | None:
    """Wait for a Fibonacci retracement after a frozen Pocket Pivot signal.

    The retracement leg runs from the lowest low of the ``leg_lookback``
    sessions ending at the signal bar up to the signal bar's high.  The first
    bar within ``wait_window`` sessions whose low touches the retracement
    level and whose close holds at or above it becomes the entry signal.  A
    close below the frozen pattern stop invalidates while waiting; no touch
    means no trade.
    """
    if not 0 < retracement < 1 or wait_window <= 0 or leg_lookback <= 0:
        return None
    signal_idx = _plan_pocket_pivot(bars, as_of_idx, stop, pivot)
    if signal_idx is None:
        return None
    leg_start = max(0, signal_idx - leg_lookback + 1)
    leg_low = min(
        float(b.get("low", b["close"])) for b in bars[leg_start:signal_idx + 1]
    )
    leg_high = float(bars[signal_idx].get("high", bars[signal_idx]["close"]))
    if leg_high <= leg_low:
        return None
    level = leg_high - retracement * (leg_high - leg_low)
    end = min(signal_idx + 1 + wait_window, len(bars))
    for i in range(signal_idx + 1, end):
        close = float(bars[i]["close"])
        if close < stop:
            return None
        if float(bars[i].get("low", close)) <= level <= close:
            return i
    return None


def _as_of_pattern_levels(detection: dict) -> tuple[float, float] | None:
    """Read the frozen pivot and stop from causal VCP detection fields."""
    pattern = detection.get("vcp_pattern") or {}
    contractions = pattern.get("contractions") or []
    if not contractions:
        return None
    try:
        pivot = float(pattern.get("pivot_price") or 0)
        stop = float(contractions[-1].get("low_price") or 0)
    except (TypeError, ValueError):
        return None
    return (pivot, stop) if pivot > 0 and stop > 0 else None


@dataclass(frozen=True)
class Config:
    initial_cash: float = 100_000.0
    max_positions: int = 10
    max_position_pct: float = 10.0
    max_sector_pct: float = 30.0
    adv_participation_pct: float = 1.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_risk_pct: float = 8.0
    max_hold_bars: int = 60
    min_edge: float = SIZING_MIN_EDGE
    edge_cap: float = 82.5


def _candidate_signals(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
    entry_rule: str = "pullback", entry_params: dict | None = None,
) -> list[dict]:
    """Build next-bar-open orders for a frozen entry-rule definition."""
    edges = compute_edge_rank(detections, DEFAULT_W_RS, DEFAULT_W_EXT)
    signals = []
    for sym, dets in detections.items():
        bars = prices.get(sym) or []
        idx = {b["date"]: i for i, b in enumerate(bars)}
        for det in dets:
            edge = (edges.get((sym, det.get("as_of_date"))) or {}).get("edge_rank")
            if edge is None or edge < cfg.min_edge:
                continue
            raw_entry_price = None

            if entry_rule in (
                "pocket_pivot", "pocket_pivot_fib", "pivot_retest",
                "detection_entry", "two_close_breakout", "first_down_close",
                "down_close_pivot_hold", "pivot_reclaim",
                "inside_day_breakout",
                "down_close_stop_reentry",
                "five_day_low_pullback",
                "five_day_low_reversal",
                "pivot_open_limit",
                "controlled_pullback_recovery",
                "closing_low_lifecycle",
                "contraction_limit",
            ):
                levels = _as_of_pattern_levels(det)
                as_of_idx = idx.get(det.get("as_of_date"))
                if levels is None or as_of_idx is None:
                    continue
                pivot, pattern_stop = levels
                if float(bars[as_of_idx].get("close") or 0) < pattern_stop:
                    continue
                if entry_rule == "detection_entry":
                    delay = int((entry_params or {}).get("delay", 0))
                    signal_idx = as_of_idx + delay if delay >= 0 else None
                    if signal_idx is not None and signal_idx >= len(bars):
                        signal_idx = None
                elif entry_rule == "five_day_low_pullback":
                    signal_idx = _plan_closing_low_pullback(
                        bars, as_of_idx, pattern_stop, **(entry_params or {}),
                    )
                elif entry_rule == "closing_low_lifecycle":
                    planned = _plan_closing_low_lifecycle(
                        bars, as_of_idx, pattern_stop, **(entry_params or {}),
                    )
                    for attempt, planned_idx in enumerate(planned, 1):
                        if planned_idx + 1 >= len(bars):
                            continue
                        signals.append({
                            "symbol": sym, "sector": det.get("sector") or "Unknown",
                            "signal_date": bars[planned_idx]["date"],
                            "fill_date": bars[planned_idx + 1]["date"],
                            "fill_idx": planned_idx + 1, "edge_rank": edge,
                            "pattern_stop": pattern_stop, "pivot": pivot,
                            "attempt": attempt,
                        })
                    continue
                elif entry_rule == "five_day_low_reversal":
                    signal_idx = _plan_closing_low_reversal(
                        bars, as_of_idx, pattern_stop, **(entry_params or {}),
                    )
                elif entry_rule == "pivot_open_limit":
                    signal_idx = _plan_pivot_open_limit(
                        bars, as_of_idx, pivot, pattern_stop,
                        **(entry_params or {}),
                    )
                elif entry_rule == "contraction_limit":
                    planned_limit = _plan_contraction_limit(
                        bars, as_of_idx, pivot, pattern_stop,
                        **(entry_params or {}),
                    )
                    if planned_limit is None:
                        signal_idx = None
                    else:
                        signal_idx, raw_entry_price = planned_limit
                elif entry_rule == "controlled_pullback_recovery":
                    signal_idx = _plan_controlled_pullback_recovery(
                        bars, as_of_idx, pivot, pattern_stop,
                        **(entry_params or {}),
                    )
                elif entry_rule == "two_close_breakout":
                    breakout_params = dict(entry_params or {})
                    signal_idx = _plan_consecutive_breakout_closes(
                        bars, as_of_idx, pivot, pattern_stop, **breakout_params,
                    )
                elif entry_rule in (
                    "first_down_close", "down_close_pivot_hold",
                    "down_close_stop_reentry",
                ):
                    breakout_idx = _find_causal_breakout(
                        bars, as_of_idx, pivot, pattern_stop,
                    )
                    planner_params = dict(entry_params or {})
                    planner_params.pop("reentry_window", None)
                    signal_idx = (
                        _plan_first_down_close(
                            bars, breakout_idx, pattern_stop,
                            pivot=(pivot if entry_rule != "first_down_close" else None),
                            **planner_params,
                        )
                        if breakout_idx is not None else None
                    )
                elif entry_rule == "pivot_reclaim":
                    breakout_idx = _find_causal_breakout(
                        bars, as_of_idx, pivot, pattern_stop,
                    )
                    signal_idx = (
                        _plan_pivot_reclaim(
                            bars, breakout_idx, pivot, pattern_stop,
                            **(entry_params or {}),
                        )
                        if breakout_idx is not None else None
                    )
                elif entry_rule == "inside_day_breakout":
                    breakout_idx = _find_causal_breakout(
                        bars, as_of_idx, pivot, pattern_stop,
                    )
                    signal_idx = (
                        _plan_post_breakout_inside_day(
                            bars, breakout_idx, pivot, pattern_stop,
                            **(entry_params or {}),
                        )
                        if breakout_idx is not None else None
                    )
                elif entry_rule == "pivot_retest":
                    breakout_idx = _find_causal_breakout(
                        bars, as_of_idx, pivot, pattern_stop,
                    )
                    pivot_params = dict(entry_params or {})
                    mode = pivot_params.get("mode", "baseline")
                    if mode == "breakout_no_gap_1pct" and breakout_idx is not None:
                        if breakout_idx == 0:
                            breakout_idx = None
                        else:
                            prior_close = float(bars[breakout_idx - 1].get("close") or 0)
                            breakout_open = float(bars[breakout_idx].get("open") or 0)
                            if prior_close <= 0 or breakout_open / prior_close - 1 >= .01:
                                breakout_idx = None
                    signal_idx = (
                        _plan_pivot_retest(
                            bars, breakout_idx, pivot, pattern_stop,
                            **pivot_params,
                        )
                        if breakout_idx is not None else None
                    )
                else:
                    planner = (
                        _plan_pocket_pivot if entry_rule == "pocket_pivot"
                        else _plan_pocket_pivot_fib
                    )
                    signal_idx = planner(
                        bars, as_of_idx, pattern_stop, pivot, **(entry_params or {}),
                    )
            else:
                fo = det.get("forward_outcome") or {}
                if fo.get("outcome_type") != "breakout":
                    continue
                bo = idx.get(fo.get("exit_date"))
                if bo is None or bo + 1 >= len(bars):
                    continue
                pivot = fo.get("pivot_price")
                pattern_stop = fo.get("stop_price") or 0.0
                if not pivot:
                    continue
                if entry_rule == "pullback":
                    signal_idx = _plan_frozen_pullback(bars, bo, pattern_stop)
                elif entry_rule == "rebreak":
                    signal_idx = _plan_rebreak_after_pullback(bars, bo, pattern_stop)
                else:
                    raise ValueError(f"unknown entry rule: {entry_rule}")
            if signal_idx is None or signal_idx + 1 >= len(bars):
                continue
            fill_idx = signal_idx + 1
            signal = {
                "symbol": sym, "sector": det.get("sector") or "Unknown",
                "signal_date": bars[signal_idx]["date"],
                "fill_date": bars[fill_idx]["date"], "fill_idx": fill_idx,
                "edge_rank": edge, "pattern_stop": pattern_stop, "pivot": pivot,
                "attempt": 1,
            }
            if raw_entry_price is not None:
                signal["raw_entry_price"] = raw_entry_price
            signals.append(signal)
    return sorted(signals, key=lambda x: (x["fill_date"], -x["edge_rank"], x["symbol"]))


def _adv_dollars(bars: list[dict], i: int, lookback: int = 20) -> float:
    prior = bars[max(0, i - lookback):i]
    if not prior:
        return 0.0
    return statistics.fmean(b["close"] * b.get("volume", 0) for b in prior)


def run_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config = Config(),
    entry_rule: str = "pullback", entry_params: dict | None = None,
    exit_rule: str = "baseline", exit_params: dict | None = None,
    simulation_start_date: str | None = None,
) -> dict:
    """Run the portfolio. ``prices`` bars must be oldest-first."""
    if exit_rule not in (
        "baseline", "breakeven_r", "pivot_failure", "distribution_cluster",
        "loss_distribution_cluster",
        "followthrough_sma",
        "model_decay",
        "fixed_time",
        "diagnostic_oracle",
        "trailing_stop",
        "armed_trailing_stop",
    ):
        raise ValueError(f"unknown exit rule: {exit_rule}")
    trailing_pct = None
    if exit_rule == "trailing_stop":
        trailing_pct = float((exit_params or {}).get("trailing_pct", 8.0))
        if not 0 < trailing_pct < 100:
            raise ValueError("trailing stop percentage must be between 0 and 100")
    armed_trigger_r = None
    armed_trailing_pct = None
    if exit_rule == "armed_trailing_stop":
        armed_trigger_r = float((exit_params or {}).get("trigger_r", 3.0))
        armed_trailing_pct = float((exit_params or {}).get("trailing_pct", 24.0))
        if armed_trigger_r <= 0:
            raise ValueError("armed trailing trigger R must be positive")
        if not 0 < armed_trailing_pct < 100:
            raise ValueError("armed trailing percentage must be between 0 and 100")
    holding_windows = _normalise_holding_windows(
        (exit_params or {}).get("holding_windows"))
    holding_window_exit_timing = str(
        (exit_params or {}).get(
            "holding_window_exit_timing", "first_outside_open"))
    if holding_window_exit_timing not in (
        "first_outside_open", "window_end_open",
    ):
        raise ValueError(
            "holding_window_exit_timing must be first_outside_open or window_end_open")
    signals = _candidate_signals(
        detections, prices, cfg, entry_rule=entry_rule, entry_params=entry_params,
    )
    by_date = collections.defaultdict(list)
    for s in signals:
        by_date[s["fill_date"]].append(s)
    if not signals:
        return {"config": cfg.__dict__, "summary": {"signals": 0, "trades": 0,
                "end_value": cfg.initial_cash, "total_return_pct": 0.0,
                "cagr_pct": 0.0, "max_drawdown_pct": 0.0, "rejected": {}},
                "trades": [], "equity_curve": []}
    first_signal_date = simulation_start_date or min(s["fill_date"] for s in signals)
    dates = sorted({b["date"] for bars in prices.values() for b in bars
                    if b["date"] >= first_signal_date})
    index = {s: {b["date"]: i for i, b in enumerate(bars)} for s, bars in prices.items()}
    cash = cfg.initial_cash
    positions: dict[str, dict] = {}
    trades, equity_curve, rejected = [], [], collections.Counter()
    last_close: dict[str, float] = {}
    previous_equity = cfg.initial_cash
    previous_spy = None
    previous_gross_exposure = 0.0
    generated_reentries = 0
    one_way_cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000

    for date in dates:
        for sym, bars in prices.items():
            i = index[sym].get(date)
            if i is not None:
                last_close[sym] = bars[i]["close"]
        # Stops are conservatively filled at min(open, stop) when the day's low breaches.
        for sym, pos in list(positions.items()):
            i = index[sym].get(date)
            if i is None or i <= pos["entry_idx"]:
                continue
            bar = prices[sym][i]
            reason = None
            raw_exit = None
            # The finite endpoint is inclusive. On the first subsequent
            # ticker session outside every allowed window, liquidate at its
            # open before evaluating that session's intraday stop.
            at_finite_window_end = bool(
                holding_windows is not None
                and holding_window_exit_timing == "window_end_open"
                and any(end == date for _, end in holding_windows if end is not None)
            )
            if (holding_windows is not None
                    and (not _in_holding_window(date, holding_windows)
                         or at_finite_window_end)):
                reason, raw_exit = "period_exit", bar["open"]
            elif (exit_rule == "diagnostic_oracle"
                    and i == pos.get("diagnostic_exit_idx")):
                reason, raw_exit = "diagnostic_oracle", bar["open"]
            elif (exit_rule == "model_decay"
                    and i == pos.get("model_exit_idx")):
                reason, raw_exit = "model_decay", bar["open"]
            elif (exit_rule == "fixed_time"
                    and i == pos.get("model_exit_idx")):
                reason, raw_exit = "fixed_time", bar["open"]
            elif pos.get("distribution_exit_signal_date"):
                reason = pos.get("distribution_exit_reason", "distribution_cluster")
                raw_exit = bar["open"]
            elif pos.get("pivot_failure_signal_date"):
                reason, raw_exit = "pivot_failure", bar["open"]
            elif pos.get("managed_exit_signal_date"):
                reason = pos.get("managed_exit_reason", "followthrough_sma")
                raw_exit = bar["open"]
            elif bar["low"] <= pos["stop"]:
                reason = (
                    "trailing_stop" if exit_rule == "trailing_stop"
                    else "armed_trailing_stop"
                    if (exit_rule == "armed_trailing_stop"
                        and pos.get("trailing_armed_date"))
                    else "breakeven_stop" if pos.get("breakeven_armed_date")
                    else "stop"
                )
                raw_exit = min(bar["open"], pos["stop"])
            elif (exit_rule not in ("trailing_stop", "armed_trailing_stop")
                  and i - pos["entry_idx"] >= cfg.max_hold_bars):
                # The timeout is known only after the prior bar completes;
                # execute conservatively at this session's open.
                reason, raw_exit = "timeout", bar["open"]
            if reason:
                exit_price = raw_exit * (1 - one_way_cost)
                proceeds = pos["shares"] * exit_price
                cash += proceeds
                trades.append({**pos, "exit_date": date, "exit_price": round(exit_price, 4),
                               "exit_reason": reason,
                               "net_return_pct": round((exit_price / pos["entry_price"] - 1) * 100, 2)})
                del positions[sym]
                if (reason == "stop" and entry_rule == "down_close_stop_reentry"
                        and int(pos.get("attempt", 1)) == 1):
                    signal_idx = _plan_stopout_pivot_reentry(
                        prices[sym], i, float(pos.get("pivot") or 0),
                        window=int((entry_params or {}).get("reentry_window", STOP_REENTRY_WINDOW)),
                    )
                    if signal_idx is not None:
                        fill_idx = signal_idx + 1
                        by_date[prices[sym][fill_idx]["date"]].append({
                            "symbol": sym, "sector": pos["sector"],
                            "signal_date": prices[sym][signal_idx]["date"],
                            "fill_date": prices[sym][fill_idx]["date"],
                            "fill_idx": fill_idx, "edge_rank": pos["edge_rank"],
                            "pattern_stop": pos["pattern_stop"],
                            "pivot": pos.get("pivot"), "attempt": 2,
                        })
                        generated_reentries += 1

        # A close-confirmed ratchet becomes active only after today's stop
        # evaluation, so it cannot use the same bar's low retroactively.
        if exit_rule == "trailing_stop":
            assert trailing_pct is not None
            for sym, pos in positions.items():
                i = index[sym].get(date)
                if i is None or i <= pos["entry_idx"]:
                    continue
                close = float(prices[sym][i].get("close") or 0)
                prior_high = float(pos.get("highest_close") or pos["entry_price"])
                highest_close = max(prior_high, close)
                pos["highest_close"] = highest_close
                pos["stop"] = max(
                    float(pos["stop"]),
                    highest_close * (1 - trailing_pct / 100),
                )
        elif exit_rule == "armed_trailing_stop":
            assert armed_trigger_r is not None and armed_trailing_pct is not None
            for sym, pos in positions.items():
                i = index[sym].get(date)
                if i is None or i <= pos["entry_idx"]:
                    continue
                close = float(prices[sym][i].get("close") or 0)
                prior_high = float(pos.get("highest_close") or pos["entry_price"])
                highest_close = max(prior_high, close)
                pos["highest_close"] = highest_close
                risk = float(pos["entry_price"]) - float(pos["initial_stop"])
                if (not pos.get("trailing_armed_date") and risk > 0
                        and close >= float(pos["entry_price"]) + armed_trigger_r * risk):
                    pos["trailing_armed_date"] = date
                if pos.get("trailing_armed_date"):
                    pos["stop"] = max(
                        float(pos["stop"]),
                        highest_close * (1 - armed_trailing_pct / 100),
                    )
        elif exit_rule == "breakeven_r":
            trigger_r = float((exit_params or {}).get("trigger_r", 1.0))
            if trigger_r <= 0:
                raise ValueError("breakeven trigger_r must be positive")
            for sym, pos in positions.items():
                if pos.get("breakeven_armed_date"):
                    continue
                i = index[sym].get(date)
                if i is None or i <= pos["entry_idx"]:
                    continue
                risk = pos["entry_price"] - pos["initial_stop"]
                if risk > 0 and prices[sym][i]["close"] >= pos["entry_price"] + trigger_r * risk:
                    pos["stop"] = pos["entry_price"]
                    pos["breakeven_armed_date"] = date
        elif exit_rule == "pivot_failure":
            for sym, pos in positions.items():
                if pos.get("pivot_failure_signal_date"):
                    continue
                i = index[sym].get(date)
                if i is None or i <= pos["entry_idx"]:
                    continue
                pivot = pos.get("pivot")
                if pivot and prices[sym][i]["close"] < pivot:
                    pos["pivot_failure_signal_date"] = date
        elif exit_rule in ("distribution_cluster", "loss_distribution_cluster"):
            event_count = int((exit_params or {}).get("event_count", 3))
            event_window = int((exit_params or {}).get("event_window", 15))
            if event_count <= 0 or event_window <= 0:
                raise ValueError("distribution count/window must be positive")
            for sym, pos in positions.items():
                if pos.get("distribution_exit_signal_date"):
                    continue
                i = index[sym].get(date)
                if i is None or i <= pos["entry_idx"]:
                    continue
                bars = prices[sym]
                if (float(bars[i].get("close") or 0) < float(bars[i - 1].get("close") or 0)
                        and float(bars[i].get("volume") or 0) > float(bars[i - 1].get("volume") or 0)):
                    pos.setdefault("distribution_event_indices", []).append(i)
                events = [
                    event for event in pos.get("distribution_event_indices", [])
                    if event >= i - event_window + 1
                ]
                pos["distribution_event_indices"] = events
                price_condition = (
                    exit_rule == "distribution_cluster"
                    or float(bars[i].get("close") or 0) < float(pos["entry_price"])
                )
                if len(events) >= event_count and price_condition:
                    pos["distribution_exit_signal_date"] = date
                    pos["distribution_exit_reason"] = exit_rule
        elif exit_rule == "followthrough_sma":
            early_days = int((exit_params or {}).get("early_days", 5))
            min_gain_pct = float((exit_params or {}).get("min_gain_pct", 2.0))
            arm_gain_pct = float((exit_params or {}).get("arm_gain_pct", 8.0))
            sma_period = int((exit_params or {}).get("sma_period", 10))
            if early_days <= 0 or min_gain_pct < 0 or arm_gain_pct <= 0 or sma_period <= 0:
                raise ValueError("invalid followthrough_sma parameters")
            for sym, pos in positions.items():
                if pos.get("managed_exit_signal_date"):
                    continue
                i = index[sym].get(date)
                if i is None or i < pos["entry_idx"]:
                    continue
                close = float(prices[sym][i].get("close") or 0)
                prior_high_close = float(pos.get("highest_close") or pos["entry_price"])
                pos["highest_close"] = max(prior_high_close, close)
                held_sessions = i - pos["entry_idx"] + 1
                armed_before_today = bool(pos.get("managed_exit_armed_date"))
                if (held_sessions == early_days
                        and pos["highest_close"] < pos["entry_price"] * (1 + min_gain_pct / 100)):
                    pos["managed_exit_signal_date"] = date
                    pos["managed_exit_reason"] = "no_followthrough"
                    continue
                if armed_before_today:
                    sma = _sma(prices[sym], i, sma_period)
                    if sma is not None and close < sma:
                        pos["managed_exit_signal_date"] = date
                        pos["managed_exit_reason"] = f"sma{sma_period}_break"
                elif close >= pos["entry_price"] * (1 + arm_gain_pct / 100):
                    pos["managed_exit_armed_date"] = date

        # Existing names cannot be doubled; strongest Edge Rank wins scarce capacity.
        for sig in sorted(
            by_date.get(date, []),
            key=lambda value: (-value["edge_rank"], value["symbol"]),
        ):
            sym = sig["symbol"]
            if sym in positions or len(positions) >= cfg.max_positions:
                rejected["duplicate_or_position_limit"] += 1
                continue
            i = index[sym].get(date)
            if i is None:
                rejected["missing_bar"] += 1
                continue
            bar = prices[sym][i]
            equity = cash + sum(
                p["shares"] * last_close.get(s, p["entry_price"])
                for s, p in positions.items()
            )
            sector_value = sum(p["shares"] * p["entry_price"] for p in positions.values()
                               if p["sector"] == sig["sector"])
            sector_room = max(0.0, equity * cfg.max_sector_pct / 100 - sector_value)
            edge_scale = min(sig["edge_rank"], cfg.edge_cap) / cfg.edge_cap
            target = equity * cfg.max_position_pct / 100 * edge_scale
            liquidity = _adv_dollars(prices[sym], i) * cfg.adv_participation_pct / 100
            budget = min(target, sector_room, liquidity, cash / (1 + one_way_cost))
            raw_entry = float(sig.get("raw_entry_price") or bar["open"])
            if raw_entry <= float(sig["pattern_stop"]):
                rejected["open_at_or_below_stop"] += 1
                continue
            fill_price = raw_entry * (1 + one_way_cost)
            shares = math.floor(budget / fill_price)
            if shares <= 0:
                rejected["cash_sector_or_liquidity"] += 1
                continue
            cost = shares * fill_price
            cash -= cost
            stop = max(sig["pattern_stop"], fill_price * (1 - cfg.max_risk_pct / 100))
            positions[sym] = {
                "symbol": sym, "sector": sig["sector"], "entry_date": date,
                "entry_idx": i, "entry_price": round(fill_price, 4), "shares": shares,
                "stop": round(stop, 4), "initial_stop": round(stop, 4),
                "pivot": sig.get("pivot"), "edge_rank": sig["edge_rank"],
                "pattern_stop": sig["pattern_stop"],
                "attempt": int(sig.get("attempt", 1)),
                "diagnostic_exit_idx": sig.get("diagnostic_exit_idx"),
                "model_exit_idx": sig.get("model_exit_idx"),
                "entry_day_stop": bool(sig.get("entry_day_stop")),
                "signal_date": sig["signal_date"], "entry_adv_dollars": round(_adv_dollars(prices[sym], i), 2),
                "highest_close": round(float(bar.get("close") or fill_price), 4),
            }
            if exit_rule == "armed_trailing_stop":
                assert armed_trigger_r is not None and armed_trailing_pct is not None
                pos = positions[sym]
                risk = float(pos["entry_price"]) - float(pos["initial_stop"])
                entry_close = float(bar.get("close") or fill_price)
                if (risk > 0 and entry_close
                        >= float(pos["entry_price"]) + armed_trigger_r * risk):
                    pos["trailing_armed_date"] = date
                    pos["stop"] = max(
                        float(pos["stop"]),
                        entry_close * (1 - armed_trailing_pct / 100),
                    )

        # Resting opening-limit entries can hit their hard stop later in the
        # entry session. Process this only after all opening orders so proceeds
        # from a later intraday stop cannot fund another same-open position.
        for sym, pos in list(positions.items()):
            i = index[sym].get(date)
            if (i is None or i != pos["entry_idx"]
                    or not pos.get("entry_day_stop")
                    or float(prices[sym][i].get("low") or 0) > pos["stop"]):
                continue
            exit_price = pos["stop"] * (1 - one_way_cost)
            cash += pos["shares"] * exit_price
            trades.append({**pos, "exit_date": date,
                           "exit_price": round(exit_price, 4),
                           "exit_reason": "entry_day_stop",
                           "net_return_pct": round(
                               (exit_price / pos["entry_price"] - 1) * 100, 2,
                           )})
            del positions[sym]

        marked = cash
        for sym, pos in positions.items():
            marked += pos["shares"] * last_close.get(sym, pos["entry_price"])
        portfolio_return = marked / previous_equity - 1 if previous_equity else 0.0
        spy_close = last_close.get("SPY")
        spy_return = (spy_close / previous_spy - 1) if spy_close and previous_spy else 0.0
        matched_spy_return = spy_return * previous_gross_exposure
        gross_value = sum(pos["shares"] * last_close.get(sym, pos["entry_price"])
                          for sym, pos in positions.items())
        gross_exposure = gross_value / marked if marked else 0.0
        equity_curve.append({"date": date, "equity": round(marked, 2), "cash": round(cash, 2),
                             "positions": len(positions),
                             "gross_exposure_pct": round(gross_exposure * 100, 4),
                             "portfolio_return": round(portfolio_return, 8),
                             "spy_return": round(spy_return, 8),
                             "excess_return": round(portfolio_return - spy_return, 8),
                             "exposure_matched_spy_return": round(matched_spy_return, 8),
                             "exposure_matched_excess_return": round(portfolio_return - matched_spy_return, 8)})
        previous_equity = marked
        previous_gross_exposure = gross_exposure
        if spy_close:
            previous_spy = spy_close

    # Liquidate remaining positions at their final available close, including costs.
    for sym, pos in list(positions.items()):
        bar = prices[sym][-1]
        exit_price = bar["close"] * (1 - one_way_cost)
        cash += pos["shares"] * exit_price
        trades.append({**pos, "exit_date": bar["date"], "exit_price": round(exit_price, 4),
                       "exit_reason": "end_of_data",
                       "net_return_pct": round((exit_price / pos["entry_price"] - 1) * 100, 2)})
    end_value = cash
    peak, max_dd = cfg.initial_cash, 0.0
    for row in equity_curve:
        peak = max(peak, row["equity"])
        max_dd = min(max_dd, row["equity"] / peak - 1)
    years = max(len(equity_curve) / 252, 1 / 252)
    cagr = (end_value / cfg.initial_cash) ** (1 / years) - 1
    return {"config": cfg.__dict__, "summary": {"signals": len(signals) + generated_reentries, "trades": len(trades),
            "end_value": round(end_value, 2), "total_return_pct": round((end_value / cfg.initial_cash - 1) * 100, 2),
            "cagr_pct": round(cagr * 100, 2), "max_drawdown_pct": round(max_dd * 100, 2),
            "rejected": dict(rejected)}, "trades": trades, "equity_curve": equity_curve}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--output-dir", default="backtests")
    ap.add_argument("--initial-cash", type=float, default=100_000)
    ap.add_argument("--commission-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=5.0)
    args = ap.parse_args()
    payload = json.load(open(args.backtest_json))
    client = CSVClient(args.price_csv)
    symbols = [r["symbol"] for r in client.get_constituents()] + ["SPY"]
    prices = {sym: list(reversed(client.get_historical_prices(sym, days=100_000)["historical"]))
              for sym in symbols}
    if args.commission_bps < 0 or args.slippage_bps < 0:
        ap.error("cost inputs must be non-negative")
    result = run_portfolio(payload.get("detections_by_ticker") or {}, prices,
                           Config(initial_cash=args.initial_cash,
                                  commission_bps=args.commission_bps,
                                  slippage_bps=args.slippage_bps))
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(args.output_dir, f"vcp_portfolio_{stamp}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    csv_path = path.replace(".json", "_daily.csv")
    with open(csv_path, "w", newline="") as f:
        fields = ["date", "equity", "cash", "positions", "gross_exposure_pct",
                  "portfolio_return", "spy_return", "excess_return",
                  "exposure_matched_spy_return", "exposure_matched_excess_return"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["equity_curve"])
    print(json.dumps(result["summary"], indent=2))
    print(path)
    print(csv_path)


if __name__ == "__main__":
    main()
