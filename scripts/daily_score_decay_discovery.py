#!/usr/bin/env python3
"""Purged Trial 256-272 daily ridge entry with causal score-decay exit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FIT, FIT_PRICE_END, HOLDOUT,
    build_rows, compact, evaluate, fit_ridge, signals_with_decay, signals_from_rows,
    fit_quadratic_ridge,
    fit_logistic_ridge,
    lifecycle_signals_with_decay,
    signals_with_loss_decay,
    threshold_from_rows,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from pullback_followthrough_discovery import holdout_gate


def markdown(report: dict) -> str:
    cell = report["internal_holdout"]["cell"]
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = [
        f"# Daily {report['model']['model_type'].title()} Ridge / Score-Decay Exit", "",
        f"Generated: {report['generated_at']}", "",
        "Formal validation accessed: **NO**", "",
        f"Fit rows/setups: {report['model']['fit_rows']} / {report['model']['fit_setups']}",
        f"Calibration rows: {report['calibration']['rows']}",
        f"Entry p{report['calibration']['entry_percentile']}: "
        f"{report['calibration']['entry_threshold']:.6f}",
        f"Exit p50: {report['calibration']['exit_threshold']:.6f}", "",
        f"## {report.get('evaluation_label', '2020–2021 internal holdout')}", "",
        f"Signals {cell['summary']['signals']}; trades {cell['trade_stats']['trades']}; "
        f"CAGR {cell['summary']['cagr_pct']:.2f}%; Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
        f"PF {(cell['trade_stats']['profit_factor'] or 0):.3f}; "
        f"MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
        f"trim-5 expectancy {(cell['drop_top_5']['expectancy_pct'] or 0):.2f}%.", "",
        f"Gate: **{'PASS' if report['internal_holdout']['gate']['passed'] else 'FAIL'}**", "",
    ]
    for check, passed in report["internal_holdout"]["gate"]["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {check}")
    if report.get("exploratory_only"):
        lines += [
            "", "Exploratory-only replay: this gate cannot authorise formal validation.",
            "Formal validation and untouched OOS remain sealed.", "",
        ]
    else:
        lines += ["", "Formal validation and untouched OOS remain sealed.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/daily_score_decay_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument("--model-type", choices=("linear", "quadratic", "logistic"), default="linear")
    ap.add_argument("--logistic-label-threshold", type=float)
    ap.add_argument("--trials-before", type=int, default=255)
    ap.add_argument("--new-multiplicity-units", type=int, default=17)
    ap.add_argument("--trials-declared", type=int, default=272)
    ap.add_argument(
        "--family-spec", default="backtests/daily_score_decay_v2/family_spec.md",
    )
    ap.add_argument("--result-prefix", default="daily_score_decay")
    ap.add_argument("--label-mode", choices=("best_exit", "forward20", "survive20"), default="best_exit")
    ap.add_argument("--entry-percentile", type=float, default=85)
    ap.add_argument("--exit-mode", choices=("decay", "loss_decay", "fixed20"), default="decay")
    ap.add_argument("--entry-mode", choices=("first", "lifecycle"), default="first")
    ap.add_argument("--gate-cagr", type=float, default=15.0)
    ap.add_argument("--gate-trades", type=int, default=25)
    ap.add_argument("--fit-start", default=FIT[0])
    ap.add_argument("--fit-end", default=FIT[1])
    ap.add_argument("--fit-price-end", default=FIT_PRICE_END)
    ap.add_argument("--calibration-start", default=CALIBRATION[0])
    ap.add_argument("--calibration-end", default=CALIBRATION[1])
    ap.add_argument("--calibration-price-end", default=CALIBRATION_PRICE_END)
    ap.add_argument("--holdout-start", default=HOLDOUT[0])
    ap.add_argument("--holdout-end", default=HOLDOUT[1])
    ap.add_argument("--evaluation-label", default="2020–2021 internal holdout")
    ap.add_argument(
        "--exploratory-only", action="store_true",
        help="Run the requested period without authorising formal validation.",
    )
    args = ap.parse_args()
    fit_period = (args.fit_start, args.fit_end)
    calibration_period = (args.calibration_start, args.calibration_end)
    holdout_period = (args.holdout_start, args.holdout_end)
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    detections = payload.get("detections_by_ticker") or {}
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }

    fit_dets, fit_drops = filter_detections(detections, membership, *fit_period)
    fit_rows = build_rows(
        fit_dets, slice_prices(prices_all, fit_period[0], args.fit_price_end),
        with_labels=True, label_mode=args.label_mode,
    )
    model = (fit_quadratic_ridge(fit_rows) if args.model_type == "quadratic"
             else (fit_logistic_ridge(
                       fit_rows, label_threshold=(args.logistic_label_threshold
                                                  if args.logistic_label_threshold is not None
                                                  else (.5 if args.label_mode == "survive20" else .10)),
                   )
                   if args.model_type == "logistic" else fit_ridge(fit_rows)))
    calibration_dets, calibration_drops = filter_detections(
        detections, membership, *calibration_period,
    )
    calibration_rows = build_rows(
        calibration_dets,
        slice_prices(prices_all, calibration_period[0], args.calibration_price_end),
        with_labels=False,
    )
    entry_threshold = threshold_from_rows(calibration_rows, model, args.entry_percentile)
    exit_threshold = threshold_from_rows(calibration_rows, model, 50)

    holdout_dets, holdout_drops = filter_detections(
        detections, membership, *holdout_period,
    )
    holdout_prices = slice_prices(prices_all, *holdout_period)
    holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
    if args.exit_mode == "loss_decay":
        if args.entry_mode != "first":
            ap.error("loss_decay requires first entry mode")
        signals = signals_with_loss_decay(
            holdout_rows, model, entry_threshold, exit_threshold,
        )
        portfolio_exit_rule = "model_decay"
    elif args.entry_mode == "lifecycle":
        if args.exit_mode != "decay":
            ap.error("lifecycle entry mode requires decay exit mode")
        signals = lifecycle_signals_with_decay(
            holdout_rows, model, entry_threshold, exit_threshold,
            cooldown=5, max_cycles=3,
        )
        portfolio_exit_rule = "model_decay"
    elif args.exit_mode == "fixed20":
        signals = signals_from_rows(holdout_rows, model, entry_threshold)
        signals = [{**signal, "model_exit_idx": signal["fill_idx"] + 20} for signal in signals]
        portfolio_exit_rule = "fixed_time"
    else:
        signals = signals_with_decay(
            holdout_rows, model, entry_threshold, exit_threshold,
        )
        portfolio_exit_rule = "model_decay"
    raw_cell = evaluate(
        signals, holdout_prices, args.iterations, exit_rule=portfolio_exit_rule,
        trials_declared=args.trials_declared,
    )
    cell = compact(raw_cell)
    gate = holdout_gate(cell)
    if args.gate_trades != 25:
        gate["checks"].pop("trades>=25")
        gate["checks"][f"trades>={args.gate_trades}"] = (
            cell["trade_stats"]["trades"] >= args.gate_trades
        )
    if args.gate_cagr != 15.0:
        gate["checks"].pop("cagr>=15pct")
        gate["checks"][f"cagr>={args.gate_cagr:g}pct"] = (
            cell["summary"]["cagr_pct"] >= args.gate_cagr
        )
        gate["passed"] = all(gate["checks"].values())
    else:
        gate["passed"] = all(gate["checks"].values())
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": args.family_spec,
        "evaluation_label": args.evaluation_label,
        "exploratory_only": args.exploratory_only,
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "coverage": coverage, "trials_before": args.trials_before,
        "new_multiplicity_units": args.new_multiplicity_units,
        "trials_after": args.trials_declared,
        "periods": {"fit": fit_period, "fit_price_end": args.fit_price_end,
                    "calibration": calibration_period,
                    "calibration_price_end": args.calibration_price_end,
                    "holdout": holdout_period},
        "membership_drops": {
            "fit": fit_drops, "calibration": calibration_drops,
            "holdout": holdout_drops,
        },
        "model": model,
        "label_mode": args.label_mode,
        "exit_mode": args.exit_mode,
        "entry_mode": args.entry_mode,
        "calibration": {
            "rows": len(calibration_rows),
            "setups": len({row['setup_id'] for row in calibration_rows}),
            "entry_percentile": args.entry_percentile, "exit_percentile": 50,
            "entry_threshold": entry_threshold, "exit_threshold": exit_threshold,
            "outcomes_used": False,
        },
        "internal_holdout": {
            "candidate_rows": len(holdout_rows),
            "candidate_setups": len({row['setup_id'] for row in holdout_rows}),
            "selected_signals": len(signals), "cell": cell, "gate": gate,
        },
        "open_formal_validation": gate["passed"] and not args.exploratory_only,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"{args.result_prefix}_{stamp}.json"
    md_path = out / f"{args.result_prefix}_{stamp}.md"
    trades_path = out / f"{args.result_prefix}_{stamp}_holdout_trades.csv"
    daily_path = out / f"{args.result_prefix}_{stamp}_holdout_daily.csv"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(markdown(report))
    if raw_cell["trades"]:
        pd.DataFrame(raw_cell["trades"]).to_csv(trades_path, index=False)
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(daily_path, index=False)
    print(json.dumps({
        "fit_rows": len(fit_rows), "calibration_rows": len(calibration_rows),
        "entry_threshold": entry_threshold, "exit_threshold": exit_threshold,
        "holdout_signals": len(signals), "holdout_summary": cell["summary"],
        "gate": gate,
        "open_formal_validation": gate["passed"] and not args.exploratory_only,
    }, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
