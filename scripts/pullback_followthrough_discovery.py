#!/usr/bin/env python3
"""Prespecified train-only discovery for controlled pullback/follow-through."""

from __future__ import annotations

import argparse
import itertools
import json
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import compact, filter_detections, run_cell, slice_prices

DISCOVERY = ("2016-07-01", "2019-12-31")
INTERNAL_HOLDOUT = ("2020-01-01", "2021-12-31")
TRIALS_BEFORE = 215
TRIALS_AFTER = 234


def entry_variants() -> list[dict]:
    """Return all 16 cells in the prespecified simplicity order."""
    return [
        {
            "lookback": lookback,
            "max_depth_pct": depth,
            "confirmation": confirmation,
            "volume_expansion": volume,
        }
        for lookback, depth, confirmation, volume in itertools.product(
            (3, 5), (8.0, 4.0), ("up_close", "prior_high"), (False, True),
        )
    ]


EXIT_VARIANTS = [
    {
        "name": "ft5_sma10", "early_days": 5, "min_gain_pct": 2.0,
        "arm_gain_pct": 8.0, "sma_period": 10,
    },
    {
        "name": "ft5_sma20", "early_days": 5, "min_gain_pct": 2.0,
        "arm_gain_pct": 8.0, "sma_period": 20,
    },
    {
        "name": "ft10_sma20", "early_days": 10, "min_gain_pct": 3.0,
        "arm_gain_pct": 10.0, "sma_period": 20,
    },
]


def entry_name(params: dict) -> str:
    confirm = "up" if params["confirmation"] == "up_close" else "high"
    volume = "vol" if params["volume_expansion"] else "novol"
    return f"lb{params['lookback']}_d{int(params['max_depth_pct'])}_{confirm}_{volume}"


def _risk(cell: dict) -> tuple[float | None, float | None]:
    robustness = cell.get("robustness") or {}
    adjusted = robustness.get("risk_adjusted") or {}
    risk = robustness.get("risk") or {}
    return adjusted.get("sharpe"), adjusted.get("calmar")


def stage_a_assessment(cell: dict) -> dict:
    stats = cell["trade_stats"]
    mdd = float(cell["summary"]["max_drawdown_pct"])
    checks = {
        "trades>=35": stats["trades"] >= 35,
        "cagr>0": cell["summary"]["cagr_pct"] > 0,
        "pf>1.10": (stats.get("profit_factor") or 0) > 1.10,
        "drop_top_5_expectancy>0": (cell["drop_top_5"].get("expectancy_pct") or 0) > 0,
        "mdd>-15pct": mdd > -15,
    }
    sharpe, calmar = _risk(cell)
    return {
        "eligible": all(checks.values()), "checks": checks,
        "sharpe": sharpe, "calmar": calmar,
    }


def select_stage_a(cells: dict[str, dict], order: list[str]) -> dict:
    assessed = {name: stage_a_assessment(cells[name]) for name in order}
    eligible = [name for name in order if assessed[name]["eligible"]]
    if not eligible:
        return {"selected": None, "assessment": assessed}
    best_calmar = max(float(assessed[name]["calmar"] or float("-inf")) for name in eligible)
    tied = [
        name for name in eligible
        if best_calmar - float(assessed[name]["calmar"] or float("-inf")) <= .05
    ]
    return {"selected": min(tied, key=order.index), "assessment": assessed}


def stage_b_assessment(cell: dict, baseline: dict) -> dict:
    stats = cell["trade_stats"]
    sharpe, calmar = _risk(cell)
    baseline_sharpe, _ = _risk(baseline)
    checks = {
        "trades>=35": stats["trades"] >= 35,
        "cagr>0": cell["summary"]["cagr_pct"] > 0,
        "pf>1.20": (stats.get("profit_factor") or 0) > 1.20,
        "drop_top_5_expectancy>0": (cell["drop_top_5"].get("expectancy_pct") or 0) > 0,
        "mdd>-15pct": cell["summary"]["max_drawdown_pct"] > -15,
        "sharpe>entry_baseline": (
            sharpe is not None and baseline_sharpe is not None and sharpe > baseline_sharpe
        ),
        "cagr>entry_baseline": cell["summary"]["cagr_pct"] > baseline["summary"]["cagr_pct"],
    }
    return {
        "eligible": all(checks.values()), "checks": checks,
        "sharpe": sharpe, "calmar": calmar,
    }


