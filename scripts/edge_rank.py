#!/usr/bin/env python3
"""Edge Rank v2 — an evidence-based replacement for the composite score.

The legacy 5-component composite has ~0 information coefficient (IC) against
forward excess-over-SPY. An IC panel over the trade log found only two signals
that individually predict forward excess at 95% significance (n=317, SE≈0.056):

    rs_252d    12-month relative strength vs SPY   IC = +0.126  (higher better)
    sma50_dist distance above the 50-day MA        IC = -0.111  (less extended better)

Blended "strong-but-not-extended" factor: full-sample IC ≈ +0.18 (survives
Bonferroni). Both signals are the same sign in each time split — regime-varying
strength, not a sign-flipping regime bet.

Edge Rank v2 is a **cross-sectional percentile** blend of those two signals,
computed per as-of date over the whole scanned universe (causal — same-date
data only), so it is always 0-100 well-distributed and interpretable as
"top X% of the universe today". Weights are a-priori (0.70/0.30), not fitted,
to avoid mining a sample this small.

This CLI is fully offline: it reads detection features from a
``vcp_backtest_*.json`` and joins realised returns from a ``vcp_trades_*.json``
to report the IC of Edge Rank v2 (and variants) against forward excess —
full-sample, train/OOS split, N-fold walk-forward, and a score-decile
monotonicity table.

Usage:
    python3 scripts/edge_rank.py \
        backtests/vcp_backtest_YYYY.json \
        backtests/vcp_trades_YYYY.json
"""

from __future__ import annotations

import argparse
import bisect
import collections
import json
import math
import os
import random
import statistics as st
import sys
from datetime import datetime

DEFAULT_W_RS = 0.70
DEFAULT_W_EXT = 0.30


def parse_arguments() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Edge Rank v2 scoring + OOS IC validation")
    ap.add_argument("backtest_json", help="vcp_backtest_*.json (detection features)")
    ap.add_argument("trades_json", help="vcp_trades_*.json (realised trades)")
    ap.add_argument(
        "--w-rs", type=float, default=DEFAULT_W_RS,
        help=f"Weight on 12-month RS percentile (default: {DEFAULT_W_RS})",
    )
    ap.add_argument(
        "--w-ext", type=float, default=DEFAULT_W_EXT,
        help=f"Weight on inverse SMA50-extension percentile (default: {DEFAULT_W_EXT})",
    )
    ap.add_argument(
        "--split-year", type=int, default=2022,
        help="Entry years < this are TRAIN, >= this are OOS (default: 2022)",
    )
    ap.add_argument(
        "--folds", type=int, default=3,
        help="Rolling-origin walk-forward folds for OOS IC (default: 3; 0/1 disables)",
    )
    ap.add_argument("--output-dir", default="backtests/", help="Report directory")
    args = ap.parse_args()
    if not (0.0 <= args.w_rs <= 1.0) or not (0.0 <= args.w_ext <= 1.0):
        ap.error("weights must be 0-1")
    if args.w_rs + args.w_ext <= 0:
        ap.error("weights must sum to > 0")
    if not (1990 <= args.split_year <= 2100):
        ap.error("--split-year out of range")
    if not (0 <= args.folds <= 12):
        ap.error("--folds must be 0-12")
    return args


def rs_252d(det: dict) -> float | None:
    """12-month stock-minus-SPY relative return (%)."""
    for p in (det.get("relative_strength") or {}).get("period_details") or []:
        if p.get("period_days") == 252:
            return p.get("relative_pct")
    return None


def sma50_dist(det: dict) -> float | None:
    """Price distance above the 50-day MA (%). Higher = more extended."""
    return (det.get("trend_template") or {}).get("sma50_distance_pct")


def _percentiles(pairs: list[tuple], ascending: bool) -> dict:
    """Map key -> 0-100 percentile of its value. ``ascending`` True means a
    higher raw value earns a higher percentile. Pure function.
    """
    vals = sorted(v for _, v in pairs)
    denom = max(len(vals) - 1, 1)
    out = {}
    for key, v in pairs:
        pct = bisect.bisect_left(vals, v) / denom * 100
        out[key] = pct if ascending else 100 - pct
    return out


