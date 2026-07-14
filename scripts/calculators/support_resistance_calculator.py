#!/usr/bin/env python3
"""Causal support/resistance zone detection for the VCP screener.

The module deliberately treats levels as zones.  Input OHLCV is the repository's
normal most-recent-first shape; all calculations are performed on a validated,
chronological copy.  A fixed-window swing is not available until ``window`` bars
after the extreme, and that confirmation date is carried through every zone.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import asdict, dataclass
from typing import Any, Optional


STRENGTH_ORDER = {"weak": 0, "moderate": 1, "strong": 2, "very_strong": 3}


@dataclass(frozen=True)
class SupportResistanceConfig:
    enabled: bool = True
    swing_window: int = 5
    lookback_period: int = 252
    atr_period: int = 14
    zone_tolerance_pct: float = 0.005
    zone_tolerance_atr: float = 0.5
    minimum_touches: int = 2
    breakout_confirmation_closes: int = 1
    breakout_min_distance_pct: float = 0.0
    breakout_volume_multiplier: float = 1.2
    require_breakout_volume: bool = False
    role_reversal_enabled: bool = True
    max_support_zones: int = 3
    max_resistance_zones: int = 3
    minimum_zone_strength: str = "moderate"
    pivot_zone_tolerance_pct: float = 0.01

    def __post_init__(self) -> None:
        if self.swing_window < 1 or self.lookback_period < 1 or self.atr_period < 1:
            raise ValueError("swing_window, lookback_period and atr_period must be positive")
        if self.minimum_touches < 1 or self.breakout_confirmation_closes < 1:
            raise ValueError("touch and close confirmation counts must be positive")
        if self.max_support_zones < 1 or self.max_resistance_zones < 1:
            raise ValueError("zone output caps must be positive")
        if min(
            self.zone_tolerance_pct,
            self.zone_tolerance_atr,
            self.breakout_min_distance_pct,
            self.pivot_zone_tolerance_pct,
        ) < 0:
            raise ValueError("zone tolerances and breakout distance cannot be negative")
        if self.breakout_volume_multiplier <= 0:
            raise ValueError("breakout_volume_multiplier must be positive")
        if self.minimum_zone_strength not in STRENGTH_ORDER:
            raise ValueError(f"unknown minimum_zone_strength: {self.minimum_zone_strength}")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SupportResistanceFilterConfig:
    near_support_pct: Optional[float] = None
    below_resistance_pct: Optional[float] = None
    breaking_above_resistance: bool = False
    retesting_former_resistance: bool = False
    min_support_strength: Optional[str] = None
    min_resistance_strength: Optional[str] = None
    min_reward_risk_ratio: Optional[float] = None
    pivot_near_resistance_pct: Optional[float] = None
    vcp_breakout_above_resistance: bool = False

    def __post_init__(self) -> None:
        numeric = (
            self.near_support_pct,
            self.below_resistance_pct,
            self.min_reward_risk_ratio,
            self.pivot_near_resistance_pct,
        )
        if any(value is not None and value < 0 for value in numeric):
            raise ValueError("support/resistance filter thresholds cannot be negative")
        for strength in (self.min_support_strength, self.min_resistance_strength):
            if strength is not None and strength not in STRENGTH_ORDER:
                raise ValueError(f"unknown zone strength: {strength}")

    def as_dict(self) -> dict:
        return asdict(self)


def _config(value: SupportResistanceConfig | dict | None) -> SupportResistanceConfig:
    if value is None:
        return SupportResistanceConfig()
    if isinstance(value, SupportResistanceConfig):
        return value
    allowed = SupportResistanceConfig.__dataclass_fields__
    return SupportResistanceConfig(**{k: v for k, v in value.items() if k in allowed})


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _normalise_bars(historical_prices: list[dict], lookback: int) -> list[dict]:
    """Return valid bars oldest-first without mutating the caller's list."""
    out: list[dict] = []
    for offset, raw in enumerate(reversed((historical_prices or [])[:lookback])):
        if not isinstance(raw, dict):
            continue
        close = _finite(raw.get("close"))
        high = _finite(raw.get("high"), close)
        low = _finite(raw.get("low"), close)
        if close <= 0 or high <= 0 or low <= 0 or high < low:
            continue
        out.append(
            {
                "date": str(raw.get("date") or f"bar-{offset}"),
                "open": _finite(raw.get("open"), close),
                "high": high,
                "low": low,
                "close": close,
                "volume": max(0.0, _finite(raw.get("volume"))),
            }
        )
    return out


def _atr_series(bars: list[dict], period: int) -> list[Optional[float]]:
    if not bars:
        return []
    true_ranges = [bars[0]["high"] - bars[0]["low"]]
    for index in range(1, len(bars)):
        previous_close = bars[index - 1]["close"]
        true_ranges.append(
            max(
                bars[index]["high"] - bars[index]["low"],
                abs(bars[index]["high"] - previous_close),
                abs(bars[index]["low"] - previous_close),
            )
        )
    result: list[Optional[float]] = []
    for index in range(len(bars)):
        start = max(0, index - period + 1)
        window = true_ranges[start : index + 1]
        result.append(sum(window) / len(window) if window else None)
    return result


def _rolling_volume_average(bars: list[dict], index: int, period: int = 50) -> float:
    values = [b["volume"] for b in bars[max(0, index - period + 1) : index + 1] if b["volume"] > 0]
    return sum(values) / len(values) if values else 0.0


