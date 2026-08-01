#!/usr/bin/env python3
"""Prespecified Trial 328-333 cross-sectional VCP leadership lifecycle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, build_rows, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from undercut_reclaim_discovery import gate


def discovery_backtest_score(cell: dict, survivorship_unresolved: bool = True) -> dict:
    """Apply the analyst rubric to a train-only cell with a reduced denominator."""
    robustness = cell.get("robustness") or {}
    significance = robustness.get("significance") or {}
    adjusted = robustness.get("risk_adjusted") or {}
    risk = robustness.get("risk") or {}
    stability = robustness.get("stability") or {}
    bootstrap = robustness.get("block_bootstrap") or {}
    trade_stats = cell.get("trade_stats") or {}

    t_stat = float(significance.get("t_statistic") or 0)
    t_points = 8 if t_stat > 3 else 6 if t_stat > 2 else 4 if t_stat > 1.65 else 0
    psr = float(significance.get("psr_vs_zero") or 0)
    psr_points = 7 if psr > .95 else 5 if psr > .90 else 3 if psr > .80 else 0
    n_eff = float(significance.get("effective_sample_size") or 0)
    sample_points = 7 if n_eff >= 252 else 4 if n_eff >= 100 else 0
    # Hundreds of declared trials and a sub-1% approximate DSR probability earn zero.
    dsr_probability = float((significance.get("approximate_dsr") or {}).get("probability") or 0)
    dsr_points = 8 if dsr_probability > .95 else 4 if dsr_probability > .50 else 0
    score_a = t_points + psr_points + sample_points + dsr_points

    sharpe = float(adjusted.get("sharpe") or 0)
    sharpe_points = 10 if sharpe > 2 else 7 if sharpe > 1 else 4 if sharpe > .5 else 0
    sortino = float(adjusted.get("sortino") or 0)
    calmar = float(adjusted.get("calmar") or 0)
    secondary = max(sortino, calmar)
    secondary_points = 8 if secondary > 2.5 else 6 if secondary > 1.5 else 3 if secondary > .7 else 0
    mdd = abs(float(risk.get("max_drawdown") or 0))
    drawdown_points = 7 if mdd < .10 else 5 if mdd < .20 else 3 if mdd < .30 else 0
    score_b = sharpe_points + secondary_points + drawdown_points

    cagr_bootstrap = bootstrap.get("cagr") or {}
    bootstrap_points = (8 if float(cagr_bootstrap.get("p05") or 0) > 0
                        else 4 if float(cagr_bootstrap.get("median") or 0) > 0 else 0)
    score_c = bootstrap_points

    pf = float(trade_stats.get("profit_factor") or 0)
    pf_points = 7 if pf > 2 else 5 if pf > 1.5 else 3 if pf > 1.2 else 0
    expectancy = float(trade_stats.get("expectancy_pct") or 0)
    win_rate = trade_stats.get("win_rate")
    payoff = trade_stats.get("payoff_ratio")
    coherence_points = 6 if expectancy > 0 and win_rate is not None and payoff is not None else 0
    positive_months = float(stability.get("positive_months") or 0)
    consistency_points = 7 if positive_months > .65 else 5 if positive_months > .55 else 3 if positive_months > .50 else 0
    score_d = pf_points + coherence_points + consistency_points

    measured_total = score_a + score_b + score_c + score_d
    measured_denominator = 30 + 25 + 8 + 20
    normalized = round(100 * measured_total / measured_denominator)
    caps = [{"reason": "no formal out-of-sample or walk-forward segment", "cap": 55}]
    if survivorship_unresolved:
        caps.insert(0, {"reason": "unresolved survivorship bias / incomplete delisted coverage",
                        "cap": 20})
    lowest_cap = min(cap["cap"] for cap in caps)
    final = min(normalized, lowest_cap)
    band = ("Tradeable" if final >= 80 else "Promising" if final >= 65
            else "Needs work" if final >= 45 else "Weak" if final >= 25 else "Reject")
    return {
        "classification": "discovery_train_only",
        "components": {
            "A_statistical_validity": {"score": score_a, "max": 30},
            "B_risk_adjusted_performance": {"score": score_b, "max": 25},
            "C_robustness_computable": {"score": score_c, "max": 8},
            "D_trade_quality_consistency": {"score": score_d, "max": 20},
        },
        "unavailable": {"walk_forward_efficiency": 10,
                        "parameter_sensitivity": 7},
        "measured_total": measured_total,
        "measured_denominator": measured_denominator,
        "reduced_denominator_normalized_raw_score": normalized,
        "caps_applied": caps,
        "final_score": final,
        "band": band,
        "note": "The lowest applicable cap is applied after reduced-denominator normalization. This discovery-only score cannot qualify the strategy.",
    }


def active_symbol_rows(rows: list[dict]) -> list[dict]:
    """Keep the newest causal setup per symbol/date, then the higher Edge Rank."""
    chosen: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["signal_date"], row["symbol"])
        current = chosen.get(key)
        priority = (row.get("as_of_date") or "", float(row.get("edge_rank") or 0),
                    row.get("setup_id") or "")
        current_priority = ((current.get("as_of_date") or ""),
                            float(current.get("edge_rank") or 0),
                            current.get("setup_id") or "") if current else None
        if current is None or priority > current_priority:
            chosen[key] = row
    return sorted(chosen.values(), key=lambda item: (
        item["signal_date"], item["symbol"], item["setup_id"],
    ))


def _percentile_ranks(values: list[float]) -> list[float]:
    """Return average-tie ranks scaled to [0, 1], or 0.5 for a singleton."""
    if len(values) == 1:
        return [.5]
    result = []
    for value in values:
        positions = [index for index, candidate in enumerate(sorted(values))
                     if candidate == value]
        result.append((sum(positions) / len(positions)) / (len(values) - 1))
    return result


def leadership_states(rows: list[dict]) -> list[dict]:
    """Attach same-date short/intermediate cross-sectional leadership ranks."""
    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in active_symbol_rows(rows):
        by_date[row["signal_date"]].append(row)
    states = []
    for date in sorted(by_date):
        cohort = sorted(by_date[date], key=lambda item: item["symbol"])
        ret5 = [float(row["features"][5]) for row in cohort]
        ret20 = [float(row["features"][7]) for row in cohort]
        ranks5 = _percentile_ranks(ret5)
        ranks20 = _percentile_ranks(ret20)
        for row, rank5, rank20 in zip(cohort, ranks5, ranks20):
            states.append({
                **row,
                "rank_ret5": rank5,
                "rank_ret20": rank20,
                "leadership": (rank5 + rank20) / 2,
                "above_sma20": float(row["features"][9]) > 0,
            })
    return states


def lifecycle_signals(states: list[dict], entry_threshold: float = .70,
                      exit_threshold: float = .40,
                      max_attempts: int = 3) -> list[dict]:
    """Emit fresh leadership crossings and causal next-open decay exits."""
    if not 0 <= exit_threshold < entry_threshold <= 1 or max_attempts <= 0:
        raise ValueError("invalid leadership lifecycle parameters")
    by_setup: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        by_setup[state["setup_id"]].append(state)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda item: item["signal_date"])
        cursor = 1
        attempts = 0
        while cursor < len(ordered) and attempts < max_attempts:
            entry_pos = next((index for index in range(cursor, len(ordered))
                              if ordered[index - 1]["leadership"] < entry_threshold
                              and ordered[index]["leadership"] >= entry_threshold
                              and ordered[index]["above_sma20"]), None)
            if entry_pos is None:
                break
            entry = ordered[entry_pos]
            exit_pos = next((index for index in range(entry_pos + 1, len(ordered))
                             if ordered[index]["leadership"] <= exit_threshold
                             and not ordered[index]["above_sma20"]), None)
            attempts += 1
            signal = {key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal.update({"attempt": attempts,
                           "leadership": entry["leadership"],
                           "rank_ret5": entry.get("rank_ret5"),
                           "rank_ret20": entry.get("rank_ret20")})
            if exit_pos is not None:
                signal["model_exit_idx"] = ordered[exit_pos]["fill_idx"]
                cursor = exit_pos + 1
            else:
                cursor = len(ordered)
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def _period_rows(detections: dict, membership: dict, prices: dict[str, list[dict]],
                 start: str, end: str) -> tuple[list[dict], int]:
    selected, dropped = filter_detections(detections, membership, start, end)
    rows = build_rows(selected, prices, with_labels=False)
    return [row for row in rows if start <= row["signal_date"] <= end], dropped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/cross_sectional_leadership_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

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
        detections, membership, train_prices, *FIT,
    )
    train_states = leadership_states(train_rows)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=333)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    backtest_score = discovery_backtest_score(train_cell)

    holdout = None
    holdout_raw = None
    holdout_drops = None
    if train_gate["passed"]:
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_rows, holdout_drops = _period_rows(
            detections, membership, holdout_prices, *HOLDOUT,
        )
        holdout_states = leadership_states(holdout_rows)
        holdout_signals = lifecycle_signals(holdout_states)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="model_decay", trials_declared=333)
        holdout_cell = compact(holdout_raw)
        holdout = {"candidate_rows": len(holdout_rows),
                   "active_symbol_rows": len(holdout_states),
                   "signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "backtest_score": backtest_score,
        "family_spec": "backtests/cross_sectional_leadership_v2/frozen_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage,
        "trials_before": 327,
        "new_multiplicity_units": 6,
        "trials_after": 333,
        "parameters": {"short_return_sessions": 5,
                       "intermediate_return_sessions": 20,
                       "entry_leadership": .70,
                       "exit_leadership": .40,
                       "exit_requires_below_sma20": True,
                       "max_attempts": 3,
                       "max_hold_sessions": 60},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"candidate_rows": len(train_rows),
                  "active_symbol_rows": len(train_states),
                  "signals": train_signals, "cell": train_cell,
                  "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"cross_sectional_leadership_{stamp}.json"
    mp = out / f"cross_sectional_leadership_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 328–333 — Cross-Sectional VCP Leadership Lifecycle", "",
             "Formal validation accessed: **NO**", "",
             f"## Backtest Score: {backtest_score['final_score']}/100 — {backtest_score['band']}", "",
             "Discovery-only reduced-denominator score; it cannot qualify the strategy.", "",
             "| Component | Score | Available max |", "|---|---:|---:|",
             f"| A. Statistical validity | {backtest_score['components']['A_statistical_validity']['score']} | 30 |",
             f"| B. Risk-adjusted performance | {backtest_score['components']['B_risk_adjusted_performance']['score']} | 25 |",
             f"| C. Robustness (bootstrap only) | {backtest_score['components']['C_robustness_computable']['score']} | 8 |",
             f"| D. Trade quality / consistency | {backtest_score['components']['D_trade_quality_consistency']['score']} | 20 |",
             f"| **Measured total** | **{backtest_score['measured_total']}** | **{backtest_score['measured_denominator']}** |",
             f"| **Normalized raw score** | **{backtest_score['reduced_denominator_normalized_raw_score']}** | **100** |",
             "| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |",
             f"| **Final score** | **{backtest_score['final_score']}** | **100** |", "",
             "WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap then applies to the normalized score.", "",
             f"Train active rows {len(train_states)}; signals {len(train_signals)}; "
             f"trades {train_cell['trade_stats']['trades']}; "
             f"CAGR {train_cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"Internal holdout accessed: **{'YES' if holdout else 'NO'}**", "",
              "Formal validation and untouched OOS remain sealed.", ""]
    mp.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            out / f"cross_sectional_leadership_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"cross_sectional_leadership_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"cross_sectional_leadership_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"cross_sectional_leadership_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp)
    print(mp)


if __name__ == "__main__":
    main()