def compute_edge_rank(
    detections_by_ticker: dict, w_rs: float, w_ext: float
) -> dict[tuple[str, str], dict]:
    """Edge Rank v2 per (symbol, as_of_date), cross-sectional per as-of date.

    Only detections with BOTH signals present are scored. Returns a dict of
    ``(sym, date) -> {edge_rank, rs_only, equal, rs_pct, ext_pct}``. Pure.
    """
    by_date: dict[str, list] = collections.defaultdict(list)
    for sym, dets in detections_by_ticker.items():
        for det in dets:
            date = det.get("as_of_date")
            rs, ext = rs_252d(det), sma50_dist(det)
            if date is not None and rs is not None and ext is not None:
                by_date[date].append(((sym, date), rs, ext))

    total = w_rs + w_ext
    scores: dict[tuple[str, str], dict] = {}
    for _, rows in by_date.items():
        rs_pct = _percentiles([(k, rs) for k, rs, _ in rows], ascending=True)
        ext_pct = _percentiles([(k, ext) for k, _, ext in rows], ascending=False)
        for key, _, _ in rows:
            r, e = rs_pct[key], ext_pct[key]
            scores[key] = {
                "edge_rank": round((w_rs * r + w_ext * e) / total, 1),
                "rs_only": round(r, 1),
                "equal": round((r + e) / 2, 1),
                "rs_pct": round(r, 1),
                "ext_pct": round(e, 1),
            }
    return scores


def annotate_candidates(results: list[dict], w_rs: float = DEFAULT_W_RS,
                        w_ext: float = DEFAULT_W_EXT) -> list[dict]:
    """Attach ``edge_rank`` and ``suggested_weight_pct`` to live screen results.

    Edge Rank is ranked cross-sectionally *within the given candidate list*
    (same-day data only, causal); weights follow the deployable sizing rule
    (skip Edge<{min}, linear, capped — see ``suggested_weights``). Candidates
    missing either signal get ``edge_rank=None`` and weight 0. Returns new
    dicts; does not mutate inputs.
    """
    feats = [(rs_252d(s), sma50_dist(s)) for s in results]
    scored_idx = [i for i, (rs, ext) in enumerate(feats) if rs is not None and ext is not None]
    if len(scored_idx) < 2:
        return [{**s, "edge_rank": None, "suggested_weight_pct": 0.0} for s in results]

    rs_pct = _percentiles([(i, feats[i][0]) for i in scored_idx], ascending=True)
    ext_pct = _percentiles([(i, feats[i][1]) for i in scored_idx], ascending=False)
    total = w_rs + w_ext
    edges = {i: round((w_rs * rs_pct[i] + w_ext * ext_pct[i]) / total, 1) for i in scored_idx}
    weights = suggested_weights([edges[i] for i in scored_idx])
    weight_by_idx = dict(zip(scored_idx, weights))
    return [
        {**s, "edge_rank": edges.get(i), "suggested_weight_pct": weight_by_idx.get(i, 0.0)}
        for i, s in enumerate(results)
    ]