def detect_swing_points(
    historical_prices: list[dict],
    config: SupportResistanceConfig | dict | None = None,
    *,
    swing_window: Optional[int] = None,
    lookback_period: Optional[int] = None,
) -> dict:
    """Detect strictly confirmed swing highs/lows.

    The extreme occurs at ``index`` but is usable only at ``confirmed_index``.
    Consequently the last ``swing_window`` bars can never be emitted as swings.
    Reaction statistics use only the same following bars required to confirm the
    swing, never bars after its availability date.
    """
    cfg = _config(config)
    window = swing_window if swing_window is not None else cfg.swing_window
    lookback = lookback_period if lookback_period is not None else cfg.lookback_period
    if window < 1:
        return {"highs": [], "lows": [], "bars": [], "error": "swing_window must be positive"}
    bars = _normalise_bars(historical_prices, lookback)
    if len(bars) < window * 2 + 1:
        return {"highs": [], "lows": [], "bars": bars, "error": "insufficient_history"}
    atrs = _atr_series(bars, cfg.atr_period)
    highs: list[dict] = []
    lows: list[dict] = []
    for index in range(window, len(bars) - window):
        before = bars[index - window : index]
        after = bars[index + 1 : index + window + 1]
        bar = bars[index]
        confirmed_index = index + window
        avg_volume = _rolling_volume_average(bars, index)
        volume_ratio = bar["volume"] / avg_volume if avg_volume > 0 else 0.0
        atr = atrs[confirmed_index] or 0.0
        if all(bar["high"] > other["high"] for other in before + after):
            reaction = max(0.0, bar["high"] - min(other["low"] for other in after))
            reaction_pct = reaction / bar["high"] * 100
            point = _point(
                "resistance", bar["high"], index, confirmed_index, bars,
                bar["volume"], volume_ratio, reaction_pct,
                reaction / atr if atr > 0 else 0.0,
            )
            point["tolerance"] = max(
                bar["high"] * cfg.zone_tolerance_pct, atr * cfg.zone_tolerance_atr
            )
            highs.append(point)
        if all(bar["low"] < other["low"] for other in before + after):
            reaction = max(0.0, max(other["high"] for other in after) - bar["low"])
            reaction_pct = reaction / bar["low"] * 100
            point = _point(
                "support", bar["low"], index, confirmed_index, bars,
                bar["volume"], volume_ratio, reaction_pct,
                reaction / atr if atr > 0 else 0.0,
            )
            point["tolerance"] = max(
                bar["low"] * cfg.zone_tolerance_pct, atr * cfg.zone_tolerance_atr
            )
            lows.append(point)
    return {"highs": highs, "lows": lows, "bars": bars, "error": None}


def _point(
    zone_type: str,
    price: float,
    index: int,
    confirmed_index: int,
    bars: list[dict],
    volume: float,
    volume_ratio: float,
    reaction_pct: float,
    reaction_atr: float,
    *,
    source: str = "swing",
    major: Optional[bool] = None,
) -> dict:
    if major is None:
        major = reaction_atr >= 2.0 or reaction_pct >= 5.0
    return {
        "type": zone_type,
        "original_type": zone_type,
        "price": price,
        "index": index,
        "date": bars[index]["date"],
        "confirmed_index": confirmed_index,
        "confirmed_date": bars[confirmed_index]["date"],
        "available_date": bars[confirmed_index]["date"],
        "volume": volume,
        "volume_ratio": volume_ratio,
        "reaction_pct": reaction_pct,
        "reaction_atr": reaction_atr,
        "major": bool(major),
        "source": source,
    }


