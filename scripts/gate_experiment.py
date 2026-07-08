#!/usr/bin/env python3
"""Detection-gate experiment (backtest-analyst structural recommendation 1).

Tests whether tightening *which* detections become trades — via a hard
Minervini trend-template gate, a universe-relative RS-rank percentile, a
composite-score cut, and a volume dry-up floor — produces a real, *out-of-
sample* excess over SPY, rather than an in-sample artifact of threshold
mining.

Fully offline: reads the detection set (``vcp_backtest_*.json``) for the gate
features and the accepted-trade log (``vcp_trades_*.json``) for realised
returns, and joins them on ``(symbol, as_of_date)``. No network.

Method (guards against the overfitting it is meant to detect):
- Split trades by entry year into TRAIN (< split-year) and OOS (>= split-year).
- Sweep a deliberately small, principled threshold grid on TRAIN only.
- Select the best gate by TRAIN excess t-stat, subject to a minimum trade
  count, then evaluate it exactly ONCE on OOS.
- Also report two a-priori (untuned) gates — trend-pass-only and
  trend-pass + RS>=70 — so a regime-lucky OOS number can be spotted by its
  train/OOS sign flip.

Usage:
    python3 scripts/gate_experiment.py \
        backtests/vcp_backtest_YYYY.json \
        backtests/vcp_trades_YYYY.json
"""

from __future__ import annotations

import argparse
import bisect
import collections
import itertools
import json
import math
import os
import statistics as st
import sys
from datetime import datetime

# Deliberately small grid — every extra combo is another multiple-testing
# trial that inflates the best in-sample t-stat.
RS_OPTS = (0, 50, 70)
SCORE_OPTS = (0, 60, 65)
VOL_OPTS = (0, 50)
TREND_OPTS = (False, True)


def parse_arguments() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="VCP detection-gate experiment (rec 1)")
    ap.add_argument("backtest_json", help="vcp_backtest_*.json (detection features)")
    ap.add_argument("trades_json", help="vcp_trades_*.json (realised trades)")
    ap.add_argument(
        "--split-year",
        type=int,
        default=2022,
        help="Entry years < this are TRAIN, >= this are OOS (default: 2022)",
    )
    ap.add_argument(
        "--min-train-trades",
        type=int,
        default=25,
        help="Minimum TRAIN trades for a gate to be eligible (default: 25)",
    )
    ap.add_argument(
        "--folds",
        type=int,
        default=3,
        help="Rolling-origin walk-forward folds (default: 3; 0/1 disables)",
    )
    ap.add_argument("--output-dir", default="backtests/", help="Report directory")
    args = ap.parse_args()
    if not (1990 <= args.split_year <= 2100):
        ap.error("--split-year out of range")
    if args.min_train_trades < 2:
        ap.error("--min-train-trades must be >= 2")
    if not (0 <= args.folds <= 12):
        ap.error("--folds must be 0-12")
    return args


def build_rs_rank(detections_by_ticker: dict) -> dict[tuple[str, str], float]:
    """Universe-relative RS-rank percentile per as-of date.

    For each ``as_of_date`` rank every detection's ``weighted_rs`` against the
    whole scanned universe that date, returning a 0-100 percentile keyed by
    ``(symbol, as_of_date)``. Pure function.
    """
    by_date: dict[str, list[tuple[str, float]]] = collections.defaultdict(list)
    for sym, dets in detections_by_ticker.items():
        for det in dets:
            aod = det.get("as_of_date")
            rs = (det.get("relative_strength") or {}).get("weighted_rs")
            if aod is not None and rs is not None:
                by_date[aod].append((sym, rs))

    ranks: dict[tuple[str, str], float] = {}
    for date, rows in by_date.items():
        sorted_vals = sorted(rs for _, rs in rows)
        denom = max(len(sorted_vals) - 1, 1)
        for sym, rs in rows:
            pct = bisect.bisect_left(sorted_vals, rs) / denom * 100
            ranks[(sym, date)] = round(pct, 1)
    return ranks


def enrich_trades(trades: list[dict], detections_by_ticker: dict) -> list[dict]:
    """Attach trend-pass, RS-rank percentile and volume score to each trade."""
    det_lookup = {
        (sym, det.get("as_of_date")): det
        for sym, dets in detections_by_ticker.items()
        for det in dets
    }
    rs_rank = build_rs_rank(detections_by_ticker)

    enriched = []
    for t in trades:
        key = (t["symbol"], t["as_of_date"])
        det = det_lookup.get(key)
        if det is None:
            continue
        tt = det.get("trend_template") or {}
        vp = det.get("volume_pattern") or {}
        enriched.append(
            {
                **t,
                "trend_passed": bool(tt.get("passed")),
                "rs_rank_pct": rs_rank.get(key),
                "volume_score": vp.get("score"),
            }
        )
    return enriched