def spearman(pairs: list[tuple[float, float]]) -> float | None:
    """Spearman rank IC. Pure function."""
    if len(pairs) < 10:
        return None

    def rank(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    n = len(xs)
    rx, ry = rank(xs), rank(ys)
    mx, my = st.fmean(rx), st.fmean(ry)
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    vy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    return round(cov / (vx * vy), 3) if vx > 0 and vy > 0 else None


def _ic(rows: list[dict], field: str) -> dict:
    pairs = [(r[field], r["excess"]) for r in rows if r.get(field) is not None]
    ic = spearman(pairs)
    n = len(pairs)
    z = round(abs(ic) * math.sqrt(n), 2) if ic is not None and n else None
    return {"ic": ic, "n": n, "z": z, "sig": bool(z and z > 1.96)}


def walk_forward_ic(rows: list[dict], field: str, folds: int) -> dict:
    """Rolling-origin OOS IC: split entry-date-sorted rows into folds+1 blocks,
    report IC on each later block and pooled across them. Pure function.
    """
    ordered = sorted(rows, key=lambda r: r["entry_date"])
    n = len(ordered)
    blocks = folds + 1
    if n < blocks * 8:
        return {"enabled": False, "reason": f"too few rows ({n})"}
    edges = [round(i * n / blocks) for i in range(blocks + 1)]
    segs = [ordered[edges[i]:edges[i + 1]] for i in range(blocks)]
    fold_rows, pooled = [], []
    for i in range(1, blocks):
        seg = segs[i]
        pooled.extend(seg)
        fold_rows.append({
            "fold": i,
            "oos_from": seg[0]["entry_date"],
            "oos_to": seg[-1]["entry_date"],
            **_ic(seg, field),
        })
    return {"enabled": True, "folds": folds, "fold_rows": fold_rows,
            "pooled": _ic(pooled, field)}


def decile_table(rows: list[dict], field: str, buckets: int = 5) -> list[dict]:
    """Bucket rows by ``field`` into quantiles; report mean excess per bucket.
    A monotone rise confirms the score orders forward returns. Pure function.
    """
    have = [r for r in rows if r.get(field) is not None]
    have.sort(key=lambda r: r[field])
    n = len(have)
    if n < buckets * 3:
        return []
    out = []
    for b in range(buckets):
        seg = have[round(b * n / buckets):round((b + 1) * n / buckets)]
        exc = [r["excess"] for r in seg]
        out.append({
            "bucket": f"Q{b + 1}",
            "n": len(seg),
            "score_lo": round(seg[0][field], 1),
            "score_hi": round(seg[-1][field], 1),
            "mean_excess": round(st.fmean(exc), 2),
            "win_pct": round(sum(1 for e in exc if e > 0) / len(exc) * 100, 1),
        })
    return out


# Position-size tilt: weight each trade by edge_rank ** power. power 0 = equal.
TILT_SCHEMES = (("equal", 0), ("linear", 1), ("convex", 2), ("cubic", 3))

# Deployable sizing rule (validated on the PIT dataset): skip Edge<MIN, weight
# linearly by Edge, cap any weight at CAP_MULT x the mean Edge (~55 in-sample).
SIZING_MIN_EDGE = 30.0
SIZING_CAP_MULT = 1.5
_SIZING_CAP_ANCHOR = 55.0  # approx. mean edge of scored candidates


def weighted_mean_fn(rows: list[dict], wfun) -> float | None:
    """Capital-weighted mean excess for an arbitrary weight function. Pure."""
    num = den = 0.0
    for r in rows:
        w = wfun(r)
        num += w * r["excess"]
        den += w
    return num / den if den > 0 else None


def weighted_mean_excess(rows: list[dict], power: float) -> float | None:
    """Capital-weighted mean excess where weight = edge_rank ** power. Pure."""
    return weighted_mean_fn(rows, lambda r: max(r["edge_rank"], 1e-9) ** power)


def _w_capped_linear(cap_mult: float):
    return lambda r: min(max(r["edge_rank"], 1e-9), cap_mult * _SIZING_CAP_ANCHOR)


def _w_skip_low(min_edge: float):
    return lambda r: max(r["edge_rank"], 1e-9) if r["edge_rank"] >= min_edge else 1e-9


def _w_trend_boost(boost: float):
    return lambda r: max(r["edge_rank"], 1e-9) * (boost if r.get("trend_passed") else 1.0)


# Practical portfolio constraints — a real book can't run uncapped weights.
PRACTICAL_SCHEMES = (
    ("linear, cap 1.5x mean", _w_capped_linear(1.5)),
    ("linear, cap 2x mean", _w_capped_linear(2.0)),
    (f"linear + skip Edge<{SIZING_MIN_EDGE:g}", _w_skip_low(SIZING_MIN_EDGE)),
    ("linear + trend-pass boost 1.5x", _w_trend_boost(1.5)),
)


def suggested_weights(edges: list[float], min_edge: float = SIZING_MIN_EDGE,
                      cap_mult: float = SIZING_CAP_MULT) -> list[float]:
    """Normalised position weights (%) for a candidate list's Edge Ranks.

    The deployable rule: weight 0 below ``min_edge``; otherwise linear in Edge,
    capped at ``cap_mult`` x the mean weight of included names; normalised to
    sum to 100. Pure function.
    """
    raw = [e if e >= min_edge else 0.0 for e in edges]
    included = [w for w in raw if w > 0]
    if included:
        cap = cap_mult * (sum(included) / len(included))
        raw = [min(w, cap) for w in raw]
    total = sum(raw)
    if total <= 0:
        return [0.0 for _ in raw]
    return [round(w / total * 100, 2) for w in raw]


def _bootstrap(rows: list[dict], stat_fn, n_iter: int = 10000, seed: int = 42):
    """Percentile 95% CI of ``stat_fn`` over trade-resampled rows. Pure.

    Resamples actual pool members (not positional indices) so it is correct on
    any subset, not just the full sample.
    """
    if len(rows) < 6:
        return None
    rng = random.Random(seed)
    m = len(rows)
    vals = sorted(
        stat_fn([rows[rng.randrange(m)] for _ in range(m)]) for _ in range(n_iter)
    )
    lo, hi = vals[int(0.025 * n_iter)], vals[int(0.975 * n_iter)]
    return [round(lo, 2), round(hi, 2)] if lo is not None and hi is not None else None


def _tilt_stability(rows: list[dict], power: float, split_year: int, folds: int) -> list[dict]:
    """Tilt gain (weighted - equal) on train/OOS and each walk-forward fold."""
    def block(sub, label):
        if len(sub) < 6:
            return {"label": label, "n": len(sub), "gain": None, "gain_ci": None}
        wm = weighted_mean_excess(sub, power)
        em = weighted_mean_excess(sub, 0)
        gain_ci = _bootstrap(
            sub, lambda s: (weighted_mean_excess(s, power) or 0) - (weighted_mean_excess(s, 0) or 0)
        )
        return {"label": label, "n": len(sub), "equal": round(em, 2),
                "tilt": round(wm, 2), "gain": round(wm - em, 2), "gain_ci": gain_ci}

    out = [
        block([r for r in rows if int(r["entry_date"][:4]) < split_year], f"train(<{split_year})"),
        block([r for r in rows if int(r["entry_date"][:4]) >= split_year], f"OOS(>={split_year})"),
    ]
    if folds >= 2:
        ordered = sorted(rows, key=lambda r: r["entry_date"])
        n = len(ordered)
        for f in range(folds):
            seg = ordered[round(f * n / folds):round((f + 1) * n / folds)]
            if seg:
                out.append(block(seg, f"fold{f + 1} ({seg[0]['entry_date']}→{seg[-1]['entry_date']})"))
    return out


def tilt_backtest(rows: list[dict], split_year: int, folds: int) -> dict:
    """Edge-weighted position-size tilt vs equal weight, with significance.

    The equal-weight pool has ~0 edge; the test is whether reallocating capital
    toward high-Edge trades adds value. Reports each weight scheme's weighted
    mean excess and its *gain* over equal weight (bootstrap CI), the linear
    tilt's stability, and capital-concentration diagnostics. Pure function.
    """
    equal_mean = weighted_mean_excess(rows, 0)
    schemes = []
    for name, power in TILT_SCHEMES:
        wm = weighted_mean_excess(rows, power)
        wm_ci = _bootstrap(rows, lambda s, p=power: weighted_mean_excess(s, p))
        gain_ci = _bootstrap(
            rows,
            lambda s, p=power: (weighted_mean_excess(s, p) or 0) - (weighted_mean_excess(s, 0) or 0),
        )
        schemes.append({
            "scheme": name, "power": power,
            "w_mean_excess": round(wm, 2) if wm is not None else None,
            "w_mean_ci": wm_ci,
            "gain_vs_equal": round(wm - equal_mean, 2) if wm is not None else None,
            "gain_ci": gain_ci,
        })

    practical = []
    for name, wfun in PRACTICAL_SCHEMES:
        wm = weighted_mean_fn(rows, wfun)
        gain_ci = _bootstrap(
            rows,
            lambda s, f=wfun: (weighted_mean_fn(s, f) or 0) - (weighted_mean_fn(s, lambda r: 1.0) or 0),
        )
        ws = [wfun(r) for r in rows]
        sw_ = sum(ws)
        practical.append({
            "scheme": name,
            "w_mean_excess": round(wm, 2) if wm is not None else None,
            "gain_vs_equal": round(wm - equal_mean, 2) if wm is not None else None,
            "gain_ci": gain_ci,
            "effective_n": round((sw_ ** 2) / sum(w * w for w in ws)) if sw_ > 0 else 0,
        })

    weights = [max(r["edge_rank"], 1e-9) for r in rows]
    sw = sum(weights)
    eff_n = round((sw ** 2) / sum(w * w for w in weights)) if sw > 0 else 0
    top_cap = sum(r["edge_rank"] for r in rows if r["edge_rank"] >= 80)
    return {
        "equal_weight_mean": round(equal_mean, 2) if equal_mean is not None else None,
        "n": len(rows),
        "schemes": schemes,
        "practical_schemes": practical,
        "linear_stability": _tilt_stability(rows, 1, split_year, folds),
        "effective_n_linear": eff_n,
        "top_quintile_capital_pct": round(top_cap / sw * 100, 0) if sw > 0 else None,
    }


def build_rows(detections: dict, trades: list[dict], scores: dict) -> list[dict]:
    """Join realised trades to Edge Rank scores + legacy composite. Pure."""
    det_lookup = {
        (sym, det.get("as_of_date")): det
        for sym, dets in detections.items()
        for det in dets
    }
    rows = []
    for t in trades:
        key = (t["symbol"], t["as_of_date"])
        sc = scores.get(key)
        det = det_lookup.get(key)
        if sc is None or det is None or t.get("excess_vs_spy_pct") is None:
            continue
        rows.append({
            "excess": t["excess_vs_spy_pct"],
            "entry_date": t["entry_date"],
            "composite": t.get("composite_score"),
            "trend_passed": bool((det.get("trend_template") or {}).get("passed")),
            **sc,
        })
    return rows


def run(args: argparse.Namespace) -> None:
    detections = json.load(open(args.backtest_json)).get("detections_by_ticker") or {}
    trades = json.load(open(args.trades_json)).get("trades") or []
    if not detections or not trades:
        print("ERROR: need non-empty detections and trades", file=sys.stderr)
        sys.exit(1)

    scores = compute_edge_rank(detections, args.w_rs, args.w_ext)
    rows = build_rows(detections, trades, scores)
    if len(rows) < 20:
        print(f"ERROR: only {len(rows)} joinable rows — too few", file=sys.stderr)
        sys.exit(1)

    split = args.split_year
    train = [r for r in rows if int(r["entry_date"][:4]) < split]
    oos = [r for r in rows if int(r["entry_date"][:4]) >= split]

    variants = ["edge_rank", "rs_only", "equal", "composite"]
    ic_summary = {
        v: {
            "full": _ic(rows, v),
            "train": _ic(train, v),
            "oos": _ic(oos, v),
            "walk_forward": walk_forward_ic(rows, v, args.folds) if args.folds >= 2
            else {"enabled": False, "reason": "disabled"},
        }
        for v in variants
    }
    deciles = decile_table(rows, "edge_rank")
    tilt = tilt_backtest(rows, split, args.folds)

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_json": os.path.basename(args.backtest_json),
        "trades_json": os.path.basename(args.trades_json),
        "weights": {"rs_252d_pct": args.w_rs, "inv_sma50_ext_pct": args.w_ext},
        "split_year": split,
        "folds": args.folds,
        "n_rows": len(rows),
        "n_train": len(train),
        "n_oos": len(oos),
        "ic_note": f"IC SE≈{1 / math.sqrt(len(rows)):.3f}; |z|>1.96 = 95% significant",
    }
    report = {"metadata": metadata, "ic_summary": ic_summary, "deciles": deciles,
              "tilt_backtest": tilt}

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"vcp_edge_rank_{ts}.json")
    md_path = os.path.join(args.output_dir, f"vcp_edge_rank_{ts}.md")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)
    with open(md_path, "w") as f:
        f.write(_render_markdown(report))
    _print_console(report, json_path, md_path)


