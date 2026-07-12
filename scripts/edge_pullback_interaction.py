"""Edge Rank × MA20-pullback interaction — one-shot declared test (2026-07-12).

Question: does the validated MA20-pullback paired improvement (Δ = pullback
excess − breakout excess on the same detection) concentrate in high-Edge-Rank
detections, i.e. do the two shipped overlays compound?

Declared before running (no sweep): primary = Δ split at Edge Rank ≥ 70;
secondary = Spearman(edge, Δ); bar = hi-group Δ > 0 with t ≥ 2 pooled, same
sign in both universes, positive hi−lo interaction. Shipped parameters only
(MA20 touch, 15-bar window, ≤5% extension, 8% max risk, 60-bar timeout).

RESULT — fails the bar; hypothesis rejected:

  | Group            | n   | Δ (pp) | t    | folds 16-20/21-26 | trim-top-5 |
  |------------------|-----|--------|------|-------------------|------------|
  | S&P  Edge≥70     | 47  | +0.62  | 1.16 | +1.01 / +0.33     | −0.03      |
  | S&P  Edge<70     | 131 | +1.69  | 3.11 | +2.41 / +1.38     | +0.86      |
  | R2K  Edge≥70     | 152 | +4.34  | 1.04 | +9.82 / +0.14     | −0.36      |
  | R2K  Edge<70     | 435 | +1.17  | 2.80 | +0.82 / +1.43     | +0.60      |
  | Pool Edge≥70     | 199 | +3.46  | 1.09 | +7.77 / +0.19     | −0.12      |
  | Pool Edge<70     | 566 | +1.29  | 3.74 | +1.10 / +1.41     | +0.85      |

The interaction flips sign across universes (−1.07 pp S&P / +3.17 pp R2K,
pooled Welch t 0.68); pooled Spearman(edge, Δ) = −0.04 (z −1.11). The hi-group
means are outlier-driven (trim flips them negative). The pullback improvement
is broad-based and, if anything, lives in *lower*-Edge names — high-Edge names
are less extended by construction, so their breakout entries are already
near-fair. The two overlays repair overlapping weaknesses (substitutes, not
complements), consistent with frozen v1 combining both and gaining nothing.
Do NOT flip to "low-Edge + pullback": post-hoc subgroup, and low-Edge names
have the worst baseline excess (Q1 −2.22%).

Usage:
  python3 scripts/edge_pullback_interaction.py <vcp_backtest.json>... \
      [--price-csv SP500_Historical_Data.csv] [--pairs-out pairs.json]
  python3 scripts/edge_pullback_interaction.py --analyze sp.json r2k.json
"""

import argparse
import json
import math
import os
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edge_rank import compute_edge_rank, spearman  # noqa: E402
from pullback_experiment import plan_pullback_entry  # noqa: E402
from trade_simulator import _to_chrono, simulate_exit  # noqa: E402

MAX_EXT, MAX_RISK, MAX_HOLD = 5.0, 8.0, 60
MA_PERIOD, WINDOW, EDGE_CUT = 20, 15, 70.0
FOLD_SPLIT = "2021-01-01"


