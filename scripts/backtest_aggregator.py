#!/usr/bin/env python3
"""Backtest aggregation — pure functions that turn per-ticker VCP detection
lists (from ``historical_scanner.scan_history``) into portfolio-level stats.

All functions are side-effect free: they take detection dicts and return new
dicts, never mutating their inputs.

Outcome semantics (from ``calculators.forward_outcome``):
- ``breakout``          : close crossed above pivot within the outcome window
- ``stop_hit``          : close fell below the stop before any breakout
- ``timeout``           : neither triggered inside the window
- ``insufficient_data`` : not enough forward bars to evaluate
"""

from __future__ import annotations

OUTCOME_TYPES = ("breakout", "stop_hit", "timeout", "insufficient_data")

# Rating bands mirror references/scoring_system.md.
RATING_BANDS = (
    ("Textbook VCP (90+)", 90.0, 101.0),
    ("Strong VCP (80-89)", 80.0, 90.0),
    ("Good VCP (70-79)", 70.0, 80.0),
    ("Developing (60-69)", 60.0, 70.0),
    ("Weak (<60)", 0.0, 60.0),
)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _outcome_counts(detections: list[dict]) -> dict:
    counts = {k: 0 for k in OUTCOME_TYPES}
    for det in detections:
        outcome = (det.get("forward_outcome") or {}).get("outcome_type")
        if outcome in counts:
            counts[outcome] += 1
    return counts


def summarize_outcomes(detections: list[dict]) -> dict:
    """Pooled outcome distribution plus trajectory stats for a detection list.

    ``breakout_rate_pct`` is computed over *resolved* detections (breakout +
    stop_hit + timeout), excluding insufficient_data, so recent unresolvable
    detections don't dilute the rate.
    """
    counts = _outcome_counts(detections)
    resolved = counts["breakout"] + counts["stop_hit"] + counts["timeout"]

    breakout_days: list[float] = []
    stop_days: list[float] = []
    max_gains: list[float] = []
    max_losses: list[float] = []
    breakout_max_gains: list[float] = []
    stop_max_losses: list[float] = []
    for det in detections:
        fo = det.get("forward_outcome") or {}
        outcome = fo.get("outcome_type")
        days = fo.get("days_to_outcome")
        gain = fo.get("max_gain_pct")
        loss = fo.get("max_loss_pct")
        if gain is not None:
            max_gains.append(gain)
        if loss is not None:
            max_losses.append(loss)
        if outcome == "breakout":
            if days is not None:
                breakout_days.append(days)
            if gain is not None:
                breakout_max_gains.append(gain)
        elif outcome == "stop_hit":
            if days is not None:
                stop_days.append(days)
            if loss is not None:
                stop_max_losses.append(loss)

    return {
        "total_detections": len(detections),
        "resolved": resolved,
        "counts": counts,
        "breakout_rate_pct": round(counts["breakout"] / resolved * 100, 1) if resolved else None,
        "stop_hit_rate_pct": round(counts["stop_hit"] / resolved * 100, 1) if resolved else None,
        "timeout_rate_pct": round(counts["timeout"] / resolved * 100, 1) if resolved else None,
        "avg_days_to_breakout": _mean(breakout_days),
        "avg_days_to_stop": _mean(stop_days),
        "avg_max_gain_pct": _mean(max_gains),
        "avg_max_loss_pct": _mean(max_losses),
        "avg_max_gain_on_breakout_pct": _mean(breakout_max_gains),
        "avg_max_loss_on_stop_pct": _mean(stop_max_losses),
    }


def group_by_year(detections: list[dict]) -> dict[str, list[dict]]:
    """Bucket detections by the year of their as-of (detection) date."""
    groups: dict[str, list[dict]] = {}
    for det in detections:
        as_of = det.get("as_of_date") or ""
        year = as_of[:4] if len(as_of) >= 4 else "unknown"
        groups = {**groups, year: [*groups.get(year, []), det]}
    return groups


def group_by_rating_band(detections: list[dict]) -> dict[str, list[dict]]:
    """Bucket detections by composite-score rating band."""
    groups: dict[str, list[dict]] = {}
    for det in detections:
        score = det.get("composite_score") or 0.0
        label = next(
            (name for name, lo, hi in RATING_BANDS if lo <= score < hi),
            "Weak (<60)",
        )
        groups = {**groups, label: [*groups.get(label, []), det]}
    return groups


def build_backtest_summary(per_ticker: dict[str, list[dict]]) -> dict:
    """Assemble the full backtest summary from per-ticker detection lists.

    Args:
        per_ticker: symbol -> chronological detections from ``scan_history``.

    Returns:
        Dict with pooled stats plus per-ticker, per-year, and per-rating-band
        breakdowns. Never mutates inputs.
    """
    all_detections = [det for dets in per_ticker.values() for det in dets]

    by_year = {
        year: summarize_outcomes(dets)
        for year, dets in sorted(group_by_year(all_detections).items())
    }
    band_groups = group_by_rating_band(all_detections)
    by_rating = {
        name: summarize_outcomes(band_groups[name])
        for name, _, _ in RATING_BANDS
        if name in band_groups
    }
    ticker_stats = {
        sym: summarize_outcomes(dets) for sym, dets in sorted(per_ticker.items())
    }

    return {
        "tickers_scanned": len(per_ticker),
        "tickers_with_detections": sum(1 for d in per_ticker.values() if d),
        "overall": summarize_outcomes(all_detections),
        "by_year": by_year,
        "by_rating_band": by_rating,
        "by_ticker": ticker_stats,
    }