def select_stage_b(cells: dict[str, dict], baseline: dict) -> dict:
    order = [row["name"] for row in EXIT_VARIANTS]
    assessed = {name: stage_b_assessment(cells[name], baseline) for name in order}
    eligible = [name for name in order if assessed[name]["eligible"]]
    if not eligible:
        return {"selected": None, "assessment": assessed}
    best_calmar = max(float(assessed[name]["calmar"] or float("-inf")) for name in eligible)
    tied = [
        name for name in eligible
        if best_calmar - float(assessed[name]["calmar"] or float("-inf")) <= .05
    ]
    return {"selected": min(tied, key=order.index), "assessment": assessed}


def holdout_gate(cell: dict) -> dict:
    stats = cell["trade_stats"]
    sharpe, _ = _risk(cell)
    checks = {
        "trades>=25": stats["trades"] >= 25,
        "cagr>=15pct": cell["summary"]["cagr_pct"] >= 15,
        "sharpe>=0.75": sharpe is not None and sharpe >= .75,
        "pf>1.20": (stats.get("profit_factor") or 0) > 1.20,
        "mdd>-15pct": cell["summary"]["max_drawdown_pct"] > -15,
        "drop_top_5_expectancy>0": (cell["drop_top_5"].get("expectancy_pct") or 0) > 0,
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_strategy(detections: dict, prices: dict, entry: dict, exit_spec: dict | None,
                 iterations: int) -> dict:
    kwargs = {
        "entry_rule": "controlled_pullback_recovery",
        "controlled_lookback": entry["lookback"],
        "controlled_depth_pct": entry["max_depth_pct"],
        "controlled_confirmation": entry["confirmation"],
        "controlled_volume_expansion": entry["volume_expansion"],
        "iterations": iterations,
    }
    if exit_spec:
        kwargs.update({
            "exit_rule": "followthrough_sma",
            "followthrough_early_days": exit_spec["early_days"],
            "followthrough_min_gain_pct": exit_spec["min_gain_pct"],
            "followthrough_arm_gain_pct": exit_spec["arm_gain_pct"],
            "followthrough_sma_period": exit_spec["sma_period"],
        })
    return compact(run_cell(detections, prices, **kwargs))


def markdown(report: dict) -> str:
    lines = [
        "# Controlled Pullback / Follow-Through — Train-Only Discovery", "",
        f"Generated: {report['generated_at']}", "",
        "Formal validation accessed: **NO**", "",
        "## Stage A — entry selection", "",
        "| Cell | Trades | CAGR | Sharpe | Calmar | PF | Trim-5 expectancy | Eligible |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name in report["stage_a"]["order"]:
        cell = report["stage_a"]["cells"][name]
        row = report["stage_a"]["selection"]["assessment"][name]
        lines.append(
            f"| {name} | {cell['trade_stats']['trades']} | {cell['summary']['cagr_pct']:.2f}% | "
            f"{(row['sharpe'] or 0):.3f} | {(row['calmar'] or 0):.3f} | "
            f"{(cell['trade_stats']['profit_factor'] or 0):.3f} | "
            f"{(cell['drop_top_5']['expectancy_pct'] or 0):.2f}% | "
            f"{'yes' if row['eligible'] else 'no'} |"
        )
    selected_a = report["stage_a"]["selection"]["selected"]
    lines += ["", f"Selected entry: **{selected_a or 'NONE'}**", ""]
    if selected_a:
        lines += [
            "## Stage B — managed exit selection", "",
            "| Exit | Trades | CAGR | Sharpe | Calmar | PF | Trim-5 expectancy | Eligible |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        baseline = report["stage_b"]["baseline"]
        bs, bc = _risk(baseline)
        lines.append(
            f"| baseline | {baseline['trade_stats']['trades']} | {baseline['summary']['cagr_pct']:.2f}% | "
            f"{(bs or 0):.3f} | {(bc or 0):.3f} | {(baseline['trade_stats']['profit_factor'] or 0):.3f} | "
            f"{(baseline['drop_top_5']['expectancy_pct'] or 0):.2f}% | reference |"
        )
        for name, cell in report["stage_b"]["cells"].items():
            row = report["stage_b"]["selection"]["assessment"][name]
            lines.append(
                f"| {name} | {cell['trade_stats']['trades']} | {cell['summary']['cagr_pct']:.2f}% | "
                f"{(row['sharpe'] or 0):.3f} | {(row['calmar'] or 0):.3f} | "
                f"{(cell['trade_stats']['profit_factor'] or 0):.3f} | "
                f"{(cell['drop_top_5']['expectancy_pct'] or 0):.2f}% | "
                f"{'yes' if row['eligible'] else 'no'} |"
            )
        selected_b = report["stage_b"]["selection"]["selected"]
        lines += ["", f"Selected managed exit: **{selected_b or 'NONE'}**", ""]
    if report.get("internal_holdout"):
        holdout = report["internal_holdout"]
        cell = holdout["cell"]
        sharpe, calmar = _risk(cell)
        lines += [
            "## 2020–2021 internal holdout", "",
            f"Trades {cell['trade_stats']['trades']}; net CAGR {cell['summary']['cagr_pct']:.2f}%; "
            f"Sharpe {(sharpe or 0):.3f}; Calmar {(calmar or 0):.3f}; "
            f"PF {(cell['trade_stats']['profit_factor'] or 0):.3f}; "
            f"MDD {cell['summary']['max_drawdown_pct']:.2f}%.", "",
            f"Formal-validation gate: **{'PASS' if holdout['gate']['passed'] else 'FAIL'}**", "",
        ]
    else:
        lines += ["## Result", "", "No complete discovery specification passed; family closed.", ""]
    lines.append("The 2022–2023 formal validation and untouched OOS were not accessed.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/pullback_followthrough_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }

    discovery_dets, discovery_drops = filter_detections(
        payload.get("detections_by_ticker") or {}, membership, *DISCOVERY,
    )
    discovery_prices = slice_prices(prices_all, *DISCOVERY)
    variants = entry_variants()
    order = [entry_name(row) for row in variants]
    stage_a_cells = {
        entry_name(entry): run_strategy(
            discovery_dets, discovery_prices, entry, None, args.iterations,
        )
        for entry in variants
    }
    stage_a_selection = select_stage_a(stage_a_cells, order)

    stage_b_cells: dict[str, dict] = {}
    stage_b_selection = {"selected": None, "assessment": {}}
    selected_entry = None
    if stage_a_selection["selected"]:
        selected_entry = variants[order.index(stage_a_selection["selected"])]
        stage_b_cells = {
            exit_spec["name"]: run_strategy(
                discovery_dets, discovery_prices, selected_entry,
                exit_spec, args.iterations,
            )
            for exit_spec in EXIT_VARIANTS
        }
        stage_b_selection = select_stage_b(
            stage_b_cells, stage_a_cells[stage_a_selection["selected"]],
        )

    internal_holdout = None
    if selected_entry and stage_b_selection["selected"]:
        selected_exit = next(
            row for row in EXIT_VARIANTS
            if row["name"] == stage_b_selection["selected"]
        )
        holdout_dets, holdout_drops = filter_detections(
            payload.get("detections_by_ticker") or {}, membership, *INTERNAL_HOLDOUT,
        )
        holdout_cell = run_strategy(
            holdout_dets, slice_prices(prices_all, *INTERNAL_HOLDOUT),
            selected_entry, selected_exit, args.iterations,
        )
        internal_holdout = {
            "period": INTERNAL_HOLDOUT, "membership_drops": holdout_drops,
            "entry": selected_entry, "exit": selected_exit,
            "cell": holdout_cell, "gate": holdout_gate(holdout_cell),
        }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/pullback_followthrough_v2/family_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "coverage": coverage,
        "trials_before": TRIALS_BEFORE,
        "new_cells": 19,
        "trials_after": TRIALS_AFTER,
        "stage_a": {
            "period": DISCOVERY, "membership_drops": discovery_drops,
            "order": order, "parameters": dict(zip(order, variants)),
            "cells": stage_a_cells, "selection": stage_a_selection,
        },
        "stage_b": {
            "baseline": (
                stage_a_cells[stage_a_selection["selected"]]
                if stage_a_selection["selected"] else None
            ),
            "cells": stage_b_cells, "selection": stage_b_selection,
        },
        "internal_holdout": internal_holdout,
        "open_formal_validation": bool(
            internal_holdout and internal_holdout["gate"]["passed"]
        ),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"pullback_followthrough_discovery_{stamp}.json"
    md_path = out / f"pullback_followthrough_discovery_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(markdown(report))
    print(json.dumps({
        "stage_a_selected": stage_a_selection["selected"],
        "stage_b_selected": stage_b_selection["selected"],
        "open_formal_validation": report["open_formal_validation"],
        "internal_holdout_gate": (
            internal_holdout["gate"] if internal_holdout else None
        ),
    }, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
