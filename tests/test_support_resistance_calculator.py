"""Deterministic tests for causal support/resistance calculations.

Repository OHLCV inputs are most-recent-first (MRF).  The helpers below accept
chronological values for readability and reverse them at the API boundary.
"""

from datetime import date, timedelta
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from calculators.support_resistance_calculator import (
    SupportResistanceConfig,
    calculate_zone_metrics,
    cluster_price_zones,
    detect_role_reversals,
    detect_swing_points,
    enrich_vcp_result_with_zones,
    find_nearest_zones,
    score_price_zone,
)


def mrf_bars(closes, *, highs=None, lows=None, volumes=None, start="2024-01-01"):
    """Build the screener's MRF OHLCV shape from chronological inputs."""
    highs = highs or [value + 1 for value in closes]
    lows = lows or [value - 1 for value in closes]
    volumes = volumes or [1_000] * len(closes)
    first = date.fromisoformat(start)
    chronological = [
        {
            "date": str(first + timedelta(days=index)),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        for index, (close, high, low, volume) in enumerate(
            zip(closes, highs, lows, volumes)
        )
    ]
    return list(reversed(chronological))


def point(zone_type, price, index, *, reaction_atr=1.0, major=False):
    touch_date = f"2024-01-{index + 1:02d}"
    confirmed_date = f"2024-01-{index + 3:02d}"
    return {
        "type": zone_type,
        "original_type": zone_type,
        "price": price,
        "index": index,
        "date": touch_date,
        "confirmed_index": index + 2,
        "confirmed_date": confirmed_date,
        "available_date": confirmed_date,
        "volume": 1_000,
        "volume_ratio": 1.0,
        "reaction_pct": 2.0,
        "reaction_atr": reaction_atr,
        "major": major,
        "source": "swing",
    }


def zone(zone_type, lower, upper, midpoint=None, **overrides):
    value = {
        "id": f"{zone_type}-test",
        "original_type": zone_type,
        "type": zone_type,
        "lower": lower,
        "upper": upper,
        "midpoint": midpoint if midpoint is not None else (lower + upper) / 2,
        "active": True,
        "touches": 1,
        "last_confirmed_index": 0,
        "average_reaction_atr": 0.0,
        "average_volume_ratio": 0.0,
        "major_swing": False,
        "role_reversal": False,
    }
    value.update(overrides)
    return value


def test_swing_high_is_emitted_with_future_confirmation_date():
    bars = mrf_bars(
        [10, 11, 12, 11, 10],
        highs=[11, 12, 16, 12, 11],
        lows=[9, 10, 11, 10, 9],
    )

    result = detect_swing_points(bars, swing_window=2)

    assert [(item["price"], item["date"], item["confirmed_date"]) for item in result["highs"]] == [
        (16.0, "2024-01-03", "2024-01-05")
    ]


def test_swing_low_is_emitted_with_future_confirmation_date():
    bars = mrf_bars(
        [10, 9, 8, 9, 10],
        highs=[11, 10, 9, 10, 11],
        lows=[9, 8, 4, 8, 9],
    )

    result = detect_swing_points(bars, swing_window=2)

    assert [(item["price"], item["date"], item["confirmed_date"]) for item in result["lows"]] == [
        (4.0, "2024-01-03", "2024-01-05")
    ]


def test_unconfirmed_right_edge_extreme_is_not_a_swing():
    four_bars = mrf_bars(
        [10, 11, 15, 12],
        highs=[11, 12, 20, 13],
        lows=[9, 10, 14, 11],
    )

    result = detect_swing_points(four_bars, swing_window=2)

    assert result["highs"] == []


def test_nearby_swing_prices_cluster_into_one_zone():
    config = SupportResistanceConfig(zone_tolerance_pct=0.01, zone_tolerance_atr=0)

    zones = cluster_price_zones(
        [point("support", 100.0, 0), point("support", 100.5, 3)],
        config=config,
        atr=0,
    )

    assert len(zones) == 1
    assert zones[0]["lower"] < 100.0 < zones[0]["upper"]
    assert zones[0]["lower"] < 100.5 < zones[0]["upper"]


def test_cluster_records_distinct_touches_and_confirmation_dates():
    config = SupportResistanceConfig(zone_tolerance_pct=0.01, zone_tolerance_atr=0)

    clustered = cluster_price_zones(
        [point("resistance", 100.0, 0), point("resistance", 100.4, 3)],
        config=config,
        atr=0,
    )[0]

    assert clustered["touches"] == 2
    assert clustered["touch_dates"] == ["2024-01-01", "2024-01-04"]
    assert clustered["confirmation_dates"] == ["2024-01-03", "2024-01-06"]


def test_later_wide_tolerance_touch_cannot_merge_older_narrow_zones():
    points = [
        point("resistance", 100.0, 0),
        point("resistance", 100.2, 3),
        point("resistance", 105.0, 6),
        point("resistance", 105.2, 9),
        point("resistance", 103.0, 12),
    ]
    for item in points[:4]:
        item["tolerance"] = 0.5
    points[-1]["tolerance"] = 10.0

    zones = cluster_price_zones(points, atr=0)

    assert len(zones) == 3
    assert sorted(zone["touches"] for zone in zones) == [1, 2, 2]


def test_high_quality_zone_scores_stronger_than_weak_zone():
    bars = mrf_bars([100] * 20, highs=[101] * 20, lows=[99] * 20)
    strong = zone(
        "support",
        99,
        101,
        touches=4,
        last_confirmed_index=19,
        average_reaction_atr=3.0,
        average_volume_ratio=1.5,
        major_swing=True,
    )
    weak = zone("support", 90, 91)

    strong_score = score_price_zone(strong, bars)
    weak_score = score_price_zone(weak, bars)

    assert strong_score["strength_score"] > weak_score["strength_score"]
    assert strong_score["strength"] in {"strong", "very_strong"}
    assert weak_score["strength"] == "weak"


def test_broken_resistance_later_retests_as_support():
    resistance = zone("resistance", 99.5, 100.5, first_confirmed_date="2024-01-01")
    bars = mrf_bars(
        [99, 101, 100.4],
        highs=[100, 102, 101],
        lows=[98, 100.8, 100.0],
    )

    result = detect_role_reversals([resistance], bars)[0]

    assert result["type"] == "support"
    assert result["role_reversal_from"] == "resistance"
    assert result["role_reversal_date"] == "2024-01-03"


def test_broken_support_later_retests_as_resistance():
    support = zone("support", 99.5, 100.5, first_confirmed_date="2024-01-01")
    bars = mrf_bars(
        [101, 99, 99.6],
        highs=[102, 99.2, 100.0],
        lows=[100.7, 98, 99.0],
    )

    result = detect_role_reversals([support], bars)[0]

    assert result["type"] == "resistance"
    assert result["role_reversal_from"] == "support"
    assert result["role_reversal_date"] == "2024-01-03"


def test_intraday_wick_above_resistance_does_not_confirm_breakout():
    resistance = zone("resistance", 99.5, 100.5)
    bars = mrf_bars([99, 100], highs=[100, 103], lows=[98, 99])

    result = detect_role_reversals([resistance], bars)[0]

    assert result["breakout_confirmed"] is False


def test_close_above_resistance_confirms_breakout():
    resistance = zone("resistance", 99.5, 100.5)
    bars = mrf_bars([99, 101], highs=[100, 102], lows=[98, 100.8])
    config = SupportResistanceConfig(role_reversal_enabled=False)

    result = detect_role_reversals([resistance], bars, config)[0]

    assert result["breakout_confirmed"] is True
    assert result["break_confirmed_date"] == "2024-01-02"


def test_breakout_requires_configured_number_of_consecutive_closes():
    resistance = zone("resistance", 99.5, 100.5)
    bars = mrf_bars(
        [99, 101, 100, 101, 102],
        highs=[100, 102, 101, 102, 103],
        lows=[98, 100, 99, 100, 101],
    )
    config = SupportResistanceConfig(
        breakout_confirmation_closes=2,
        role_reversal_enabled=False,
    )

    result = detect_role_reversals([resistance], bars, config)[0]

    assert result["break_confirmed_date"] == "2024-01-05"


def test_nearest_zone_selection_prefers_closest_midpoints():
    zones = [
        zone("support", 89, 91, 90),
        zone("support", 94, 96, 95),
        zone("resistance", 109, 111, 110),
        zone("resistance", 119, 121, 120),
    ]

    result = find_nearest_zones(zones, 100)

    assert result["nearest_support"]["midpoint"] == 95
    assert result["nearest_resistance"]["midpoint"] == 110


def test_price_inside_support_zone_is_reported():
    zones = [zone("support", 99, 101, 100), zone("resistance", 109, 111, 110)]

    result = find_nearest_zones(zones, 100)

    assert result["inside_support_zone"] is True
    assert result["inside_resistance_zone"] is False


def test_reward_risk_uses_nearest_zone_midpoints():
    zones = [zone("support", 94, 96, 95), zone("resistance", 109, 111, 110)]

    result = find_nearest_zones(zones, 100)

    assert result["reward_risk_ratio"] == 2.0


def test_no_support_below_price_returns_none():
    result = find_nearest_zones([zone("resistance", 109, 111, 110)], 100)

    assert result["nearest_support"] is None
    assert result["support_distance_pct"] is None


def test_no_resistance_above_price_returns_none():
    result = find_nearest_zones([zone("support", 94, 96, 95)], 100)

    assert result["nearest_resistance"] is None
    assert result["resistance_distance_pct"] is None


def test_missing_ohlcv_returns_neutral_insufficient_data_payload():
    result = calculate_zone_metrics([])

    assert result["status"] == "insufficient_data"
    assert result["zones"] == []
    assert result["nearest_support"] is None


def test_malformed_candles_are_skipped_without_raising():
    result = calculate_zone_metrics(
        [None, "bad-row", {}, {"date": "2024-01-01", "close": 100, "high": 101, "low": 99}]
    )

    assert result["status"] in {"insufficient_data", "no_zones"}
    assert result["nearest_support"] is None


def test_insufficient_history_reports_error_without_fabricating_swings():
    bars = mrf_bars([100, 101, 102])

    result = detect_swing_points(bars, swing_window=2)

    assert result["error"] == "insufficient_history"
    assert result["highs"] == []
    assert result["lows"] == []


def test_swing_attributes_are_invariant_when_later_bars_are_appended():
    initial = mrf_bars(
        [10, 11, 12, 11, 10],
        highs=[11, 12, 16, 12, 11],
        lows=[9, 10, 11, 10, 9],
    )
    extended = mrf_bars(
        [10, 11, 12, 11, 10, 10, 10],
        highs=[11, 12, 16, 12, 11, 11, 11],
        lows=[9, 10, 11, 10, 9, 9, 9],
    )

    original = detect_swing_points(initial, swing_window=2)["highs"][0]
    after_future_bars = detect_swing_points(extended, swing_window=2)["highs"][0]

    stable_fields = ("price", "date", "confirmed_date", "reaction_pct", "major")
    assert {key: original[key] for key in stable_fields} == {
        key: after_future_bars[key] for key in stable_fields
    }


def test_breaks_before_zone_confirmation_are_ignored():
    resistance = zone(
        "resistance",
        99.5,
        100.5,
        first_confirmed_date="2024-01-03",
        last_confirmed_index=2,
    )
    bars = mrf_bars(
        [102, 99, 99],
        highs=[103, 100, 100],
        lows=[101, 98, 98],
    )

    result = detect_role_reversals([resistance], bars)[0]

    assert result["breakout_confirmed"] is False


def test_later_clustered_touch_does_not_erase_earlier_confirmed_reversal():
    resistance = zone(
        "resistance",
        99.5,
        100.5,
        touches=3,
        tolerance=6.0,
        last_confirmed_index=6,
        touch_records=[
            {"price": 100.0, "confirmed_index": 0, "tolerance": 1.0},
            {"price": 100.1, "confirmed_index": 2, "tolerance": 1.0},
            {"price": 100.2, "confirmed_index": 6, "tolerance": 6.0},
        ],
    )
    bars = mrf_bars(
        [99, 99, 99, 102, 100.2, 101, 100.1, 101],
        highs=[100, 100, 100, 103, 101, 102, 101, 102],
        lows=[98, 98, 98, 101, 100.0, 100.8, 99.8, 100.8],
    )

    result = detect_role_reversals([resistance], bars)[0]

    assert result["break_confirmed_date"] == "2024-01-04"
    assert result["role_reversal_date"] == "2024-01-05"


def test_disabled_enrichment_preserves_candidate_and_returns_neutral_fields():
    candidate = {"symbol": "SYN", "composite_score": 77, "vcp_pattern": {}}

    result = enrich_vcp_result_with_zones(
        candidate,
        mrf_bars([100, 101, 102]),
        SupportResistanceConfig(enabled=False),
    )

    assert result["symbol"] == "SYN"
    assert result["composite_score"] == 77
    assert result["support_resistance"]["status"] == "disabled"
    assert result["nearest_support"] is None