def _icfmt(d: dict) -> str:
    if d.get("ic") is None:
        return f"n={d.get('n', 0)} —"
    return f"{d['ic']:+.3f} (z={d['z']}{'*' if d['sig'] else ''}, n={d['n']})"


def _render_markdown(report: dict) -> str:
    m = report["metadata"]
    w = m["weights"]
    lines = [
        "# Edge Rank v2 — IC validation",
        "",
        f"Generated: {m['generated_at']}",
        f"Detections: {m['backtest_json']} | Trades: {m['trades_json']}",
        "",
        f"- Score = {w['rs_252d_pct']:g}×(12m RS pct) + "
        f"{w['inv_sma50_ext_pct']:g}×(inverse SMA50-extension pct), cross-sectional "
        f"per as-of date",
        f"- Rows: {m['n_rows']} (train {m['n_train']} / OOS {m['n_oos']}); "
        f"split {m['split_year']}",
        f"- {m['ic_note']} (`*` marks significant)",
        "",
        "IC = Spearman rank correlation of score vs forward excess-over-SPY. A "
        "usable score has positive IC that holds sign across train, OOS and the "
        "pooled walk-forward.",
        "",
        "## IC by variant",
        "",
        "| Score | Full | TRAIN | OOS | Walk-forward pooled |",
        "|---|---|---|---|---|",
    ]
    labels = {"edge_rank": "**Edge Rank v2**", "rs_only": "RS-only (12m pct)",
              "equal": "Equal 50/50", "composite": "Legacy composite"}
    for v in ["edge_rank", "rs_only", "equal", "composite"]:
        s = report["ic_summary"][v]
        wf = s["walk_forward"]
        wf_cell = _icfmt(wf["pooled"]) if wf.get("enabled") else "—"
        lines.append(
            f"| {labels[v]} | {_icfmt(s['full'])} | {_icfmt(s['train'])} | "
            f"{_icfmt(s['oos'])} | {wf_cell} |"
        )

    wf = report["ic_summary"]["edge_rank"]["walk_forward"]
    if wf.get("enabled"):
        lines += ["", "## Edge Rank v2 — walk-forward folds", "",
                  "| Fold | OOS window | IC |", "|---|---|---|"]
        for fr in wf["fold_rows"]:
            lines.append(f"| {fr['fold']} | {fr['oos_from']}→{fr['oos_to']} | {_icfmt(fr)} |")

    if report["deciles"]:
        lines += ["", "## Edge Rank v2 — score quantiles vs forward excess", "",
                  "| Bucket | Score range | N | Mean excess | Win% |",
                  "|---|---|---|---|---|"]
        for d in report["deciles"]:
            lines.append(
                f"| {d['bucket']} | {d['score_lo']}–{d['score_hi']} | {d['n']} | "
                f"{d['mean_excess']}% | {d['win_pct']}% |"
            )
    lines += _render_tilt(report.get("tilt_backtest") or {})
    lines += ["", "## Notes", "",
              "- Cross-sectional percentiles use only same-date data (causal, no",
              "  lookahead). Weights are a-priori, not fitted to these outcomes.",
              "- Signals are regime-varying (stronger post-2022) but same-sign in",
              "  both splits — factor exposure, not a sign-flipping regime bet.",
              "- Tilt sizes every trade by edge_rank**power; the *gain* over equal",
              "  weight (CI excluding 0) is the significant result, not the",
              "  absolute weighted mean (the pool itself averages ~0).", ""]
    return "\n".join(lines)


