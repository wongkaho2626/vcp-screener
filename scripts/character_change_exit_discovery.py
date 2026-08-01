#!/usr/bin/env python3
"""Prespecified Trial 496-504 strong-stock character-change exit audit."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import _period_rows, _score_table
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from dmi_crossover_lifecycle_discovery import (
    VALIDATION,
    VALIDATION_PRICE_END,
    VALIDATION_PRICE_START,
)
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, is_member, load_membership
from pivot_retest_experiment import slice_prices
from portfolio_backtest import Config
from undercut_reclaim_discovery import gate

STRENGTH_WINDOW = 10
STRENGTH_REQUIRED = 8
SMA_FAST = 10
SMA_SLOW = 20
ABNORMAL_GAP = -.06
ABNORMAL_CLOSE_RETURN = -.16
RECOVERY_WINDOW = 10
SWING_WINDOW = 5
ACTIVATION_MIN = 30
TRIALS_BEFORE = 495
TRIALS_AFTER = 504


def simple_moving_average(bars: list[dict], index: int,
                          window: int) -> float | None:
    """Return an inclusive completed-close SMA, or None without full history."""
    if window <= 0:
        raise ValueError("moving-average window must be positive")
    if index < window - 1 or index >= len(bars):
        return None
    closes = [float(bar.get("close") or 0)
              for bar in bars[index - window + 1:index + 1]]
    if any(close <= 0 for close in closes):
        return None
    return statistics.fmean(closes)


def is_strong_state(
    bars: list[dict], index: int,
    strength_window: int = STRENGTH_WINDOW,
    strength_required: int = STRENGTH_REQUIRED,
    sma_fast: int = SMA_FAST,
    sma_slow: int = SMA_SLOW,
) -> bool:
    """Test persistent completed-close support above both contemporaneous SMAs."""
    if strength_window <= 0 or not 0 < strength_required <= strength_window:
        raise ValueError("invalid strength persistence parameters")
    if index < strength_window - 1 or index >= len(bars):
        return False
    qualifying = 0
    current_above = False
    for position in range(index - strength_window + 1, index + 1):
        fast = simple_moving_average(bars, position, sma_fast)
        slow = simple_moving_average(bars, position, sma_slow)
        close = float(bars[position].get("close") or 0)
        above = bool(fast is not None and slow is not None
                     and close > fast and close > slow)
        qualifying += int(above)
        if position == index:
            current_above = above
    return current_above and qualifying >= strength_required


def is_abnormal_down_day(
    bars: list[dict], index: int,
    gap_threshold: float = ABNORMAL_GAP,
    close_return_threshold: float = ABNORMAL_CLOSE_RETURN,
) -> bool:
    """Test the frozen gap-down / close-loss rule on a completed bar."""
    if gap_threshold >= 0 or close_return_threshold >= 0:
        raise ValueError("abnormal-down thresholds must be negative")
    if index <= 0 or index >= len(bars):
        return False
    prior_close = float(bars[index - 1].get("close") or 0)
    open_price = float(bars[index].get("open") or 0)
    close = float(bars[index].get("close") or 0)
    if prior_close <= 0 or open_price <= 0 or close <= 0:
        return False
    return (open_price / prior_close - 1 <= gap_threshold
            or close / prior_close - 1 <= close_return_threshold)


def detection_entry_signals(rows: list[dict], membership: dict) -> list[dict]:
    """Select unchanged detection-day next-open signals with fill-date PIT checks."""
    signals = []
    for row in rows:
        if row["signal_date"] != row["as_of_date"]:
            continue
        if not is_member(membership, row["symbol"], row["fill_date"]):
            continue
        signals.append({key: row[key] for key in (
            "symbol", "sector", "signal_date", "fill_date", "fill_idx",
            "edge_rank", "pattern_stop", "pivot",
        )})
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def character_change_exit(
    signal: dict, bars: list[dict], cfg: Config = Config(),
) -> dict | None:
    """Return the first causal custom-exit activation before stop/timeout."""
    entry_idx = int(signal["fill_idx"])
    if entry_idx <= 0 or entry_idx >= len(bars):
        return None
    raw_open = float(bars[entry_idx].get("open") or 0)
    pattern_stop = float(signal.get("pattern_stop") or 0)
    if raw_open <= pattern_stop or raw_open <= 0:
        return None
    one_way_cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    fill_price = raw_open * (1 + one_way_cost)
    stop = max(pattern_stop, fill_price * (1 - cfg.max_risk_pct / 100))

    armed = False
    damaged = False
    damage_idx: int | None = None
    resistance_low: float | None = None
    swing_low: float | None = None
    terminal = min(len(bars) - 2, entry_idx + cfg.max_hold_bars - 1)
    for index in range(entry_idx, terminal + 1):
        # The existing engine does not apply the daily hard stop on the entry
        # bar. Thereafter an intraday stop removes the position before its
        # completed close can establish a new custom-exit state.
        if index > entry_idx and float(bars[index].get("low") or 0) <= stop:
            return None

        if armed:
            if is_abnormal_down_day(bars, index):
                return {"signal_idx": index, "model_exit_idx": index + 1,
                        "reason": "abnormal_down_day"}

            close = float(bars[index].get("close") or 0)
            if damaged:
                if swing_low is not None and close < swing_low:
                    return {"signal_idx": index, "model_exit_idx": index + 1,
                            "reason": "frozen_swing_low_break"}
                elapsed = index - int(damage_idx)
                high = float(bars[index].get("high") or 0)
                if (1 <= elapsed <= RECOVERY_WINDOW
                        and resistance_low is not None
                        and high >= resistance_low and close < resistance_low):
                    return {"signal_idx": index, "model_exit_idx": index + 1,
                            "reason": "failed_ma_cluster_recovery"}
            else:
                fast = simple_moving_average(bars, index, SMA_FAST)
                slow = simple_moving_average(bars, index, SMA_SLOW)
                if fast is not None and slow is not None and close < fast and close < slow:
                    damaged = True
                    damage_idx = index
                    resistance_low = min(fast, slow)
                    prior_lows = [float(bar.get("low") or 0)
                                  for bar in bars[index - SWING_WINDOW:index]]
                    swing_low = min(prior_lows) if len(prior_lows) == SWING_WINDOW else None
                    if swing_low is not None and close < swing_low:
                        return {"signal_idx": index,
                                "model_exit_idx": index + 1,
                                "reason": "frozen_swing_low_break"}

        # A bar can arm the position only after its close; it cannot also be
        # treated as a post-arm break on that same close.
        if not armed and is_strong_state(bars, index):
            armed = True
    return None


def attach_character_change_exits(
    signals: list[dict], prices: dict[str, list[dict]],
) -> tuple[list[dict], dict]:
    """Attach model exits without calculating a return or outcome label."""
    attached = []
    reasons: dict[str, int] = {}
    for signal in signals:
        activation = character_change_exit(
            signal, prices.get(signal["symbol"]) or [])
        enriched = dict(signal)
        if activation is not None:
            enriched["model_exit_idx"] = activation["model_exit_idx"]
            enriched["character_change_signal_idx"] = activation["signal_idx"]
            enriched["character_change_reason"] = activation["reason"]
            reason = activation["reason"]
            reasons[reason] = reasons.get(reason, 0) + 1
        attached.append(enriched)
    return attached, dict(sorted(reasons.items()))


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir",
                        default="backtests/character_change_exit_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]}

    train_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    train_rows, train_drops = _period_rows(
        detections, membership, train_prices, *FIT)
    baseline_signals = detection_entry_signals(train_rows, membership)
    train_signals, activation_reasons = attach_character_change_exits(
        baseline_signals, train_prices)
    activations = sum("model_exit_idx" in signal for signal in train_signals)
    activation_pass = activations >= ACTIVATION_MIN
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    density = {
        "baseline_signals": len(baseline_signals),
        "custom_exit_activations": activations,
        "activation_rate": activations / len(baseline_signals) if baseline_signals else 0,
        "symbols_activated": len({row["symbol"] for row in train_signals
                                  if "model_exit_idx" in row}),
        "activation_reasons": activation_reasons,
        "minimum": ACTIVATION_MIN,
        "maximum": len(baseline_signals),
        "passed": activation_pass,
    }
    common = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/character_change_exit_v2/frozen_spec.md",
        "hypothesis_classification": "user_supplied_mechanism_causal_translation",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "coverage": coverage,
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {
            "entry": "unchanged detection_entry next open",
            "strength_window": STRENGTH_WINDOW,
            "strength_required": STRENGTH_REQUIRED,
            "moving_averages": [SMA_FAST, SMA_SLOW],
            "abnormal_gap_pct": ABNORMAL_GAP * 100,
            "abnormal_close_return_pct": ABNORMAL_CLOSE_RETURN * 100,
            "damage": "first strict close below SMA10 and SMA20",
            "recovery_window_sessions": RECOVERY_WINDOW,
            "swing_low_sessions": SWING_WINDOW,
            "execution": "full exit at next open",
            "max_hold_sessions": Config().max_hold_bars,
        },
        "chronology": {
            "train": FIT,
            "embargo": ["2018-07-01", "2018-12-31"],
            "validation": VALIDATION,
            "best_available_frozen_oos": ["2022-01-01", "2026-03-31"],
        },
        "density": density,
        "membership_drops": {"train_detection_date": train_drops},
    }

    if not activation_pass:
        report = {
            **common,
            "classification": "outcome_free_activation_density_only",
            "return_evaluation_accessed": False,
            "validation_accessed": False,
            "best_available_oos_accessed": False,
            "permission_to_evaluate_returns": False,
        }
        json_path = output / f"character_change_exit_{stamp}.json"
        md_path = output / f"character_change_exit_{stamp}.md"
        json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        md_path.write_text(
            "# Trial 496–504 — Character-Change Exit Density Audit\n\n"
            "Return evaluation accessed: **NO**\n\n"
            f"Baseline signals: {len(baseline_signals)}; custom exit activations: "
            f"**{activations}** across {density['symbols_activated']} symbols; "
            f"required at least {ACTIVATION_MIN}.\n\n"
            f"Activation reasons: `{json.dumps(activation_reasons, sort_keys=True)}`.\n\n"
            "Density gate: **FAIL**. Family closed outcome-free; validation and "
            "best-available OOS remain sealed.\n"
        )
        print(json.dumps(density, indent=2))
        print(json_path)
        print(md_path)
        return

    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=TRIALS_AFTER)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)
    validation = None
    validation_drops = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_base = detection_entry_signals(validation_rows, membership)
        validation_signals, validation_reasons = attach_character_change_exits(
            validation_base, validation_prices)
        validation_raw = evaluate(
            validation_signals, validation_prices, args.iterations,
            exit_rule="model_decay", trials_declared=TRIALS_AFTER)
        validation_cell = compact(validation_raw)
        validation = {
            "baseline_signals": len(validation_base),
            "custom_exit_activations": sum(
                "model_exit_idx" in signal for signal in validation_signals),
            "activation_reasons": validation_reasons,
            "cell": validation_cell,
            "score": discovery_backtest_score(validation_cell),
            "gate": gate(validation_cell, 60, 15),
        }

    report = {
        **common,
        "classification": "train_return_evaluation",
        "return_evaluation_accessed": True,
        "validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "backtest_score": train_score,
        "train": {"cell": train_cell, "gate": train_gate},
        "validation": validation,
        "membership_drops": {
            "train_detection_date": train_drops,
            "validation_detection_date": validation_drops,
        },
        "open_best_available_oos": bool(
            validation and validation["gate"]["passed"]),
    }
    json_path = output / f"character_change_exit_{stamp}.json"
    md_path = output / f"character_change_exit_{stamp}.md"
    trades_path = output / f"character_change_exit_{stamp}_train_trades.csv"
    equity_path = output / f"character_change_exit_{stamp}_train_equity.csv"
    signals_path = output / f"character_change_exit_{stamp}_train_signals.csv"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    _write_csv(signals_path, train_signals)
    _write_csv(trades_path, train_raw["trades"])
    _write_csv(equity_path, train_raw["equity_curve"])
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    significance = (train_cell.get("robustness") or {}).get("significance") or {}
    lines = [
        "# Trial 496–504 — Strong-Stock Character-Change Exit", "",
        "Best-available frozen OOS accessed: **NO**", "",
        *_score_table(train_score),
        f"Outcome-free gate: {activations} custom exits / "
        f"{len(baseline_signals)} signals — **PASS**.", "",
        f"Train trades {train_cell['trade_stats']['trades']}; CAGR "
        f"{train_cell['summary']['cagr_pct']:.2f}%; Sharpe "
        f"{(adjusted.get('sharpe') or 0):.3f}; PF "
        f"{(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; MDD "
        f"{train_cell['summary']['max_drawdown_pct']:.2f}%; trim-five "
        f"expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
        f"Activation reasons: `{json.dumps(activation_reasons, sort_keys=True)}`.", "",
        f"t-stat {(significance.get('t_statistic') or 0):.3f}; PSR "
        f"{100 * (significance.get('psr_vs_zero') or 0):.1f}%; approximate DSR "
        f"probability {100 * ((significance.get('approximate_dsr') or {}).get('probability') or 0):.3f}%.", "",
        f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", "",
    ]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += [
        "", f"2019–2021 validation accessed: "
        f"**{'YES' if validation else 'NO'}**", "",
        "2022–2026Q1 best-available OOS remains sealed.", "",
        "This exit-only result cannot overcome the previously established "
        "~18.72% hindsight-perfect-exit train ceiling for the unchanged entry.", "",
    ]
    md_path.write_text("\n".join(lines))
    print(json.dumps({"density": density, "train": train_cell,
                      "gate": train_gate, "score": train_score}, indent=2))
    print(json_path)
    print(md_path)
    print(signals_path)
    print(trades_path)
    print(equity_path)


if __name__ == "__main__":
    main()