def _tstat(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    s = st.stdev(xs)
    return st.mean(xs) / (s / math.sqrt(len(xs))) if s > 0 else float("nan")


def group_stats(pairs: list[dict]) -> dict | None:
    """Summary stats for one Edge group's paired deltas. Pure."""
    d = [p["delta"] for p in pairs]
    if len(d) < 6:
        return None
    f1 = [p["delta"] for p in pairs if p["as_of"] < FOLD_SPLIT]
    f2 = [p["delta"] for p in pairs if p["as_of"] >= FOLD_SPLIT]
    trim = sorted(d)[:-5] if len(d) > 5 else d
    return {
        "n": len(d),
        "mean": round(st.mean(d), 2),
        "t": round(_tstat(d), 2),
        "fold1": round(st.mean(f1), 2) if f1 else None,
        "fold2": round(st.mean(f2), 2) if f2 else None,
        "trim5": round(st.mean(trim), 2),
    }


def analyze(label: str, pairs: list[dict], lines: list[str]) -> None:
    """Print + collect markdown rows for one pair set. Appends to ``lines``."""
    hi = [p for p in pairs if p["edge"] >= EDGE_CUT]
    lo = [p for p in pairs if p["edge"] < EDGE_CUT]
    print(f"== {label}: pairs={len(pairs)} (hi n={len(hi)}, lo n={len(lo)})")
    lines.append(f"### {label} — {len(pairs)} pairs")
    lines.append("")
    lines.append("| Group | N | Mean Δ | t | Fold 16–20 | Fold 21–26 | trim-top-5 |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, grp in ((f"Edge≥{EDGE_CUT:.0f}", hi), (f"Edge<{EDGE_CUT:.0f}", lo)):
        s = group_stats(grp)
        if s is None:
            print(f"  {name}: n={len(grp)} (too few)")
            lines.append(f"| {name} | {len(grp)} | too few | | | | |")
            continue
        print(
            f"  {name}: mean Δ {s['mean']:+.2f} pp  t={s['t']:+.2f} | "
            f"folds {s['fold1']}/{s['fold2']} | trim5 {s['trim5']:+.2f}"
        )
        lines.append(
            f"| {name} | {s['n']} | {s['mean']:+.2f} pp | {s['t']} | "
            f"{s['fold1']} | {s['fold2']} | {s['trim5']} |"
        )
    if len(hi) >= 6 and len(lo) >= 6:
        a = [p["delta"] for p in hi]
        b = [p["delta"] for p in lo]
        se = math.sqrt(st.variance(a) / len(a) + st.variance(b) / len(b))
        diff = st.mean(a) - st.mean(b)
        print(f"  interaction hi-lo: {diff:+.2f} pp  Welch t={diff/se:+.2f}")
        lines.append(f"\nInteraction hi−lo: **{diff:+.2f} pp** (Welch t {diff/se:+.2f})")
    rho = spearman([(p["edge"], p["delta"]) for p in pairs])
    if rho is not None:
        z = rho * math.sqrt(len(pairs) - 1)
        print(f"  secondary Spearman(edge, Δ): {rho:+.3f} (z={z:+.2f}, n={len(pairs)})")
        lines.append(f"Spearman(edge, Δ): {rho:+.3f} (z {z:+.2f})")
    lines.append("")


def build_pairs(backtest_jsons: list[str], price_csv: str | None,
                sleep_secs: float) -> list[dict]:
    detections_by_ticker: dict[str, list[dict]] = {}
    for path in backtest_jsons:
        payload = json.load(open(path))
        for sym, dets in (payload.get("detections_by_ticker") or {}).items():
            detections_by_ticker.setdefault(sym, []).extend(dets)

    scores = compute_edge_rank(detections_by_ticker, w_rs=0.7, w_ext=0.3)

    if price_csv:
        from csv_client import CSVClient  # noqa: PLC0415 — optional offline path

        client = CSVClient(price_csv)
        sleep_secs = 0.0
    else:
        from yf_client import YFClient  # noqa: PLC0415 — online fallback

        client = YFClient()

    fetch_days = 2520 + 500
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"]
    )
    print(f"SPY bars: {len(spy_chrono)}", flush=True)

    def spy_ret(d1: str, d2: str) -> float | None:
        i, j = spy_idx.get(d1), spy_idx.get(d2)
        if i is None or j is None or j <= i:
            return None
        return (spy_chrono[j]["close"] / spy_chrono[i]["close"] - 1) * 100

    def leg_excess(chrono, entry_idx, entry_price, pattern_stop):
        stop = max(pattern_stop or 0, entry_price * (1 - MAX_RISK / 100))
        ex = simulate_exit(chrono, entry_idx, stop, MAX_HOLD)
        if ex is None:
            return None
        ret = (ex["exit_price"] / entry_price - 1) * 100
        sr = spy_ret(chrono[entry_idx]["date"], ex["exit_date"])
        return ret - sr if sr is not None else None

    pairs = []
    symbols = sorted(detections_by_ticker)
    for i, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            continue
        chrono, idx_map = _to_chrono((hist or {}).get("historical") or [])
        for det in detections_by_ticker[sym]:
            fo = det.get("forward_outcome") or {}
            pivot, pattern_stop = fo.get("pivot_price"), fo.get("stop_price")
            if fo.get("outcome_type") != "breakout" or not pivot:
                continue
            score = scores.get((sym, det.get("as_of_date")))
            if score is None:
                continue
            bo_idx = idx_map.get(fo.get("exit_date"))
            if bo_idx is None:
                continue
            bo_price = fo.get("exit_price") or chrono[bo_idx]["close"]
            if (bo_price / pivot - 1) * 100 > MAX_EXT:
                continue
            bo_exc = leg_excess(chrono, bo_idx, bo_price, pattern_stop)
            if bo_exc is None:
                continue
            wait_stop = pattern_stop or pivot * (1 - MAX_RISK / 100)
            plan = plan_pullback_entry(
                chrono, bo_idx, pivot, wait_stop, window=WINDOW, ma_period=MA_PERIOD
            )
            if plan is None:
                continue
            pb_exc = leg_excess(chrono, plan["entry_idx"], plan["entry_price"], pattern_stop)
            if pb_exc is None:
                continue
            pairs.append({
                "sym": sym,
                "as_of": det.get("as_of_date"),
                "edge": score["edge_rank"],
                "delta": round(pb_exc - bo_exc, 4),
            })
        if sleep_secs > 0 and i < len(symbols):
            time.sleep(sleep_secs)
        if i % 200 == 0:
            print(f"  ...{i}/{len(symbols)} symbols, pairs so far {len(pairs)}", flush=True)
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Edge Rank × MA20-pullback interaction (one-shot declared test)"
    )
    ap.add_argument("backtest_jsons", nargs="*", help="vcp_backtest_*.json report(s)")
    ap.add_argument("--price-csv", help="Offline OHLCV CSV (CSVClient); else yfinance")
    ap.add_argument("--label", default="run")
    ap.add_argument("--pairs-out", help="Save per-detection pairs JSON here")
    ap.add_argument("--analyze", nargs="+",
                    help="Pool + analyze saved pairs JSONs instead of building")
    ap.add_argument("--sleep-secs", type=float, default=0.25)
    ap.add_argument("--output-dir", default="backtests/")
    args = ap.parse_args()

    lines = ["# Edge Rank × Pullback Interaction", "",
             f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "",
             "Δ = MA20-pullback excess − breakout excess on the same detection (pp).",
             f"Declared split: Edge Rank ≥ {EDGE_CUT:.0f}. No sweep.", ""]

    if args.analyze:
        pooled = []
        for p in args.analyze:
            part = json.load(open(p))
            analyze(os.path.basename(p), part, lines)
            pooled.extend(part)
        analyze("POOLED", pooled, lines)
    else:
        pairs = build_pairs(args.backtest_jsons, args.price_csv, args.sleep_secs)
        if args.pairs_out:
            with open(args.pairs_out, "w") as f:
                json.dump(pairs, f)
            print(f"pairs saved: {args.pairs_out}")
        analyze(args.label, pairs, lines)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_edge_pullback_interaction_{ts}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