def _consolidation_points(bars: list[dict], cfg: SupportResistanceConfig) -> list[dict]:
    """Add sparse rolling-range boundaries as consolidation evidence."""
    width = max(10, cfg.swing_window * 4)
    if len(bars) < width:
        return []
    atrs = _atr_series(bars, cfg.atr_period)
    points: list[dict] = []
    for end in range(width - 1, len(bars), max(5, width // 2)):
        start = end - width + 1
        section = bars[start : end + 1]
        high_offset = max(range(len(section)), key=lambda i: section[i]["high"])
        low_offset = min(range(len(section)), key=lambda i: section[i]["low"])
        high_index, low_index = start + high_offset, start + low_offset
        high, low = bars[high_index]["high"], bars[low_index]["low"]
        mid = (high + low) / 2
        atr = atrs[end] or 0.0
        if mid <= 0 or high - low > max(mid * 0.10, atr * 4):
            continue
        for kind, price, index in (("resistance", high, high_index), ("support", low, low_index)):
            avg = _rolling_volume_average(bars, index)
            point = _point(
                kind, price, index, end, bars, bars[index]["volume"],
                bars[index]["volume"] / avg if avg > 0 else 0.0, 0.0, 0.0,
                source="consolidation", major=False,
            )
            point["tolerance"] = max(
                price * cfg.zone_tolerance_pct, atr * cfg.zone_tolerance_atr
            )
            points.append(point)
    return points


def _high_volume_price_points(
    bars: list[dict], cfg: SupportResistanceConfig
) -> list[dict]:
    """Return a few daily high-volume closes as a volume-at-price proxy.

    Daily OHLCV cannot build a true intraday volume profile.  Restricting this
    proxy to the three largest >=1.5x rolling-volume bars keeps it explanatory
    and prevents volume nodes from overwhelming confirmed price reactions.
    """
    if not bars:
        return []
    current_price = bars[-1]["close"]
    atrs = _atr_series(bars, cfg.atr_period)
    candidates: list[tuple[float, int]] = []
    for index, bar in enumerate(bars):
        prior_average = _rolling_volume_average(bars, index - 1) if index > 0 else 0.0
        ratio = bar["volume"] / prior_average if prior_average > 0 else 0.0
        if ratio >= 1.5:
            candidates.append((ratio, index))
    points: list[dict] = []
    for ratio, index in sorted(candidates, reverse=True)[:3]:
        bar = bars[index]
        kind = "support" if bar["close"] <= current_price else "resistance"
        point = _point(
            kind,
            bar["close"],
            index,
            index,
            bars,
            bar["volume"],
            ratio,
            0.0,
            0.0,
            source="high_volume_close",
            major=False,
        )
        point["tolerance"] = max(
            bar["close"] * cfg.zone_tolerance_pct,
            (atrs[index] or 0.0) * cfg.zone_tolerance_atr,
        )
        points.append(point)
    return points


def _deduplicate_points(points: list[dict]) -> list[dict]:
    unique: dict[tuple[str, str], dict] = {}
    for point in points:
        key = (point["type"], point["date"])
        existing = unique.get(key)
        if existing is None or (point.get("major", False), point.get("reaction_atr", 0)) > (
            existing.get("major", False), existing.get("reaction_atr", 0)
        ):
            unique[key] = point
    return list(unique.values())


def cluster_price_zones(
    swing_points: list[dict] | dict,
    historical_prices: Optional[list[dict]] = None,
    config: SupportResistanceConfig | dict | None = None,
    *,
    atr: Optional[float] = None,
) -> list[dict]:
    """Cluster nearby same-role points using max(percent, ATR) tolerance."""
    cfg = _config(config)
    if isinstance(swing_points, dict):
        points = list(swing_points.get("highs", [])) + list(swing_points.get("lows", []))
    else:
        points = list(swing_points or [])
    if atr is None and historical_prices:
        bars = _normalise_bars(historical_prices, cfg.lookback_period)
        series = _atr_series(bars, cfg.atr_period)
        atr = next((value for value in reversed(series) if value), 0.0)
    atr = atr or 0.0
    zones: list[dict] = []
    # Confirmation order makes cluster membership causal: a later point may
    # join an established zone but can never change where an earlier point was
    # assigned.
    ordered_points = sorted(
        points,
        key=lambda item: (
            item.get("confirmed_index", item.get("index", 0)),
            item.get("type", ""),
            item.get("price", 0),
        ),
    )
    for point in ordered_points:
        price = _finite(point.get("price"))
        zone_type = point.get("type")
        if price <= 0 or zone_type not in ("support", "resistance"):
            continue
        tolerance = _finite(
            point.get("tolerance"),
            max(price * cfg.zone_tolerance_pct, atr * cfg.zone_tolerance_atr),
        )
        candidates = []
        for zone in zones:
            if zone["original_type"] != zone_type:
                continue
            # Membership must be acceptable under both the incoming point's
            # contemporaneous tolerance and the already-established cluster.
            # Otherwise a later high-ATR point could bridge two older zones and
            # retroactively rewrite their break/retest history.
            if abs(price - zone["midpoint"]) <= min(tolerance, zone["tolerance"]):
                candidates.append(zone)
        target = min(
            candidates,
            key=lambda candidate: abs(price - candidate["midpoint"]),
            default=None,
        )
        if target is None:
            target = {
                "original_type": zone_type,
                "type": zone_type,
                "points": [],
                "tolerance": tolerance,
            }
            zones.append(target)
        target["points"].append(point)
        prices = [p["price"] for p in target["points"]]
        target["tolerance"] = max(target["tolerance"], tolerance)
        target["midpoint"] = sum(prices) / len(prices)
        target["lower"] = min(prices) - target["tolerance"] / 2
        target["upper"] = max(prices) + target["tolerance"] / 2

    output: list[dict] = []
    for number, zone in enumerate(zones, 1):
        points = zone.pop("points")
        by_touch = sorted(points, key=lambda p: p["index"])
        by_confirmation = sorted(points, key=lambda p: p["confirmed_index"])
        dates = list(dict.fromkeys(p["date"] for p in by_touch))
        confirmed = list(dict.fromkeys(p["confirmed_date"] for p in by_confirmation))
        volumes = [p.get("volume", 0.0) for p in points if p.get("volume", 0) > 0]
        zone.update(
            {
                "id": f"{zone['original_type']}-{number}",
                "active": True,
                "touches": len(dates),
                "touch_dates": dates,
                "confirmation_dates": confirmed,
                "first_touch_date": dates[0] if dates else None,
                "most_recent_touch_date": dates[-1] if dates else None,
                "first_confirmed_date": confirmed[0] if confirmed else None,
                "most_recent_confirmed_date": confirmed[-1] if confirmed else None,
                "average_volume": sum(volumes) / len(volumes) if volumes else 0.0,
                "average_volume_ratio": sum(p.get("volume_ratio", 0.0) for p in points) / len(points),
                "average_reaction_pct": sum(p.get("reaction_pct", 0.0) for p in points) / len(points),
                "average_reaction_atr": sum(p.get("reaction_atr", 0.0) for p in points) / len(points),
                "major_swing": any(p.get("major", False) for p in points),
                "sources": sorted(set(p.get("source", "swing") for p in points)),
                "touch_records": [
                    {
                        "price": p["price"],
                        "date": p["date"],
                        "confirmed_index": p["confirmed_index"],
                        "confirmed_date": p["confirmed_date"],
                        "source": p.get("source", "swing"),
                        "tolerance": p.get("tolerance", zone["tolerance"]),
                    }
                    for p in by_touch
                ],
                "last_confirmed_index": max((p.get("confirmed_index", 0) for p in points), default=0),
                "role_reversal": False,
                "role_reversal_from": None,
                "role_reversal_date": None,
            }
        )
        output.append(zone)
    return output


def score_price_zone(
    zone: dict,
    historical_prices: list[dict],
    config: SupportResistanceConfig | dict | None = None,
    *,
    current_index: Optional[int] = None,
) -> dict:
    """Score a zone with an explicit 100-point formula.

    Components: confirmed touches 30, recency 15, confirmed reaction 20,
    relative touch volume 10, bars spent in the zone 10, major swing 10, and
    confirmed role reversal 5.  No component changes existing VCP scores.
    """
    cfg = _config(config)
    bars = _normalise_bars(historical_prices, cfg.lookback_period)
    return _score_price_zone_with_bars(zone, bars, cfg, current_index=current_index)


def _score_price_zone_with_bars(
    zone: dict,
    bars: list[dict],
    cfg: SupportResistanceConfig,
    *,
    current_index: Optional[int] = None,
) -> dict:
    current = len(bars) - 1 if current_index is None else min(current_index, len(bars) - 1)
    touches = min(30.0, zone.get("touches", 0) / 4 * 30.0)
    age = max(0, current - int(zone.get("last_confirmed_index", current)))
    recency = 15.0 * max(0.0, 1.0 - age / max(1, len(bars) - 1))
    reaction = 20.0 * min(1.0, max(0.0, zone.get("average_reaction_atr", 0.0)) / 3.0)
    volume = 10.0 * min(1.0, max(0.0, zone.get("average_volume_ratio", 0.0)) / 1.5)
    time_near = sum(1 for bar in bars if zone["lower"] <= bar["close"] <= zone["upper"])
    persistence = 10.0 * min(1.0, time_near / 10.0)
    major = 10.0 if zone.get("major_swing") else 0.0
    reversal = 5.0 if zone.get("role_reversal") else 0.0
    components = {
        "touches": round(touches, 2),
        "recency": round(recency, 2),
        "reaction": round(reaction, 2),
        "volume": round(volume, 2),
        "time_near_zone": round(persistence, 2),
        "major_swing": round(major, 2),
        "role_reversal": round(reversal, 2),
    }
    score = round(min(100.0, sum(components.values())), 2)
    if score >= 80:
        category = "very_strong"
    elif score >= 60:
        category = "strong"
    elif score >= 35:
        category = "moderate"
    else:
        category = "weak"
    result = dict(zone)
    result.update(
        {
            "strength_score": score,
            "strength": category,
            "strength_components": components,
            "time_near_zone_bars": time_near,
        }
    )
    return result


def detect_role_reversals(
    zones: list[dict],
    historical_prices: list[dict],
    config: SupportResistanceConfig | dict | None = None,
) -> list[dict]:
    """Detect close-confirmed breaks and later role-reversal retests.

    High/low wicks never increment the confirmation counter.  If volume
    confirmation is enabled, each confirming close must also meet the rolling
    50-bar volume multiplier.  A retest is evaluated only after the final
    confirming close, so role reversal cannot be recognised early.
    """
    cfg = _config(config)
    bars = _normalise_bars(historical_prices, cfg.lookback_period)
    return _detect_role_reversals_with_bars(zones, bars, cfg)


def _detect_role_reversals_with_bars(
    zones: list[dict], bars: list[dict], cfg: SupportResistanceConfig
) -> list[dict]:
    output: list[dict] = []
    for raw_zone in zones:
        zone = dict(raw_zone)
        original = zone["original_type"]
        required = max(1, cfg.breakout_confirmation_closes)
        consecutive = 0
        break_index: Optional[int] = None
        break_bounds = (zone["lower"], zone["upper"])
        touch_records = sorted(
            zone.get("touch_records") or [], key=lambda item: item["confirmed_index"]
        )
        # Replay clustered zones causally. A later touch may strengthen or widen
        # the zone, but it cannot erase a break that was observable from earlier
        # confirmed touches. Hand-built/public zones without touch records keep
        # the legacy single-availability behavior used by direct callers.
        available_from = (
            touch_records[0]["confirmed_index"] + 1
            if touch_records
            else int(zone.get("last_confirmed_index", -1)) + 1
        )
        available_from = min(len(bars), available_from)
        known_touch_count = 0
        for index in range(available_from, len(bars)):
            bar = bars[index]
            if touch_records:
                available_records = [
                    record for record in touch_records if record["confirmed_index"] < index
                ]
                if len(available_records) < cfg.minimum_touches:
                    consecutive = 0
                    continue
                if len(available_records) != known_touch_count:
                    # Bounds changed as a newly confirmed touch became known;
                    # confirmation closes must be consecutive under one shape.
                    consecutive = 0
                    known_touch_count = len(available_records)
                known_prices = [record["price"] for record in available_records]
                known_tolerance = max(
                    (record.get("tolerance", zone["tolerance"]) for record in available_records),
                    default=zone["tolerance"],
                )
                lower = min(known_prices) - known_tolerance / 2
                upper = max(known_prices) + known_tolerance / 2
            else:
                lower, upper = zone["lower"], zone["upper"]
            distance = cfg.breakout_min_distance_pct
            beyond = (
                bar["close"] > upper * (1 + distance)
                if original == "resistance"
                else bar["close"] < lower * (1 - distance)
            )
            # Compare breakout volume with information available before the
            # breakout bar; including the current spike would dilute its ratio.
            avg_volume = _rolling_volume_average(bars, index - 1) if index > 0 else 0.0
            volume_ok = (
                not cfg.require_breakout_volume
                or (avg_volume > 0 and bar["volume"] >= avg_volume * cfg.breakout_volume_multiplier)
            )
            if beyond and volume_ok:
                consecutive += 1
                if consecutive >= required:
                    break_index = index
                    break_bounds = (lower, upper)
                    break
            else:
                consecutive = 0
        zone["breakout_confirmed"] = original == "resistance" and break_index is not None
        zone["breakdown_confirmed"] = original == "support" and break_index is not None
        zone["break_confirmed_date"] = bars[break_index]["date"] if break_index is not None else None
        zone["break_confirmed_index"] = break_index
        zone["break_zone_lower"] = break_bounds[0] if break_index is not None else None
        zone["break_zone_upper"] = break_bounds[1] if break_index is not None else None
        if break_index is not None:
            zone["active"] = False
        if break_index is not None and cfg.role_reversal_enabled:
            for index in range(break_index + 1, len(bars)):
                bar = bars[index]
                if original == "resistance":
                    retest = bar["low"] <= break_bounds[1] and bar["close"] >= break_bounds[0]
                else:
                    retest = bar["high"] >= break_bounds[0] and bar["close"] <= break_bounds[1]
                if retest:
                    zone["type"] = "support" if original == "resistance" else "resistance"
                    zone["active"] = True
                    zone["role_reversal"] = True
                    zone["role_reversal_from"] = original
                    zone["role_reversal_date"] = bar["date"]
                    zone["role_reversal_index"] = index
                    break
        output.append(zone)
    return output


def find_nearest_zones(
    zones: list[dict],
    current_price: float,
    config: SupportResistanceConfig | dict | None = None,
) -> dict:
    """Return nearest active support/resistance and signed midpoint distances."""
    _config(config)  # validate/coerce for a consistent public contract
    supports = [z for z in zones if z.get("active", True) and z.get("type") == "support" and z["lower"] <= current_price]
    resistances = [z for z in zones if z.get("active", True) and z.get("type") == "resistance" and z["upper"] >= current_price]
    support = min(supports, key=lambda z: abs(current_price - z["midpoint"]), default=None)
    resistance = min(resistances, key=lambda z: abs(z["midpoint"] - current_price), default=None)
    support_distance = (
        (support["midpoint"] - current_price) / current_price * 100 if support and current_price > 0 else None
    )
    resistance_distance = (
        (resistance["midpoint"] - current_price) / current_price * 100
        if resistance and current_price > 0
        else None
    )
    risk = current_price - support["midpoint"] if support else None
    reward = resistance["midpoint"] - current_price if resistance else None
    reward_risk = reward / risk if reward is not None and risk is not None and reward >= 0 and risk > 0 else None
    return {
        "nearest_support": support,
        "nearest_resistance": resistance,
        "support_distance_pct": round(support_distance, 2) if support_distance is not None else None,
        "resistance_distance_pct": round(resistance_distance, 2) if resistance_distance is not None else None,
        "reward_risk_ratio": round(reward_risk, 2) if reward_risk is not None else None,
        "inside_support_zone": any(z["lower"] <= current_price <= z["upper"] for z in supports),
        "inside_resistance_zone": any(z["lower"] <= current_price <= z["upper"] for z in resistances),
    }


def _minimum_strength(zones: list[dict], category: str) -> list[dict]:
    minimum = STRENGTH_ORDER.get(str(category).lower(), STRENGTH_ORDER["moderate"])
    return [z for z in zones if STRENGTH_ORDER.get(z.get("strength", "weak"), 0) >= minimum]


def _calculate_payload(
    historical_prices: list[dict],
    cfg: SupportResistanceConfig,
    extra_points: Optional[list[dict]] = None,
) -> dict:
    neutral = _neutral_payload(cfg)
    if not cfg.enabled:
        neutral["status"] = "disabled"
        return neutral
    detected = detect_swing_points(historical_prices, cfg)
    bars = detected.get("bars", [])
    if not bars:
        neutral.update({"status": "insufficient_data", "error": detected.get("error")})
        return neutral
    points = list(detected.get("highs", [])) + list(detected.get("lows", []))
    points.extend(_consolidation_points(bars, cfg))
    points.extend(_high_volume_price_points(bars, cfg))
    points.extend(extra_points or [])
    points = _deduplicate_points(points)
    if not points:
        neutral.update({"status": "no_zones", "error": detected.get("error")})
        return neutral
    atrs = _atr_series(bars, cfg.atr_period)
    current_atr = next((value for value in reversed(atrs) if value), 0.0)
    zones = cluster_price_zones(points, None, cfg, atr=current_atr)
    zones = _detect_role_reversals_with_bars(zones, bars, cfg)
    zones = [_score_price_zone_with_bars(zone, bars, cfg) for zone in zones]
    zones = [z for z in zones if z["touches"] >= cfg.minimum_touches]
    eligible = _minimum_strength(zones, cfg.minimum_zone_strength)
    current_price = bars[-1]["close"]
    nearest = find_nearest_zones(eligible, current_price, cfg)
    supports = sorted(
        [z for z in eligible if z.get("active", True) and z["type"] == "support"],
        key=lambda z: abs(current_price - z["midpoint"]),
    )[: cfg.max_support_zones]
    resistances = sorted(
        [z for z in eligible if z.get("active", True) and z["type"] == "resistance"],
        key=lambda z: abs(z["midpoint"] - current_price),
    )[: cfg.max_resistance_zones]
    latest_date = bars[-1]["date"]
    resistance_breaks = [z for z in zones if z.get("breakout_confirmed")]
    support_breaks = [z for z in zones if z.get("breakdown_confirmed")]
    neutral.update(
        {
            "status": "ok",
            "error": None,
            "current_price": current_price,
            "as_of_date": latest_date,
            "zones": supports + resistances,
            "all_zones": zones,
            "support_zones": supports,
            "resistance_zones": resistances,
            "nearest_support": nearest["nearest_support"],
            "nearest_resistance": nearest["nearest_resistance"],
            "support_distance_pct": nearest["support_distance_pct"],
            "resistance_distance_pct": nearest["resistance_distance_pct"],
            "reward_risk_ratio": nearest["reward_risk_ratio"],
            "inside_support_zone": nearest["inside_support_zone"],
            "inside_resistance_zone": nearest["inside_resistance_zone"],
            "resistance_breakout": any(z["upper"] < current_price for z in resistance_breaks),
            "support_breakdown": any(z["lower"] > current_price for z in support_breaks),
            "resistance_breakout_today": any(z.get("break_confirmed_date") == latest_date for z in resistance_breaks),
            "support_breakdown_today": any(z.get("break_confirmed_date") == latest_date for z in support_breaks),
            "role_reversal_detected": any(z.get("role_reversal") for z in zones),
            "retest_today": any(z.get("role_reversal_date") == latest_date for z in zones),
            "swing_points": {"highs": detected.get("highs", []), "lows": detected.get("lows", [])},
        }
    )
    return neutral


def calculate_zone_metrics(
    historical_prices: list[dict],
    config: SupportResistanceConfig | dict | None = None,
    *,
    as_of_offset: int = 0,
) -> dict:
    cfg = _config(config)
    history = (historical_prices or [])[max(0, as_of_offset) :]
    return _calculate_payload(history, cfg)


def _vcp_points(vcp: dict, historical_prices: list[dict], cfg: SupportResistanceConfig) -> list[dict]:
    bars = _normalise_bars(historical_prices, cfg.lookback_period)
    atrs = _atr_series(bars, cfg.atr_period)
    date_index = {bar["date"]: index for index, bar in enumerate(bars)}
    points: list[dict] = []
    for contraction in vcp.get("contractions") or []:
        for kind, price_key, date_key in (
            ("resistance", "high_price", "high_date"),
            ("support", "low_price", "low_date"),
        ):
            price = _finite(contraction.get(price_key))
            date = str(contraction.get(date_key) or "")
            index = date_index.get(date)
            if price <= 0 or index is None or not bars:
                continue
            confirmed = index + cfg.swing_window
            if confirmed >= len(bars):
                # A VCP boundary close to the right edge is useful to VCP logic,
                # but it is not yet a fixed-window S/R swing.
                continue
            avg = _rolling_volume_average(bars, index)
            point = _point(
                kind, price, index, confirmed, bars, bars[index]["volume"],
                bars[index]["volume"] / avg if avg > 0 else 0.0,
                float(contraction.get("depth_pct") or 0), 0.0,
                source="vcp_contraction", major=True,
            )
            point["tolerance"] = max(
                price * cfg.zone_tolerance_pct,
                (atrs[confirmed] or 0.0) * cfg.zone_tolerance_atr,
            )
            points.append(point)
    return points


def enrich_vcp_result_with_zones(
    vcp_result: dict,
    historical_prices: list[dict],
    config: SupportResistanceConfig | dict | None = None,
    *,
    as_of_offset: int = 0,
) -> dict:
    """Return a copied candidate/VCP result with nested and flat S/R fields."""
    cfg = _config(config)
    result = dict(vcp_result or {})
    history = (historical_prices or [])[max(0, as_of_offset) :]
    vcp = result.get("vcp_pattern") if isinstance(result.get("vcp_pattern"), dict) else result
    payload = _calculate_payload(history, cfg, _vcp_points(vcp, history, cfg))
    pivot = _finite(vcp.get("pivot_price"))
    current_price = _finite(result.get("price"), payload.get("current_price") or 0.0)
    resistance_origins = [
        zone
        for zone in payload.get("all_zones", [])
        if zone.get("original_type") == "resistance"
        and strength_at_least(zone.get("strength"), cfg.minimum_zone_strength)
    ]
    matching = next(
        (
            z
            for z in resistance_origins
            if pivot > 0
            and z["lower"] * (1 - cfg.pivot_zone_tolerance_pct)
            <= pivot
            <= z["upper"] * (1 + cfg.pivot_zone_tolerance_pct)
        ),
        None,
    )
    pivot_nearest_resistance = min(
        resistance_origins,
        key=lambda zone: abs(zone["midpoint"] - pivot),
        default=None,
    ) if pivot > 0 else None
    pivot_resistance_distance = (
        abs(pivot_nearest_resistance["midpoint"] - pivot) / pivot * 100
        if pivot_nearest_resistance is not None and pivot > 0
        else None
    )
    contractions = vcp.get("contractions") or []
    last_low = _finite(contractions[-1].get("low_price")) if contractions else 0.0
    support_zones = [
        zone
        for zone in payload.get("all_zones", [])
        if zone.get("active", True)
        and zone.get("type") == "support"
        and strength_at_least(zone.get("strength"), cfg.minimum_zone_strength)
    ]
    last_support = min(support_zones, key=lambda z: abs(z["midpoint"] - last_low), default=None) if last_low else None
    base_support = max(support_zones, key=lambda z: z.get("strength_score", 0), default=None)
    # VCP-specific breakout evidence is tied to the resistance zone aligned
    # with the pivot. The general resistance_breakout field remains available
    # for breaks of unrelated historical zones.
    breakout_above = bool(
        matching
        and matching.get("breakout_confirmed")
        and current_price > (matching.get("break_zone_upper") or matching["upper"])
    )
    retest = bool(
        payload.get("retest_today")
        and any(z.get("role_reversal_from") == "resistance" for z in payload.get("all_zones", []))
    )
    distance_from_pivot = (
        (current_price - pivot) / pivot * 100 if current_price > 0 and pivot > 0 else result.get("distance_from_pivot_pct")
    )
    payload["vcp_signals"] = {
        "pivot_matches_resistance_zone": matching is not None,
        "breakout_above_resistance": breakout_above,
        "retest_of_breakout_zone": retest,
        "last_contraction_support": last_support,
        "base_support_zone": base_support,
        "distance_from_vcp_pivot_pct": round(distance_from_pivot, 2) if distance_from_pivot is not None else None,
        "pivot_resistance_distance_pct": round(pivot_resistance_distance, 2)
        if pivot_resistance_distance is not None
        else None,
        "breakout_volume_confirmed": bool(
            (result.get("volume_pattern") or {}).get("breakout_volume_detected")
        ),
        "breakout_holds_above_zone": breakout_above,
    }
    payload["chart_markers"] = {
        "latest_price": {"price": current_price or payload.get("current_price"), "date": payload.get("as_of_date")},
        "vcp_pivot": {"price": pivot, "date": contractions[-1].get("high_date") if contractions else None} if pivot else None,
        "breakout_point": next(
            (
                {"price": z["upper"], "date": z.get("break_confirmed_date")}
                for z in resistance_origins
                if z.get("breakout_confirmed")
            ),
            None,
        ),
    }
    result["support_resistance"] = payload
    support = payload.get("nearest_support")
    resistance = payload.get("nearest_resistance")
    aliases = {
        "nearest_support": support.get("midpoint") if support else None,
        "nearest_support_lower": support.get("lower") if support else None,
        "nearest_support_upper": support.get("upper") if support else None,
        "nearest_support_strength": support.get("strength") if support else None,
        "nearest_support_strength_score": support.get("strength_score") if support else None,
        "support_distance_pct": payload.get("support_distance_pct"),
        "nearest_resistance": resistance.get("midpoint") if resistance else None,
        "nearest_resistance_lower": resistance.get("lower") if resistance else None,
        "nearest_resistance_upper": resistance.get("upper") if resistance else None,
        "nearest_resistance_strength": resistance.get("strength") if resistance else None,
        "nearest_resistance_strength_score": resistance.get("strength_score") if resistance else None,
        "resistance_distance_pct": payload.get("resistance_distance_pct"),
        "reward_risk_ratio": payload.get("reward_risk_ratio"),
        "inside_support_zone": payload.get("inside_support_zone", False),
        "inside_resistance_zone": payload.get("inside_resistance_zone", False),
        "resistance_breakout": payload.get("resistance_breakout", False),
        "support_breakdown": payload.get("support_breakdown", False),
        "role_reversal_detected": payload.get("role_reversal_detected", False),
        "pivot_matches_resistance_zone": matching is not None,
        "breakout_above_resistance": breakout_above,
        "retest_of_breakout_zone": retest,
        "last_contraction_support": last_support.get("midpoint") if last_support else None,
        "base_support_zone": base_support.get("midpoint") if base_support else None,
        "distance_from_vcp_pivot_pct": round(distance_from_pivot, 2) if distance_from_pivot is not None else None,
        "pivot_resistance_distance_pct": round(pivot_resistance_distance, 2)
        if pivot_resistance_distance is not None
        else None,
    }
    result.update(aliases)
    return result


def _neutral_payload(cfg: SupportResistanceConfig) -> dict:
    return {
        "status": "empty",
        "error": None,
        "config": cfg.as_dict(),
        "zones": [],
        "all_zones": [],
        "support_zones": [],
        "resistance_zones": [],
        "nearest_support": None,
        "nearest_resistance": None,
        "support_distance_pct": None,
        "resistance_distance_pct": None,
        "reward_risk_ratio": None,
        "inside_support_zone": False,
        "inside_resistance_zone": False,
        "resistance_breakout": False,
        "support_breakdown": False,
        "resistance_breakout_today": False,
        "support_breakdown_today": False,
        "role_reversal_detected": False,
        "retest_today": False,
        "swing_points": {"highs": [], "lows": []},
    }


def strength_at_least(actual: Optional[str], required: Optional[str]) -> bool:
    if required is None:
        return True
    return STRENGTH_ORDER.get(str(actual or "weak").lower(), 0) >= STRENGTH_ORDER.get(str(required).lower(), 0)


def passes_support_resistance_filters(
    result: dict, filters: SupportResistanceFilterConfig | dict | None
) -> bool:
    if filters is None:
        return True
    if isinstance(filters, dict):
        allowed = SupportResistanceFilterConfig.__dataclass_fields__
        filters = SupportResistanceFilterConfig(**{k: v for k, v in filters.items() if k in allowed})
    support_distance = result.get("support_distance_pct")
    resistance_distance = result.get("resistance_distance_pct")
    if filters.near_support_pct is not None:
        if support_distance is None or abs(float(support_distance)) > filters.near_support_pct:
            return False
        required_support = filters.min_support_strength or "strong"
        if not strength_at_least(result.get("nearest_support_strength"), required_support):
            return False
    if filters.below_resistance_pct is not None and (
        resistance_distance is None or not (0 <= float(resistance_distance) <= filters.below_resistance_pct)
    ):
        return False
    if filters.breaking_above_resistance:
        current_price = _finite(result.get("price"))
        broken_zones = [
            zone
            for zone in (result.get("support_resistance") or {}).get("all_zones", [])
            if zone.get("original_type") == "resistance"
            and zone.get("breakout_confirmed")
            and current_price > zone.get("upper", math.inf)
            and strength_at_least(zone.get("strength"), "strong")
        ]
        if not broken_zones:
            return False
    if filters.retesting_former_resistance and not result.get("retest_of_breakout_zone"):
        return False
    if not strength_at_least(result.get("nearest_support_strength"), filters.min_support_strength):
        return False
    if not strength_at_least(result.get("nearest_resistance_strength"), filters.min_resistance_strength):
        return False
    if filters.min_reward_risk_ratio is not None and (
        result.get("reward_risk_ratio") is None
        or float(result["reward_risk_ratio"]) < filters.min_reward_risk_ratio
    ):
        return False
    if filters.pivot_near_resistance_pct is not None:
        pivot_distance = result.get("pivot_resistance_distance_pct")
        if pivot_distance is None or float(pivot_distance) > filters.pivot_near_resistance_pct:
            return False
    if filters.vcp_breakout_above_resistance and not result.get("breakout_above_resistance"):
        return False
    return True


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def add_support_resistance_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("Support and resistance")
    group.add_argument("--no-support-resistance", action="store_true", help="Disable zone enrichment")
    group.add_argument("--sr-swing-window", type=_positive_int, default=5)
    group.add_argument("--sr-lookback-period", type=_positive_int, default=252)
    group.add_argument("--sr-atr-period", type=_positive_int, default=14)
    group.add_argument("--sr-zone-tolerance-pct", type=_non_negative_float, default=0.005)
    group.add_argument("--sr-zone-tolerance-atr", type=_non_negative_float, default=0.5)
    group.add_argument("--sr-minimum-touches", type=_positive_int, default=2)
    group.add_argument("--sr-breakout-confirmation-closes", type=_positive_int, default=1)
    group.add_argument("--sr-breakout-min-distance-pct", type=_non_negative_float, default=0.0)
    group.add_argument("--sr-breakout-volume-multiplier", type=_positive_float, default=1.2)
    group.add_argument("--sr-require-breakout-volume", action="store_true")
    group.add_argument("--sr-no-role-reversal", action="store_true")
    group.add_argument("--sr-max-support-zones", type=_positive_int, default=3)
    group.add_argument("--sr-max-resistance-zones", type=_positive_int, default=3)
    group.add_argument(
        "--sr-minimum-zone-strength", choices=list(STRENGTH_ORDER), default="moderate"
    )
    group.add_argument("--sr-near-support-pct", type=_non_negative_float)
    group.add_argument("--sr-below-resistance-pct", type=_non_negative_float)
    group.add_argument("--sr-breaking-above-resistance", action="store_true")
    group.add_argument("--sr-retesting-former-resistance", action="store_true")
    group.add_argument("--sr-min-support-strength", choices=list(STRENGTH_ORDER))
    group.add_argument("--sr-min-resistance-strength", choices=list(STRENGTH_ORDER))
    group.add_argument("--sr-min-reward-risk-ratio", type=_non_negative_float)
    group.add_argument("--sr-pivot-near-resistance-pct", type=_non_negative_float)
    group.add_argument("--sr-vcp-breakout-above-resistance", action="store_true")


def support_resistance_config_from_args(args: argparse.Namespace) -> SupportResistanceConfig:
    return SupportResistanceConfig(
        enabled=not getattr(args, "no_support_resistance", False),
        swing_window=args.sr_swing_window,
        lookback_period=args.sr_lookback_period,
        atr_period=args.sr_atr_period,
        zone_tolerance_pct=args.sr_zone_tolerance_pct,
        zone_tolerance_atr=args.sr_zone_tolerance_atr,
        minimum_touches=args.sr_minimum_touches,
        breakout_confirmation_closes=args.sr_breakout_confirmation_closes,
        breakout_min_distance_pct=args.sr_breakout_min_distance_pct,
        breakout_volume_multiplier=args.sr_breakout_volume_multiplier,
        require_breakout_volume=args.sr_require_breakout_volume,
        role_reversal_enabled=not args.sr_no_role_reversal,
        max_support_zones=args.sr_max_support_zones,
        max_resistance_zones=args.sr_max_resistance_zones,
        minimum_zone_strength=args.sr_minimum_zone_strength,
    )


def support_resistance_filters_from_args(args: argparse.Namespace) -> SupportResistanceFilterConfig:
    return SupportResistanceFilterConfig(
        near_support_pct=args.sr_near_support_pct,
        below_resistance_pct=args.sr_below_resistance_pct,
        breaking_above_resistance=args.sr_breaking_above_resistance,
        retesting_former_resistance=args.sr_retesting_former_resistance,
        min_support_strength=args.sr_min_support_strength,
        min_resistance_strength=args.sr_min_resistance_strength,
        min_reward_risk_ratio=args.sr_min_reward_risk_ratio,
        pivot_near_resistance_pct=args.sr_pivot_near_resistance_pct,
        vcp_breakout_above_resistance=args.sr_vcp_breakout_above_resistance,
    )