def _excess(sub: list[dict]) -> list[float]:
    return [t["excess_vs_spy_pct"] for t in sub if t.get("excess_vs_spy_pct") is not None]


def stats(sub: list[dict]) -> dict:
    """Excess-over-SPY summary for a trade subset. Pure function."""
    exc = _excess(sub)
    n = len(exc)
    if n < 2:
        return {"n": n, "mean": None, "t": None, "win_pct": None}
    mean = st.fmean(exc)
    sd = st.stdev(exc)
    t = mean / (sd / math.sqrt(n)) if sd > 0 else None
    return {
        "n": n,
        "mean": round(mean, 2),
        "t": round(t, 2) if t is not None else None,
        "win_pct": round(sum(1 for x in exc if x > 0) / n * 100, 1),
    }


def apply_gate(
    sub: list[dict], trend: bool, rs: float, score: float, vol: float
) -> list[dict]:
    """Return trades passing the gate. Pure function (no mutation)."""
    out = []
    for t in sub:
        if trend and not t["trend_passed"]:
            continue
        rr = t["rs_rank_pct"]
        if rr is None or rr < rs:
            continue
        if (t["composite_score"] or 0) < score:
            continue
        if (t["volume_score"] or 0) < vol:
            continue
        out.append(t)
    return out


def sweep_train(train: list[dict], min_train: int) -> list[tuple[tuple, dict]]:
    """All eligible gates ranked by TRAIN excess t-stat (desc). Pure function."""
    results = []
    for trend, rs, score, vol in itertools.product(
        TREND_OPTS, RS_OPTS, SCORE_OPTS, VOL_OPTS
    ):
        s = stats(apply_gate(train, trend, rs, score, vol))
        if s["n"] >= min_train and s["t"] is not None:
            results.append(((trend, rs, score, vol), s))
    results.sort(key=lambda x: -(x[1]["t"] if x[1]["t"] is not None else -9.9))
    return results


# Fixed, a-priori gates evaluated identically across every walk-forward fold.
# No per-fold tuning — a rule that survives here is not a selection artifact.
WF_CANDIDATES = (
    ("none", (False, 0, 0, 0)),
    ("trend-pass", (True, 0, 0, 0)),
    ("trend-pass + RS-rank>=70", (True, 70, 0, 0)),
)


def walk_forward(enriched: list[dict], folds: int, min_train: int) -> dict:
    """Rolling-origin walk-forward over entry-date-sorted trades. Pure function.

    Splits trades into ``folds + 1`` sequential equal-count blocks; block 0 is
    the initial training anchor. For each subsequent block (an OOS fold), the
    train set is every earlier block pooled. Reports, per fold and pooled across
    all folds, the OOS excess for each fixed candidate gate plus the gate
    selected on that fold's train set.
    """
    ordered = sorted(enriched, key=lambda t: t["entry_date"])
    n = len(ordered)
    blocks = folds + 1
    if n < blocks * 2:
        return {"enabled": False, "reason": f"too few trades ({n}) for {folds} folds"}

    edges = [round(i * n / blocks) for i in range(blocks + 1)]
    segments = [ordered[edges[i]:edges[i + 1]] for i in range(blocks)]

    pooled: dict[str, list[dict]] = {name: [] for name, _ in WF_CANDIDATES}
    pooled["train-selected"] = []
    fold_rows = []
    for i in range(1, blocks):
        train = [t for seg in segments[:i] for t in seg]
        test = segments[i]
        row = {
            "fold": i,
            "train_n": len(train),
            "oos_from": test[0]["entry_date"],
            "oos_to": test[-1]["entry_date"],
            "candidates": {},
        }
        for name, combo in WF_CANDIDATES:
            picked = apply_gate(test, *combo)
            pooled[name].extend(picked)
            row["candidates"][name] = stats(picked)
        sweep = sweep_train(train, min_train)
        if sweep:
            combo = sweep[0][0]
            picked = apply_gate(test, *combo)
            pooled["train-selected"].extend(picked)
            row["candidates"]["train-selected"] = {
                **stats(picked),
                "gate": _gate_label(combo),
            }
        else:
            row["candidates"]["train-selected"] = {"n": 0, "mean": None, "t": None,
                                                    "win_pct": None, "gate": "(none eligible)"}
        fold_rows.append(row)

    pooled_stats = {name: stats(sub) for name, sub in pooled.items()}
    return {"enabled": True, "folds": folds, "fold_rows": fold_rows,
            "pooled_oos": pooled_stats}


