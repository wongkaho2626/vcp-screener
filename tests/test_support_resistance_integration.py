"""Integration tests for VCP candidate enrichment and optional scan filters."""

from datetime import date, timedelta
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

import screen_vcp
from calculators.support_resistance_calculator import (
    SupportResistanceConfig,
    SupportResistanceFilterConfig,
    enrich_vcp_result_with_zones,
    passes_support_resistance_filters,
)


def mrf_bars(closes, *, highs=None, lows=None, volumes=None, start="2024-02-01"):
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


def test_existing_vcp_candidate_is_enriched_with_zone_and_derived_fields():
    history = mrf_bars(
        [100, 100, 100, 100, 100, 100, 100],
        highs=[101, 110, 101, 101, 101, 101, 101],
        lows=[99, 99, 90, 99, 99, 99, 99],
    )
    candidate = {
        "symbol": "SYN",
        "price": 105,
        "composite_score": 81,
        "vcp_pattern": {
            "pivot_price": 110,
            "contractions": [
                {
                    "high_price": 110,
                    "high_date": "2024-02-02",
                    "low_price": 90,
                    "low_date": "2024-02-03",
                    "depth_pct": 18.18,
                }
            ],
        },
    }
    config = SupportResistanceConfig(
        swing_window=1,
        minimum_touches=1,
        minimum_zone_strength="weak",
        zone_tolerance_atr=0,
        role_reversal_enabled=False,
    )

    result = enrich_vcp_result_with_zones(candidate, history, config)

    assert result["symbol"] == "SYN"
    assert result["composite_score"] == 81
    assert result["pivot_matches_resistance_zone"] is True
    assert result["last_contraction_support"] == 90
    assert result["base_support_zone"] == 90
    assert result["distance_from_vcp_pivot_pct"] == -4.55
    assert "support_resistance" in result


def test_candidate_breakout_above_identified_resistance_is_derived():
    history = mrf_bars(
        [99, 99, 99, 103],
        highs=[100, 100, 100, 104],
        lows=[98, 98, 98, 102],
    )
    candidate = {
        "symbol": "BRK",
        "price": 103,
        "vcp_pattern": {
            "pivot_price": 100,
            "contractions": [
                {
                    "high_price": 100,
                    "high_date": "2024-02-02",
                    "low_price": 98,
                    "low_date": "2024-02-01",
                    "depth_pct": 2,
                }
            ],
        },
    }
    config = SupportResistanceConfig(
        swing_window=1,
        minimum_touches=1,
        minimum_zone_strength="weak",
        zone_tolerance_atr=0,
        role_reversal_enabled=False,
    )

    result = enrich_vcp_result_with_zones(candidate, history, config)

    assert result["resistance_breakout"] is True
    assert result["breakout_above_resistance"] is True


def test_default_filter_configuration_does_not_exclude_candidate():
    candidate = {
        "support_distance_pct": None,
        "resistance_distance_pct": None,
        "reward_risk_ratio": None,
    }

    assert passes_support_resistance_filters(candidate, SupportResistanceFilterConfig()) is True


def test_opt_in_minimum_reward_risk_filter_excludes_low_ratio_candidate():
    candidate = {"reward_risk_ratio": 1.5}
    filters = SupportResistanceFilterConfig(min_reward_risk_ratio=2.0)

    assert passes_support_resistance_filters(candidate, filters) is False


def patch_base_vcp_pipeline(monkeypatch):
    monkeypatch.setattr(screen_vcp, "calculate_relative_strength", lambda *_: {"rs_rank_estimate": 80, "score": 8})
    monkeypatch.setattr(
        screen_vcp,
        "calculate_trend_template",
        lambda *_, **__: {"score": 8, "sma50": 95, "sma200": 80},
    )
    monkeypatch.setattr(
        screen_vcp,
        "calculate_vcp_pattern",
        lambda *_, **__: {
            "valid_vcp": True,
            "wide_and_loose": False,
            "pivot_price": 100,
            "contractions": [{"low_price": 90, "depth_pct": 10}],
            "num_contractions": 1,
            "score": 8,
        },
    )
    monkeypatch.setattr(
        screen_vcp,
        "calculate_volume_pattern",
        lambda *_, **__: {"score": 8, "breakout_volume_detected": False, "dry_up_ratio": 0.5},
    )
    monkeypatch.setattr(
        screen_vcp,
        "calculate_pivot_proximity",
        lambda *_, **__: {"score": 8, "distance_from_pivot_pct": 1.0},
    )
    monkeypatch.setattr(
        screen_vcp,
        "compute_execution_state",
        lambda **_: {"state": "NEAR_PIVOT", "reasons": []},
    )
    monkeypatch.setattr(screen_vcp, "classify_pattern", lambda **_: "VCP")
    monkeypatch.setattr(
        screen_vcp,
        "calculate_composite_score",
        lambda **_: {
            "composite_score": 80,
            "quality_rating": "A",
            "rating": "A",
            "rating_description": "synthetic",
            "guidance": "synthetic",
            "weakest_component": "volume",
            "weakest_score": 8,
            "strongest_component": "trend",
            "strongest_score": 8,
        },
    )


def test_analyze_stock_keeps_enriched_candidate_when_filters_are_not_requested(monkeypatch):
    patch_base_vcp_pipeline(monkeypatch)
    monkeypatch.setattr(
        screen_vcp,
        "enrich_vcp_result_with_zones",
        lambda result, *_args, **_kwargs: {**result, "sr_enriched": True},
    )

    result = screen_vcp.analyze_stock(
        "SYN",
        mrf_bars([99, 100, 101]),
        {"price": 101, "marketCap": 1_000_000},
        [],
    )

    assert result is not None
    assert result["sr_enriched"] is True


def test_analyze_stock_applies_opt_in_support_resistance_filter(monkeypatch):
    patch_base_vcp_pipeline(monkeypatch)
    monkeypatch.setattr(
        screen_vcp,
        "enrich_vcp_result_with_zones",
        lambda result, *_args, **_kwargs: {**result, "reward_risk_ratio": 1.0},
    )

    result = screen_vcp.analyze_stock(
        "SYN",
        mrf_bars([99, 100, 101]),
        {"price": 101, "marketCap": 1_000_000},
        [],
        support_resistance_filters=SupportResistanceFilterConfig(min_reward_risk_ratio=2.0),
    )

    assert result is None
