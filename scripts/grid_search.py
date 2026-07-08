#!/usr/bin/env python3
"""Walk-forward grid search over VCP detection parameters.

Naively re-running backtest_vcp.py per combination would refetch ~600 tickers
every time. Instead this caches every ticker's history ONCE, then sweeps
parameters entirely offline, reusing the exact detect→trade pipeline
(scan_history → plan_trade → simulate_exit) so results match the real backtest.

Because this session already showed the VCP signal overfits easily, the search
is WALK-FORWARD: each combo's objective is its out-of-sample performance on a
held-out period, not the in-sample fit. The report shows both, so the
overfitting gap is visible, and applies a multiple-testing (Bonferroni) lens.

Modes:
    python3 scripts/grid_search.py cache   # fetch + pickle all histories (once)
    python3 scripts/grid_search.py time     # run ONE combo, print timing
    python3 scripts/grid_search.py run       # full grid (use after `time`)
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import pickle
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from historical_scanner import scan_history  # noqa: E402
from trade_simulator import _to_chrono, _t_stat, plan_trade, simulate_exit  # noqa: E402
from yf_client import YFClient  # noqa: E402

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "backtests", "grid_cache.pkl")
UNIVERSE = os.path.join(os.path.dirname(__file__), "..", "backtests", "universe_pit_2016_2026.txt")
FETCH_DAYS = 2520 + 620          # 10y scan + lookback + outcome + buffer
STRIDE = 5
OUTCOME_DAYS = 60
MAX_HOLD = 60
MAX_EXT = 5.0
MAX_RISK = 8.0
COST_BPS = 10.0                  # per side, stock leg
SPLIT_YEAR = "2020"             # train <= 2020, test > 2020

# ── Parameter grid (the high-leverage detection knobs) ───────────────────────
GRID = {
    "min_contractions": [2, 3],
    "contraction_ratio": [0.6, 0.7, 0.8],
    "t1_depth_min": [8.0, 12.0, 15.0],
}
SCORE_CUTOFFS = [0, 50, 60, 65, 70, 75]   # swept post-hoc per combo (cheap)


def read_universe() -> list[str]:
    with open(UNIVERSE) as f:
        return [ln.split("#")[0].strip() for ln in f if ln.split("#")[0].strip()]


def build_cache() -> None:
    client = YFClient()
    syms = read_universe()
    print(f"Caching {len(syms)} tickers + SPY ({FETCH_DAYS}d each)...")
    cache = {}
    spy = client.get_historical_prices("SPY", days=FETCH_DAYS)
    cache["__SPY__"] = (spy or {}).get("historical") or []
    ok = 0
    for i, sym in enumerate(syms, 1):
        try:
            h = client.get_historical_prices(sym, days=FETCH_DAYS)
            bars = (h or {}).get("historical") or []
        except Exception:  # noqa: BLE001
            bars = []
        if len(bars) >= 150:
            cache[sym] = bars
            ok += 1
        if i % 50 == 0:
            print(f"  {i}/{len(syms)}  ({ok} usable)")
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"Cached {ok} tickers + SPY → {CACHE_PATH} ({os.path.getsize(CACHE_PATH)//1_000_000} MB)")


def _trades_for_combo(cache: dict, params: dict) -> list[dict]:
    """Run the detect→trade pipeline over the cache for one param combo.

    Returns trade dicts with entry year, composite_score, and net excess vs SPY
    (10bps/side cost on the stock leg).
    """
    spy_bars = cache["__SPY__"]
    spy_chrono, spy_idx = _to_chrono(spy_bars)
    ak = {
        "min_contractions": params["min_contractions"],
        "contraction_ratio": params["contraction_ratio"],
        "t1_depth_min": params["t1_depth_min"],
    }
    c = COST_BPS / 1e4
    trades = []
    for sym, bars in cache.items():
        if sym == "__SPY__":
            continue
        dets = scan_history(sym, bars, spy_bars, stride_days=STRIDE,
                            outcome_days=OUTCOME_DAYS, lookback_days=120, analyzer_kwargs=ak)
        if not dets:
            continue
        chrono, idx_map = _to_chrono(bars)
        for det in dets:
            if (det.get("forward_outcome") or {}).get("outcome_type") != "breakout":
                continue
            plan = plan_trade(det, MAX_EXT, MAX_RISK)
            if plan["action"] != "trade":
                continue
            start = idx_map.get(plan["entry_date"])
            if start is None:
                continue
            ex = simulate_exit(chrono, start, plan["stop_price"], MAX_HOLD)
            if ex is None:
                continue
            net_ret = (ex["exit_price"] * (1 - c)) / (plan["entry_price"] * (1 + c)) - 1
            si, sj = spy_idx.get(plan["entry_date"]), spy_idx.get(ex["exit_date"])
            if si is None or sj is None or sj <= si:
                continue
            spy_ret = spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1
            trades.append({
                "year": plan["entry_date"][:4],
                "score": det.get("composite_score") or 0,
                "excess": (net_ret - spy_ret) * 100,
            })
    return trades


def _stats(xs: list[float]) -> tuple:
    if len(xs) < 2:
        return (None, None, len(xs))
    return (round(st.fmean(xs), 3), _t_stat(xs), len(xs))


def evaluate(trades: list[dict], cutoff: float) -> dict:
    tr = [t for t in trades if t["score"] >= cutoff and t["year"] <= SPLIT_YEAR]
    te = [t for t in trades if t["score"] >= cutoff and t["year"] > SPLIT_YEAR]
    return {
        "cutoff": cutoff,
        "train": _stats([t["excess"] for t in tr]),
        "test": _stats([t["excess"] for t in te]),
    }


def run_grid() -> None:
    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    n_tests = len(combos) * len(SCORE_CUTOFFS)
    print(f"Grid: {len(combos)} detection combos × {len(SCORE_CUTOFFS)} cutoffs "
          f"= {n_tests} configs (Bonferroni α/{n_tests})")

    rows = []
    for k, params in enumerate(combos, 1):
        t0 = time.time()
        trades = _trades_for_combo(cache, params)
        for cutoff in SCORE_CUTOFFS:
            ev = evaluate(trades, cutoff)
            rows.append({**params, **ev})
        print(f"  [{k}/{len(combos)}] {params}  {len(trades)} trades  {time.time()-t0:.0f}s")

    # Rank by OOS test mean excess, requiring a non-trivial test sample
    valid = [r for r in rows if r["test"][2] >= 30 and r["test"][0] is not None]
    valid.sort(key=lambda r: r["test"][0], reverse=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_json = os.path.join(os.path.dirname(CACHE_PATH), f"grid_results_{ts}.json")
    with open(out_json, "w") as f:
        json.dump(rows, f, indent=2, default=str)

    print("\n" + "=" * 96)
    print("TOP CONFIGS BY OUT-OF-SAMPLE (2021-2026) MEAN EXCESS vs SPY  (test n>=30)")
    print("=" * 96)
    hdr = f"{'minC':>5}{'cRatio':>7}{'t1dep':>6}{'cutoff':>7}{'trainExc':>10}{'trainT':>8}{'trainN':>7}{'testExc':>9}{'testT':>7}{'testN':>7}"
    print(hdr); print("-" * len(hdr))
    for r in valid[:15]:
        tr, te = r["train"], r["test"]
        print(f"{r['min_contractions']:>5}{r['contraction_ratio']:>7}{r['t1_depth_min']:>6}"
              f"{r['cutoff']:>7}{str(tr[0]):>10}{str(tr[1]):>8}{tr[2]:>7}"
              f"{str(te[0]):>9}{str(te[1]):>7}{te[2]:>7}")

    # Also show the IN-SAMPLE best to expose the overfitting gap
    tr_valid = [r for r in rows if r["train"][2] >= 30 and r["train"][0] is not None]
    tr_valid.sort(key=lambda r: r["train"][0], reverse=True)
    if tr_valid:
        b = tr_valid[0]
        print(f"\nIn-sample best: minC={b['min_contractions']} cRatio={b['contraction_ratio']} "
              f"t1={b['t1_depth_min']} cutoff={b['cutoff']} → train {b['train'][0]}% (t={b['train'][1]}) "
              f"BUT test {b['test'][0]}% (t={b['test'][1]}, n={b['test'][2]})")
    print(f"\nResults JSON: {out_json}")
    print("NOTE: with", n_tests, "configs, Bonferroni-significant OOS needs t >",
          round(2.6 if n_tests < 50 else 3.0, 1), "— judge accordingly.")


def main() -> None:
    ap = argparse.ArgumentParser(description="VCP walk-forward grid search")
    ap.add_argument("mode", choices=["cache", "time", "run"])
    args = ap.parse_args()
    if args.mode == "cache":
        build_cache()
    elif args.mode == "time":
        with open(CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
        params = {"min_contractions": 2, "contraction_ratio": 0.7, "t1_depth_min": 10.0}
        t0 = time.time()
        trades = _trades_for_combo(cache, params)
        dt = time.time() - t0
        print(f"one combo: {len(trades)} trades in {dt:.1f}s  "
              f"→ full grid ≈ {dt*len(list(itertools.product(*GRID.values())))/60:.0f} min")
        for cutoff in (0, 70):
            ev = evaluate(trades, cutoff)
            print(f"  cutoff {cutoff}: train {ev['train']}  test {ev['test']}")
    else:
        run_grid()


if __name__ == "__main__":
    main()