def _gate_label(combo: tuple) -> str:
    trend, rs, score, vol = combo
    parts = []
    if trend:
        parts.append("trend-pass")
    if rs > 0:
        parts.append(f"RS-rank>={rs:g}")
    if score > 0:
        parts.append(f"score>={score:g}")
    if vol > 0:
        parts.append(f"vol>={vol:g}")
    return " + ".join(parts) if parts else "(no filter)"


def _eval_gate(combo: tuple, train, oos, full) -> dict:
    """Train/OOS/full stats for one gate. Pure function."""
    return {
        "combo": list(combo),
        "label": _gate_label(combo),
        "train": stats(apply_gate(train, *combo)),
        "oos": stats(apply_gate(oos, *combo)),
        "full": stats(apply_gate(full, *combo)),
    }


def run(args: argparse.Namespace) -> None:
    detections = json.load(open(args.backtest_json)).get("detections_by_ticker") or {}
    if not detections:
        print("ERROR: backtest JSON has no detections_by_ticker", file=sys.stderr)
        sys.exit(1)
    trades = json.load(open(args.trades_json)).get("trades") or []
    if not trades:
        print("ERROR: trades JSON has no trades", file=sys.stderr)
        sys.exit(1)

    enriched = enrich_trades(trades, detections)
    if not enriched:
        print("ERROR: no trades could be joined to detections", file=sys.stderr)
        sys.exit(1)

    split = args.split_year
    train = [t for t in enriched if int(t["entry_date"][:4]) < split]
    oos = [t for t in enriched if int(t["entry_date"][:4]) >= split]

    baseline = {
        "train": stats(train),
        "oos": stats(oos),
        "full": stats(enriched),
    }
    sweep = sweep_train(train, args.min_train_trades)
    selected = _eval_gate(sweep[0][0], train, oos, enriched) if sweep else None
    apriori = [
        _eval_gate(combo, train, oos, enriched)
        for combo in ((True, 0, 0, 0), (True, 70, 0, 0))
    ]
    wf = (
        walk_forward(enriched, args.folds, args.min_train_trades)
        if args.folds >= 2
        else {"enabled": False, "reason": "walk-forward disabled (--folds < 2)"}
    )

    trend_frac = sum(1 for t in enriched if t["trend_passed"]) / len(enriched) * 100
    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_json": os.path.basename(args.backtest_json),
        "trades_json": os.path.basename(args.trades_json),
        "split_year": split,
        "n_enriched": len(enriched),
        "n_train": len(train),
        "n_oos": len(oos),
        "trend_pass_fraction_pct": round(trend_frac, 1),
        "n_train_combos_eligible": len(sweep),
        "folds": args.folds,
    }
    report = {
        "metadata": metadata,
        "baseline": baseline,
        "selected_gate": selected,
        "apriori_gates": apriori,
        "walk_forward": wf,
        "train_sweep_top": [{"gate": _gate_label(c), **s} for c, s in sweep[:8]],
    }

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"vcp_gate_experiment_{ts}.json")
    md_path = os.path.join(args.output_dir, f"vcp_gate_experiment_{ts}.md")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    with open(md_path, "w") as f:
        f.write(_render_markdown(report))

    _print_console(report, json_path, md_path)


def _fmt(s: dict) -> str:
    if s["mean"] is None:
        return f"n={s['n']} (too few)"
    return f"n={s['n']} mean={s['mean']}% t={s['t']} win={s['win_pct']}%"


def _row(label: str, g: dict) -> str:
    def cell(s):
        return (
            f"{s['mean']}% ({s['t']}), n={s['n']}"
            if s["mean"] is not None
            else f"n={s['n']}"
        )

    return f"| {label} | {cell(g['train'])} | {cell(g['oos'])} | {cell(g['full'])} |"