def _ci(ci) -> str:
    return f"({ci[0]}, {ci[1]})" if ci else "—"


def _render_tilt(tilt: dict) -> list[str]:
    if not tilt:
        return []
    lines = [
        "",
        "## Position-size tilt — Edge-weighted vs equal weight",
        "",
        f"Weight each of the {tilt['n']} trades by `edge_rank ** power` (power 0 = "
        f"equal). Equal-weight pool averages {tilt['equal_weight_mean']}% excess. "
        "The **gain over equal weight** (bootstrap CI excluding 0) is the test — "
        "it isolates the value of tilting from the pool's own ~0 base.",
        "",
        "| Weight scheme | Weighted excess | 95% CI | Gain vs equal | Gain 95% CI |",
        "|---|---|---|---|---|",
    ]
    for s in tilt["schemes"]:
        sig = "*" if s["gain_ci"] and s["gain_ci"][0] > 0 else ""
        lines.append(
            f"| {s['scheme']} (w=Edge^{s['power']}) | {s['w_mean_excess']}% | "
            f"{_ci(s['w_mean_ci'])} | {s['gain_vs_equal']}%{sig} | {_ci(s['gain_ci'])} |"
        )
    lines += ["", f"`*` = gain CI excludes 0 (significant). Linear-tilt effective "
              f"positions = {tilt['effective_n_linear']} of {tilt['n']}; "
              f"top-quintile (Edge≥80) holds {tilt['top_quintile_capital_pct']}% of "
              "capital."]
    if tilt.get("practical_schemes"):
        lines += ["", "### Practical portfolio constraints", "",
                  "Real books cap concentration; the tilt must survive that to be "
                  "deployable.", "",
                  "| Sizing rule | Weighted excess | Gain vs equal | Gain 95% CI | Eff. N |",
                  "|---|---|---|---|---|"]
        for s in tilt["practical_schemes"]:
            sig = "*" if s["gain_ci"] and s["gain_ci"][0] > 0 else ""
            lines.append(
                f"| {s['scheme']} | {s['w_mean_excess']}% | {s['gain_vs_equal']}%{sig} | "
                f"{_ci(s['gain_ci'])} | {s['effective_n']} |"
            )
    lines += ["",
              "### Linear tilt — stability (gain vs equal)", "",
              "| Segment | N | Equal | Tilt | Gain | Gain 95% CI |", "|---|---|---|---|---|---|"]
    for b in tilt["linear_stability"]:
        if b["gain"] is None:
            lines.append(f"| {b['label']} | {b['n']} | — | — | — | — |")
        else:
            sig = "*" if b["gain_ci"] and b["gain_ci"][0] > 0 else ""
            lines.append(
                f"| {b['label']} | {b['n']} | {b['equal']}% | {b['tilt']}% | "
                f"{b['gain']}%{sig} | {_ci(b['gain_ci'])} |"
            )
    return lines


