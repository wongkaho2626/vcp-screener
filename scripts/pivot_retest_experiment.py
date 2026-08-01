#!/usr/bin/env python3
"""Evaluate the frozen pivot-retest v2 entry without opening its sealed OOS.

The script runs independent discovery/train and validation portfolios on a
point-in-time S&P 500 universe.  It holds the repository's portfolio sizing,
capacity, costs and exits fixed, and varies only the prespecified entry rule or
cost stress.  The untouched 2000-2005 OOS is deliberately unsupported here;
it requires a separate explicit command after the validation gate passes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, is_member, load_membership
from portfolio_backtest import Config, run_portfolio
from portfolio_robustness import analyze

TRIALS_DECLARED = 195
SEGMENTS = {
    "train": ("2016-07-01", "2021-12-31"),
    "validation": ("2022-01-01", "2026-06-30"),
}


def filter_detections(
    detections: dict, membership: dict, start: str, end: str,
) -> tuple[dict, int]:
    kept: dict[str, list[dict]] = {}
    dropped = 0
    for symbol, rows in detections.items():
        selected = []
        for row in rows:
            as_of = row.get("as_of_date") or ""
            if start <= as_of <= end and is_member(membership, symbol, as_of):
                selected.append(row)
            elif start <= as_of <= end:
                dropped += 1
        if selected:
            kept[symbol] = selected
    return kept, dropped


def slice_prices(prices: dict[str, list[dict]], start: str, end: str) -> dict:
    warmup = str(date.fromisoformat(start) - timedelta(days=730))
    return {
        symbol: [bar for bar in bars if warmup <= bar["date"] <= end]
        for symbol, bars in prices.items()
        if any(warmup <= bar["date"] <= end for bar in bars)
    }


def trade_stats(trades: list[dict]) -> dict:
    values = [float(t["net_return_pct"]) for t in trades]
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    gross_profit = sum(wins)
    gross_loss = -sum(losses)
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = sum(losses) / len(losses) if losses else None
    return {
        "trades": len(values),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "expectancy_pct": sum(values) / len(values) if values else None,
        "win_rate": len(wins) / len(values) if values else None,
        "average_win_pct": avg_win,
        "average_loss_pct": avg_loss,
        "payoff_ratio": avg_win / abs(avg_loss) if avg_win is not None and avg_loss else None,
    }


def trim_stats(trades: list[dict], count: int) -> dict:
    ordered = sorted(trades, key=lambda t: float(t["net_return_pct"]), reverse=True)
    return trade_stats(ordered[count:])


def run_cell(
    detections: dict, prices: dict[str, list[dict]], *, entry_rule: str,
    window: int = 15, delay: int = 0, cost_multiplier: int = 1,
    iterations: int = 1000, exit_rule: str = "baseline",
    trigger_r: float = 1.0, pivot_mode: str = "baseline",
    clv_threshold: float = .60, confirm_window: int = 3,
    required_closes: int = 2, down_close_window: int = 10,
    undercut_window: int = 15, reclaim_window: int = 5,
    inside_day_window: int = 10, reentry_window: int = 20,
    distribution_count: int = 3, distribution_window: int = 15,
    closing_low_lookback: int = 5, closing_low_window: int = 60,
    low_reversal_confirm_window: int = 3,
    pivot_open_window: int = 60,
    controlled_lookback: int = 3,
    controlled_depth_pct: float = 8.0,
    controlled_confirmation: str = "up_close",
    controlled_volume_expansion: bool = False,
    followthrough_early_days: int = 5,
    followthrough_min_gain_pct: float = 2.0,
    followthrough_arm_gain_pct: float = 8.0,
    followthrough_sma_period: int = 10,
) -> dict:
    cfg = Config(
        commission_bps=5.0 * cost_multiplier,
        slippage_bps=5.0 * cost_multiplier,
    )
    params = None
    if entry_rule == "pivot_retest":
        params = {
            "window": window, "mode": pivot_mode,
            "clv_threshold": clv_threshold, "confirm_window": confirm_window,
        }
    elif entry_rule == "detection_entry":
        params = {"delay": delay}
    elif entry_rule == "two_close_breakout":
        params = {"required_closes": required_closes}
    elif entry_rule in ("first_down_close", "down_close_pivot_hold"):
        params = {"window": down_close_window}
    elif entry_rule == "pivot_reclaim":
        params = {
            "undercut_window": undercut_window,
            "reclaim_window": reclaim_window,
        }
    elif entry_rule == "inside_day_breakout":
        params = {"window": inside_day_window}
    elif entry_rule == "down_close_stop_reentry":
        params = {"window": 10, "reentry_window": reentry_window}
    elif entry_rule == "five_day_low_pullback":
        params = {
            "lookback": closing_low_lookback, "window": closing_low_window,
        }
    elif entry_rule == "closing_low_lifecycle":
        params = {
            "lookback": 5, "window": 60, "cooldown": 5, "max_attempts": 3,
        }
    elif entry_rule == "five_day_low_reversal":
        params = {
            "lookback": 5, "window": 60,
            "confirm_window": low_reversal_confirm_window,
        }
    elif entry_rule == "pivot_open_limit":
        params = {"window": pivot_open_window}
    elif entry_rule == "contraction_limit":
        params = {"retracement": .25, "window": 60}
    elif entry_rule == "controlled_pullback_recovery":
        params = {
            "lookback": controlled_lookback,
            "max_depth_pct": controlled_depth_pct,
            "confirmation": controlled_confirmation,
            "volume_expansion": controlled_volume_expansion,
            "window": 60,
        }
    if exit_rule == "breakeven_r":
        exit_params = {"trigger_r": trigger_r}
    elif exit_rule in ("distribution_cluster", "loss_distribution_cluster"):
        exit_params = {
            "event_count": distribution_count,
            "event_window": distribution_window,
        }
    elif exit_rule == "followthrough_sma":
        exit_params = {
            "early_days": followthrough_early_days,
            "min_gain_pct": followthrough_min_gain_pct,
            "arm_gain_pct": followthrough_arm_gain_pct,
            "sma_period": followthrough_sma_period,
        }
    else:
        exit_params = None
    portfolio = run_portfolio(
        detections, prices, cfg, entry_rule=entry_rule, entry_params=params,
        exit_rule=exit_rule,
        exit_params=exit_params,
    )
    curve = portfolio["equity_curve"]
    if len(curve) < 3:
        robustness = None
    else:
        dates = pd.Series([row["date"] for row in curve])
        returns = [float(row["portfolio_return"]) for row in curve]
        robustness = analyze(
            dates, returns, TRIALS_DECLARED, iterations, 10, 20260801, .70,
        )
    return {
        "summary": portfolio["summary"],
        "trade_stats": trade_stats(portfolio["trades"]),
        "drop_top_5": trim_stats(portfolio["trades"], 5),
        "drop_top_10": trim_stats(portfolio["trades"], 10),
        "reentry_trade_stats": trade_stats([
            trade for trade in portfolio["trades"]
            if int(trade.get("attempt", 1)) == 2
        ]),
        "distribution_trade_stats": trade_stats([
            trade for trade in portfolio["trades"]
            if trade.get("exit_reason") in (
                "distribution_cluster", "loss_distribution_cluster",
            )
        ]),
        "robustness": robustness,
        "portfolio": portfolio,
    }


def _tier(value, tiers: list[tuple[float, int]]) -> int:
    if value is None:
        return 0
    for threshold, points in tiers:
        if value > threshold:
            return points
    return 0


def preliminary_score(train: dict, validation: dict, sensitivity: dict) -> dict:
    """Transparent backtest-analyst score used only for the validation gate."""
    r = validation.get("robustness") or {}
    sig = r.get("significance") or {}
    risk_adj = r.get("risk_adjusted") or {}
    risk = r.get("risk") or {}
    stability = r.get("stability") or {}
    ts = validation["trade_stats"]
    train_sr = ((train.get("robustness") or {}).get("risk_adjusted") or {}).get("sharpe")
    val_sr = risk_adj.get("sharpe")
    efficiency = val_sr / train_sr if train_sr not in (None, 0) and val_sr is not None else None

    a = {
        "t_statistic": _tier(sig.get("t_statistic"), [(3, 8), (2, 6), (1.65, 4)]),
        "psr": _tier(sig.get("psr_vs_zero"), [(.95, 7), (.90, 5), (.80, 3)]),
        "dsr": _tier((sig.get("approximate_dsr") or {}).get("probability"), [(.95, 8), (.50, 4)]),
        "sample": 7 if ts["trades"] >= 30 and (r.get("sample") or {}).get("observations", 0) >= 504 else 0,
    }
    cagr = validation["summary"]["cagr_pct"] / 100
    mdd = risk.get("max_drawdown")
    if mdd is None:
        drawdown_points = 0
    elif abs(mdd) < .10:
        drawdown_points = 7
    elif abs(mdd) < .20:
        drawdown_points = 5
    elif abs(mdd) < .30:
        drawdown_points = 3
    else:
        drawdown_points = 0
    b = {
        "sharpe": _tier(val_sr, [(2, 10), (1, 7), (.5, 4)]),
        "sortino_or_calmar": max(
            _tier(risk_adj.get("sortino"), [(2.5, 8), (1.5, 6), (.7, 4)]),
            _tier(risk_adj.get("calmar"), [(2, 8), (1, 6), (.5, 4)]),
        ),
        "drawdown": drawdown_points,
    }
    # Robustness receives full credit only when the lower bootstrap CAGR is
    # positive and all prespecified neighbouring windows retain positive SR.
    boot = (r.get("block_bootstrap") or {}).get("cagr") or {}
    sens_srs = [
        ((cell.get("robustness") or {}).get("risk_adjusted") or {}).get("sharpe")
        for cell in sensitivity.values()
    ]
    smooth = bool(sens_srs) and all(v is not None and v > 0 for v in sens_srs)
    c = {
        "wfa_efficiency": _tier(efficiency, [(.7, 10), (.5, 7), (.3, 4)]),
        "bootstrap": 8 if boot.get("p05", -1) > 0 else (4 if boot.get("median", -1) > 0 else 0),
        "sensitivity": 7 if smooth else (4 if sum(v is not None and v > 0 for v in sens_srs) >= 2 else 0),
    }
    pf = ts.get("profit_factor")
    coherent = (ts.get("expectancy_pct") or 0) > 0 and (ts.get("payoff_ratio") or 0) > 0
    positive_months = stability.get("positive_months")
    d = {
        "profit_factor": _tier(pf, [(2, 7), (1.5, 5), (1.2, 3)]),
        "win_payoff": 6 if coherent else 0,
        "consistency": _tier(positive_months, [(.65, 7), (.55, 5), (.50, 3)]),
    }
    components = {"A": sum(a.values()), "B": sum(b.values()), "C": sum(c.values()), "D": sum(d.values())}
    raw = sum(components.values())
    caps = []
    if ts["trades"] < 30:
        caps.append({"reason": "fewer than 30 validation trades", "cap": 40})
    final = min([raw, *[cap["cap"] for cap in caps]])
    gate = {
        "cagr_ge_20": cagr >= .20,
        "score_gt_80": final > 80,
        "trades_ge_30": ts["trades"] >= 30,
        "positive_ratios": all((risk_adj.get(k) or -math.inf) > 0 for k in ("sharpe", "sortino", "calmar")) and (pf or 0) > 1.2,
        "wfa_efficiency_gt_0_5": efficiency is not None and efficiency > .5 and (train_sr or 0) > 0,
    }
    return {
        "subscores": {"A": a, "B": b, "C": c, "D": d},
        "components": components, "raw_score": raw, "caps": caps,
        "final_score": final, "wfa_efficiency": efficiency,
        "validation_gate": gate, "open_untouched_oos": all(gate.values()),
    }


def compact(cell: dict) -> dict:
    return {k: v for k, v in cell.items() if k != "portfolio"}


def write_daily(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_trades(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def report_markdown(report: dict) -> str:
    score = report["preliminary_score"]
    lines = [
        f"# {report['strategy_name']} Validation Report", "",
        f"Generated: {report['generated_at']}", "",
        f"## Preliminary Backtest Score: {score['final_score']} / 100", "",
        f"Untouched OOS opened: **{'YES' if score['open_untouched_oos'] else 'NO'}**", "",
        "| Segment / cell | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF |", "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for segment in ("train", "validation"):
        cell = report["primary"][segment]
        rb = cell["robustness"]
        ra, risk = rb["risk_adjusted"], rb["risk"]
        lines.append(
            f"| {segment} {report['entry_rule']} | {cell['trade_stats']['trades']} | "
            f"{cell['summary']['cagr_pct']:.2f}% | {ra['sharpe']:.3f} | "
            f"{ra['sortino']:.3f} | {ra['calmar']:.3f} | "
            f"{risk['max_drawdown']:.2%} | {cell['trade_stats']['profit_factor'] or 0:.3f} |"
        )
    lines += ["", "## Score components", "", "| Component | Score | Max |", "|---|---:|---:|",
              f"| A. Statistical validity | {score['components']['A']} | 30 |",
              f"| B. Risk-adjusted performance | {score['components']['B']} | 25 |",
              f"| C. Robustness / validation | {score['components']['C']} | 25 |",
              f"| D. Trade quality / consistency | {score['components']['D']} | 20 |",
              f"| **Raw / final** | **{score['raw_score']} / {score['final_score']}** | 100 |", "",
              "## Validation gate", ""]
    for name, passed in score["validation_gate"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {name}")
    lines += ["", "Per the frozen specification, failure of any gate seals the 2000-2005 untouched OOS and closes this hypothesis.", ""]
    return "\n".join(lines)


def main() -> None:
    global TRIALS_DECLARED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/pivot_retest_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    ap.add_argument(
        "--entry-rule", choices=(
            "pivot_retest", "detection_entry", "two_close_breakout",
            "first_down_close",
            "down_close_pivot_hold",
            "pivot_reclaim",
            "inside_day_breakout",
            "down_close_stop_reentry",
            "five_day_low_pullback",
            "five_day_low_reversal",
            "pivot_open_limit",
            "controlled_pullback_recovery",
            "closing_low_lifecycle",
            "contraction_limit",
        ),
        default="pivot_retest",
    )
    ap.add_argument("--strategy-name", default="Pivot-Retest v2")
    ap.add_argument("--frozen-spec", default="backtests/pivot_retest_v2/frozen_spec.md")
    ap.add_argument("--trials", type=int, default=TRIALS_DECLARED)
    ap.add_argument(
        "--exit-rule", choices=(
            "baseline", "breakeven_r", "pivot_failure", "distribution_cluster",
            "loss_distribution_cluster",
            "followthrough_sma",
        ),
        default="baseline",
    )
    args = ap.parse_args()

    TRIALS_DECLARED = args.trials

    payload = json.loads(Path(args.backtest_json).read_text())
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("coverage/benchmark gate failed; validation is not scoreable")
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices = {
        row["symbol"]: list(reversed(client.get_historical_prices(row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    detections = payload.get("detections_by_ticker") or {}
    primary, baseline, costs, sensitivity, membership_drops = {}, {}, {}, {}, {}
    raw_primary = {}
    for name, (start, end) in SEGMENTS.items():
        dets, dropped = filter_detections(detections, membership, start, end)
        membership_drops[name] = dropped
        px = slice_prices(prices, start, end)
        raw_primary[name] = run_cell(
            dets, px, entry_rule=args.entry_rule, exit_rule=args.exit_rule,
            iterations=args.iterations,
        )
        primary[name] = compact(raw_primary[name])
        baseline_entry = args.entry_rule if args.exit_rule != "baseline" else "pullback"
        baseline[name] = compact(run_cell(
            dets, px, entry_rule=baseline_entry, exit_rule="baseline",
            iterations=args.iterations,
        ))
        costs[name] = {
            str(mult): compact(run_cell(
                dets, px, entry_rule=args.entry_rule, exit_rule=args.exit_rule,
                cost_multiplier=mult, iterations=max(200, args.iterations // 5),
            ))
            for mult in (2, 5, 10)
        }
        if args.exit_rule == "breakeven_r":
            sensitivity[name] = {
                f"trigger_{trigger:g}R": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule, exit_rule=args.exit_rule,
                    trigger_r=trigger, iterations=max(200, args.iterations // 5),
                ))
                for trigger in (.75, 1.25)
            }
        elif args.exit_rule in (
            "distribution_cluster", "loss_distribution_cluster",
        ):
            sensitivity[name] = {
                **{
                    f"count_{count}_window_15": compact(run_cell(
                        dets, px, entry_rule=args.entry_rule,
                        exit_rule=args.exit_rule, distribution_count=count,
                        distribution_window=15,
                        iterations=max(200, args.iterations // 5),
                    ))
                    for count in (2, 4)
                },
                **{
                    f"count_3_window_{window}": compact(run_cell(
                        dets, px, entry_rule=args.entry_rule,
                        exit_rule=args.exit_rule, distribution_count=3,
                        distribution_window=window,
                        iterations=max(200, args.iterations // 5),
                    ))
                    for window in (10, 20)
                },
            }
        elif args.entry_rule == "pivot_retest":
            sensitivity[name] = {
                str(window): compact(run_cell(dets, px, entry_rule=args.entry_rule, window=window, iterations=max(200, args.iterations // 5)))
                for window in (10, 20)
            }
        elif args.entry_rule == "two_close_breakout":
            sensitivity[name] = {
                f"{required}_closes": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    required_closes=required,
                    iterations=max(200, args.iterations // 5),
                ))
                for required in (1, 3)
            }
        elif args.entry_rule in ("first_down_close", "down_close_pivot_hold"):
            sensitivity[name] = {
                f"window_{wait}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    down_close_window=wait,
                    iterations=max(200, args.iterations // 5),
                ))
                for wait in (5, 15)
            }
        elif args.entry_rule == "pivot_reclaim":
            sensitivity[name] = {
                f"undercut_{under}_reclaim_{reclaim}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    undercut_window=under, reclaim_window=reclaim,
                    iterations=max(200, args.iterations // 5),
                ))
                for under, reclaim in ((10, 3), (20, 7))
            }
        elif args.entry_rule == "inside_day_breakout":
            sensitivity[name] = {
                f"window_{wait}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    inside_day_window=wait,
                    iterations=max(200, args.iterations // 5),
                ))
                for wait in (5, 15)
            }
        elif args.entry_rule == "down_close_stop_reentry":
            sensitivity[name] = {
                f"reentry_window_{wait}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    reentry_window=wait,
                    iterations=max(200, args.iterations // 5),
                ))
                for wait in (10, 30)
            }
        elif args.entry_rule == "five_day_low_pullback":
            sensitivity[name] = {
                f"lookback_{lookback}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    closing_low_lookback=lookback,
                    iterations=max(200, args.iterations // 5),
                ))
                for lookback in (3, 10)
            }
        elif args.entry_rule == "five_day_low_reversal":
            sensitivity[name] = {
                f"confirm_window_{window}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    low_reversal_confirm_window=window,
                    iterations=max(200, args.iterations // 5),
                ))
                for window in (2, 5)
            }
        elif args.entry_rule == "pivot_open_limit":
            sensitivity[name] = {
                f"order_lifetime_{window}": compact(run_cell(
                    dets, px, entry_rule=args.entry_rule,
                    pivot_open_window=window,
                    iterations=max(200, args.iterations // 5),
                ))
                for window in (30, 90)
            }
        else:
            sensitivity[name] = {
                "delay_1": compact(run_cell(dets, px, entry_rule=args.entry_rule, delay=1, iterations=max(200, args.iterations // 5)))
            }
    score_sensitivity = {"primary": primary["validation"], **sensitivity["validation"]}
    score = preliminary_score(primary["train"], primary["validation"], score_sensitivity)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_name": args.strategy_name,
        "entry_rule": args.entry_rule,
        "exit_rule": args.exit_rule,
        "frozen_spec": args.frozen_spec,
        "data": {"price_csv": args.price_csv, "coverage": coverage, "membership_drops": membership_drops},
        "segments": SEGMENTS, "trials_declared": TRIALS_DECLARED,
        "primary": primary, "baseline": baseline,
        "cost_stress": costs, "window_sensitivity": sensitivity,
        "preliminary_score": score,
        "untouched_oos": {"period": ["2000-01-01", "2005-12-31"], "opened": False},
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    slug = f"{args.entry_rule}_{args.exit_rule}"
    prefix = out / f"{slug}_validation_{stamp}"
    prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    prefix.with_suffix(".md").write_text(report_markdown(report))
    for name, cell in raw_primary.items():
        write_daily(out / f"{slug}_{name}_daily.csv", cell["portfolio"]["equity_curve"])
        write_trades(out / f"{slug}_{name}_trades.csv", cell["portfolio"]["trades"])
    print(json.dumps({"score": score, "validation": primary["validation"]["summary"]}, indent=2))
    print(prefix.with_suffix(".json"))
    print(prefix.with_suffix(".md"))


if __name__ == "__main__":
    main()