def _render_markdown(report: dict) -> str:
    m = report["metadata"]
    lines = [
        "# VCP Detection-Gate Experiment",
        "",
        f"Generated: {m['generated_at']}",
        f"Detections: {m['backtest_json']} | Trades: {m['trades_json']}",
        "",
        f"- Split year: **{m['split_year']}** — TRAIN < {m['split_year']} "
        f"(n={m['n_train']}), OOS >= {m['split_year']} (n={m['n_oos']})",
        f"- Trades passing full Minervini trend template: "
        f"**{m['trend_pass_fraction_pct']}%** of {m['n_enriched']}",
        f"- Eligible gates in train sweep (>= min trades): "
        f"{m['n_train_combos_eligible']}",
        "",
        "Primary metric: **excess over SPY** (same holding windows). A gate is "
        "credible only if TRAIN and OOS agree in sign and OOS reaches "
        "significance (|t| > 1.65). A train/OOS sign flip = regime luck, not edge.",
        "",
        "## Gates — train / OOS / full",
        "",
        "| Gate | TRAIN excess (t) | OOS excess (t) | Full (t) |",
        "|---|---|---|---|",
        _row(
            "None (baseline)",
            {
                "train": report["baseline"]["train"],
                "oos": report["baseline"]["oos"],
                "full": report["baseline"]["full"],
            },
        ),
    ]
    if report["selected_gate"]:
        lines.append(
            _row(
                f"Train-selected: {report['selected_gate']['label']}",
                report["selected_gate"],
            )
        )
    for g in report["apriori_gates"]:
        lines.append(_row(f"A-priori: {g['label']}", g))
    lines += _render_walk_forward(report.get("walk_forward") or {})
    lines += [
        "",
        "## Train sweep — top gates by in-sample excess t",
        "",
        "| Gate | n | Mean excess | t | Win% |",
        "|---|---|---|---|---|",
    ]
    for r in report["train_sweep_top"]:
        lines.append(
            f"| {r['gate']} | {r['n']} | {r['mean']}% | {r['t']} | {r['win_pct']}% |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- RS-rank is a universe-relative percentile: each detection's",
        "  `weighted_rs` ranked against all detections on the same as-of date.",
        "- The train sweep is a multiple-testing exercise; the best in-sample t",
        "  is upward-biased. Trust the OOS column, not the train column.",
        "- Small subsets (n < 30) are underpowered — treat their t-stats as noisy.",
        "",
    ]
    return "\n".join(lines)


def _render_walk_forward(wf: dict) -> list[str]:
    if not wf.get("enabled"):
        return ["", "## Walk-forward", "", f"_Skipped: {wf.get('reason', 'n/a')}_"]

    def cell(s):
        return (
            f"{s['mean']}% ({s['t']}), n={s['n']}"
            if s.get("mean") is not None
            else f"n={s.get('n', 0)}"
        )

    names = [n for n, _ in WF_CANDIDATES] + ["train-selected"]
    lines = [
        "",
        f"## Walk-forward ({wf['folds']} rolling-origin folds)",
        "",
        "Each fold trains on all earlier trades and tests on the next block. A "
        "gate with a real edge should hold its sign and rough magnitude across "
        "folds and in the pooled-OOS row; a rule that swings sign fold-to-fold "
        "is riding regimes.",
        "",
        "| Fold | OOS window | " + " | ".join(names) + " |",
        "|---|---|" + "|".join(["---"] * len(names)) + "|",
    ]
    for row in wf["fold_rows"]:
        cells = [cell(row["candidates"][n]) for n in names]
        lines.append(
            f"| {row['fold']} | {row['oos_from']}→{row['oos_to']} | "
            + " | ".join(cells)
            + " |"
        )
    pooled = wf["pooled_oos"]
    lines.append(
        "| **Pooled OOS** | all folds | "
        + " | ".join(f"**{cell(pooled[n])}**" for n in names)
        + " |"
    )
    return lines


def _print_console(report: dict, json_path: str, md_path: str) -> None:
    m = report["metadata"]
    print("\n" + "=" * 70)
    print("DETECTION-GATE EXPERIMENT — excess over SPY (train / OOS)")
    print("=" * 70)
    print(f"  Split {m['split_year']}: train n={m['n_train']}, OOS n={m['n_oos']}")
    print(f"  Trend-template pass rate: {m['trend_pass_fraction_pct']}%")
    print(f"  Baseline  train={_fmt(report['baseline']['train'])}")
    print(f"            OOS  ={_fmt(report['baseline']['oos'])}")
    if report["selected_gate"]:
        g = report["selected_gate"]
        print(f"  Selected [{g['label']}]")
        print(f"            train={_fmt(g['train'])}")
        print(f"            OOS  ={_fmt(g['oos'])}   <-- honest out-of-sample")
    for g in report["apriori_gates"]:
        print(
            f"  A-priori [{g['label']}]  "
            f"train={_fmt(g['train'])} | OOS={_fmt(g['oos'])}"
        )
    wf = report.get("walk_forward") or {}
    if wf.get("enabled"):
        print(f"  Walk-forward ({wf['folds']} folds) — pooled OOS excess:")
        for name in [n for n, _ in WF_CANDIDATES] + ["train-selected"]:
            print(f"    {name:<26} {_fmt(wf['pooled_oos'][name])}")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")


def main() -> None:
    run(parse_arguments())


if __name__ == "__main__":
    main()