def _print_console(report: dict, json_path: str, md_path: str) -> None:
    print("\n" + "=" * 70)
    print("EDGE RANK v2 — IC vs forward excess-over-SPY")
    print("=" * 70)
    for v in ["edge_rank", "rs_only", "equal", "composite"]:
        s = report["ic_summary"][v]
        wf = s["walk_forward"]
        wf_cell = _icfmt(wf["pooled"]) if wf.get("enabled") else "—"
        print(f"  {v:<16} full {_icfmt(s['full'])}")
        print(f"  {'':<16} OOS  {_icfmt(s['oos'])} | WF {wf_cell}")
    if report["deciles"]:
        print("  Edge Rank quantiles (mean excess):")
        for d in report["deciles"]:
            print(f"    {d['bucket']} [{d['score_lo']}-{d['score_hi']}]  "
                  f"{d['mean_excess']:+}%  (n={d['n']})")
    tilt = report.get("tilt_backtest") or {}
    if tilt:
        print(f"  Position-size tilt (equal pool = {tilt['equal_weight_mean']}%):")
        for s in tilt["schemes"]:
            sig = " *" if s["gain_ci"] and s["gain_ci"][0] > 0 else ""
            print(f"    {s['scheme']:<8} gain vs equal {s['gain_vs_equal']:+}% "
                  f"CI {_ci(s['gain_ci'])}{sig}")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")


def main() -> None:
    run(parse_arguments())


if __name__ == "__main__":
    main()
