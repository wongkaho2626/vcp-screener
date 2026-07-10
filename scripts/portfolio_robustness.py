#!/usr/bin/env python3
"""Professional robustness report for a daily portfolio return/equity series.

The input must be CSV with a date column and either a decimal daily return
column or an equity column.  No network access is used.  Optional statsmodels
tests are reported as unavailable rather than silently omitted.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics as st
from pathlib import Path

import pandas as pd

TRADING_DAYS = 252


def _finite(values) -> list[float]:
    return [float(x) for x in values if pd.notna(x) and math.isfinite(float(x))]


def _safe_number(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def sharpe(returns: list[float], periods: int = TRADING_DAYS) -> float | None:
    if len(returns) < 2:
        return None
    sd = st.stdev(returns)
    return st.fmean(returns) / sd * math.sqrt(periods) if sd else None


def max_drawdown(returns: list[float]) -> tuple[float, int, list[float]]:
    wealth = peak = 1.0
    worst = 0.0
    duration = longest = 0
    drawdowns = []
    for value in returns:
        wealth *= 1 + value
        peak = max(peak, wealth)
        dd = wealth / peak - 1
        drawdowns.append(dd)
        if dd < 0:
            duration += 1
            longest = max(longest, duration)
        else:
            duration = 0
    return worst if not drawdowns else min(drawdowns), longest, drawdowns


def effective_sample_size(returns: list[float], max_lag: int | None = None) -> tuple[float, list[float]]:
    n = len(returns)
    if n < 3:
        return float(n), []
    lag_max = min(max_lag or int(math.sqrt(n)), n - 2)
    mean = st.fmean(returns)
    denom = sum((x - mean) ** 2 for x in returns)
    rhos = []
    for lag in range(1, lag_max + 1):
        rho = sum((returns[i] - mean) * (returns[i - lag] - mean) for i in range(lag, n)) / denom if denom else 0.0
        rhos.append(rho)
    # Initial-positive-sequence prevents negative noise from inflating n_eff.
    positive_sum = 0.0
    for rho in rhos:
        if rho <= 0:
            break
        positive_sum += rho
    return max(1.0, min(float(n), n / (1 + 2 * positive_sum))), rhos


def probabilistic_sharpe(returns: list[float], benchmark: float = 0.0) -> float | None:
    n = len(returns)
    observed_annual = sharpe(returns)
    if n < 3 or observed_annual is None:
        return None
    # Bailey & Lopez de Prado's finite-sample expression uses the Sharpe at
    # the observation frequency. ``sharpe`` and public benchmarks here are
    # annualized, so convert both back to daily before applying the formula.
    observed = observed_annual / math.sqrt(TRADING_DAYS)
    benchmark_period = benchmark / math.sqrt(TRADING_DAYS)
    mean, sd = st.fmean(returns), st.stdev(returns)
    skew = sum(((x - mean) / sd) ** 3 for x in returns) / n
    kurt = sum(((x - mean) / sd) ** 4 for x in returns) / n
    denom = 1 - skew * observed + (kurt - 1) * observed * observed / 4
    if denom <= 0:
        return None
    z = (observed - benchmark_period) * math.sqrt(n - 1) / math.sqrt(denom)
    return st.NormalDist().cdf(z)


def deflated_sharpe(returns: list[float], trials: int) -> dict[str, float | None]:
    """Approximate DSR using the expected maximum of ``trials`` normals.

    The benchmark is expressed as an annualized Sharpe.  This approximation
    assumes candidate Sharpe estimates share the observed standard error.
    """
    observed = sharpe(returns)
    if observed is None:
        return {"benchmark_sharpe": None, "probability": None}
    trials = max(1, trials)
    n_eff, _ = effective_sample_size(returns)
    se = math.sqrt(TRADING_DAYS / max(n_eff - 1, 1))
    if trials == 1:
        benchmark = 0.0
    else:
        gamma = 0.5772156649
        nd = st.NormalDist()
        benchmark = se * ((1 - gamma) * nd.inv_cdf(1 - 1 / trials) + gamma * nd.inv_cdf(1 - 1 / (trials * math.e)))
    # Reuse PSR machinery with the multiple-testing benchmark.
    return {"benchmark_sharpe": benchmark, "probability": probabilistic_sharpe(returns, benchmark)}


def _metric_sample(returns: list[float]) -> dict[str, float]:
    wealth = math.prod(1 + x for x in returns)
    years = len(returns) / TRADING_DAYS
    cagr = wealth ** (1 / years) - 1 if years and wealth > 0 else -1.0
    mdd, _, _ = max_drawdown(returns)
    return {"cagr": cagr, "sharpe": sharpe(returns) or 0.0, "max_drawdown": mdd}


def block_bootstrap(returns: list[float], iterations: int, block_size: int, seed: int) -> dict:
    rng, n = random.Random(seed), len(returns)
    results = {key: [] for key in ("cagr", "sharpe", "max_drawdown")}
    for _ in range(iterations):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n)
            sample.extend(returns[(start + j) % n] for j in range(block_size))
        metrics = _metric_sample(sample[:n])
        for key, value in metrics.items():
            results[key].append(value)
    return {key: {"p05": _quantile(vals, .05), "median": _quantile(vals, .5), "p95": _quantile(vals, .95)} for key, vals in results.items()}


def monte_carlo(returns: list[float], iterations: int, seed: int) -> dict:
    rng, n = random.Random(seed), len(returns)
    mdds, finals = [], []
    for _ in range(iterations):
        sample = rng.choices(returns, k=n)
        mdds.append(max_drawdown(sample)[0])
        finals.append(math.prod(1 + x for x in sample))
    return {"max_drawdown": {"p05": _quantile(mdds, .05), "median": _quantile(mdds, .5), "p95": _quantile(mdds, .95)},
            "final_equity": {"p05": _quantile(finals, .05), "median": _quantile(finals, .5), "p95": _quantile(finals, .95)}}


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] if lo == hi else ordered[lo] * (hi - position) + ordered[hi] * (position - lo)


def optional_tests(returns: list[float]) -> dict:
    result = {"ljung_box": {"available": False}, "adf": {"available": False}}
    try:
        from statsmodels.stats.diagnostic import acorr_ljungbox
        from statsmodels.tsa.stattools import adfuller
        lag = min(10, max(1, len(returns) // 5))
        lb = acorr_ljungbox(returns, lags=[lag], return_df=True).iloc[0]
        lb_stat, lb_p = _safe_number(lb["lb_stat"]), _safe_number(lb["lb_pvalue"])
        result["ljung_box"] = {"available": lb_stat is not None and lb_p is not None, "lag": lag, "statistic": lb_stat, "p_value": lb_p}
        adf = adfuller(returns, autolag="AIC")
        adf_stat, adf_p = _safe_number(adf[0]), _safe_number(adf[1])
        result["adf"] = {"available": adf_stat is not None and adf_p is not None, "statistic": adf_stat, "p_value": adf_p}
    except Exception as exc:  # optional statsmodels installs may be version-incompatible
        result["reason"] = str(exc)
    return result


def analyze(dates: pd.Series, returns: list[float], trials: int, iterations: int, block_size: int, seed: int, split: float) -> dict:
    if len(returns) < 3:
        raise ValueError("at least three finite daily returns are required")
    mean, sd = st.fmean(returns), st.stdev(returns)
    skew = sum(((x - mean) / sd) ** 3 for x in returns) / len(returns) if sd else 0.0
    kurt = sum(((x - mean) / sd) ** 4 for x in returns) / len(returns) if sd else 3.0
    jb = len(returns) / 6 * (skew ** 2 + (kurt - 3) ** 2 / 4)
    wealth = math.prod(1 + x for x in returns)
    cagr = wealth ** (TRADING_DAYS / len(returns)) - 1 if wealth > 0 else -1.0
    mdd, dd_duration, dds = max_drawdown(returns)
    downside = [min(x, 0.0) for x in returns]
    downside_dev = math.sqrt(st.fmean(x * x for x in downside))
    losses = sorted(returns)
    var95 = _quantile(losses, .05)
    tail = [x for x in losses if x <= var95]
    gains_sum = sum(max(x, 0) for x in returns)
    losses_sum = -sum(min(x, 0) for x in returns)
    n_eff, autocorr = effective_sample_size(returns)
    cut = min(len(returns) - 2, max(2, int(len(returns) * split)))
    is_sr, oos_sr = sharpe(returns[:cut]), sharpe(returns[cut:])
    date_index = pd.DatetimeIndex(pd.to_datetime(dates).to_numpy())
    daily = pd.Series(returns, index=date_index)
    monthly = daily.groupby(date_index.to_period("M")).apply(lambda x: math.prod(1 + v for v in x) - 1)
    quarterly = daily.groupby(date_index.to_period("Q")).apply(lambda x: math.prod(1 + v for v in x) - 1)
    return {
        "sample": {"observations": len(returns), "start": str(pd.to_datetime(dates).min().date()), "end": str(pd.to_datetime(dates).max().date()), "trials_declared": trials},
        "performance": {"total_return": wealth - 1, "cagr": cagr, "annual_volatility": sd * math.sqrt(TRADING_DAYS)},
        "distribution": {"skewness": skew, "excess_kurtosis": kurt - 3, "jarque_bera": {"statistic": jb, "p_value": math.exp(-jb / 2)}},
        "risk_adjusted": {"sharpe": sharpe(returns), "sortino": mean / downside_dev * math.sqrt(TRADING_DAYS) if downside_dev else None, "calmar": cagr / abs(mdd) if mdd else None, "omega_zero": gains_sum / losses_sum if losses_sum else None},
        "risk": {"max_drawdown": mdd, "max_drawdown_duration_days": dd_duration, "ulcer_index": math.sqrt(st.fmean(x * x for x in dds)), "lake_ratio": sum(x < 0 for x in dds) / len(dds), "var_95": var95, "cvar_95": st.fmean(tail)},
        "significance": {"t_statistic": mean / (sd / math.sqrt(len(returns))) if sd else None, "effective_sample_size": n_eff, "autocorrelations": autocorr, "psr_vs_zero": probabilistic_sharpe(returns), "approximate_dsr": deflated_sharpe(returns, trials)},
        "stability": {"is_sharpe": is_sr, "oos_sharpe": oos_sr, "wfa_efficiency": oos_sr / is_sr if is_sr not in (None, 0) and oos_sr is not None else None, "positive_months": float((monthly > 0).mean()), "positive_quarters": float((quarterly > 0).mean())},
        "optional_tests": optional_tests(returns),
        "block_bootstrap": block_bootstrap(returns, iterations, block_size, seed),
        "monte_carlo": monte_carlo(returns, iterations, seed + 1),
    }


def markdown_report(report: dict) -> str:
    p, r, a, s = report["performance"], report["risk"], report["risk_adjusted"], report["significance"]

    def pct(value: float | None) -> str:
        return "unavailable" if value is None else f"{value:.2%}"

    def num(value: float | None) -> str:
        return "unavailable" if value is None else f"{value:.3f}"

    lines = ["# Portfolio Robustness Report", "", f"Period: {report['sample']['start']} to {report['sample']['end']} ({report['sample']['observations']} daily observations)", "", "## Core metrics", "", "| Metric | Value |", "|---|---:|",
             f"| CAGR | {pct(p['cagr'])} |", f"| Annual volatility | {pct(p['annual_volatility'])} |", f"| Sharpe | {num(a['sharpe'])} |", f"| Sortino | {num(a['sortino'])} |", f"| Calmar | {num(a['calmar'])} |", f"| Maximum drawdown | {pct(r['max_drawdown'])} |", f"| Ulcer index | {pct(r['ulcer_index'])} |", f"| Time underwater | {pct(r['lake_ratio'])} |", f"| 95% VaR | {pct(r['var_95'])} |", f"| 95% CVaR | {pct(r['cvar_95'])} |", "", "## Statistical validation", "", f"- t-statistic: {num(s['t_statistic'])}", f"- Effective sample size: {num(s['effective_sample_size'])}", f"- PSR vs zero: {pct(s['psr_vs_zero'])}", f"- Approximate DSR probability ({report['sample']['trials_declared']} declared trials): {pct(s['approximate_dsr']['probability'])}", f"- DSR benchmark Sharpe: {num(s['approximate_dsr']['benchmark_sharpe'])}", "", "## Stability and robustness", "", f"- IS Sharpe: {num(report['stability']['is_sharpe'])}", f"- OOS Sharpe: {num(report['stability']['oos_sharpe'])}", f"- WFA efficiency: {num(report['stability']['wfa_efficiency'])}", f"- Positive months: {pct(report['stability']['positive_months'])}", f"- Positive quarters: {pct(report['stability']['positive_quarters'])}", f"- Bootstrap CAGR 90% interval: {pct(report['block_bootstrap']['cagr']['p05'])} to {pct(report['block_bootstrap']['cagr']['p95'])}", f"- Monte Carlo MDD 90% interval: {pct(report['monte_carlo']['max_drawdown']['p05'])} to {pct(report['monte_carlo']['max_drawdown']['p95'])}"]
    for name in ("ljung_box", "adf"):
        test = report["optional_tests"][name]
        lines.append(f"- {name.replace('_', ' ').title()}: " + (f"p={test['p_value']:.4f}" if test.get("available") else "unavailable (install statsmodels)"))
    lines += ["", "## Method notes", "", "- Returns are decimal daily returns; risk-free rate and Omega threshold are zero.", "- WFA is a chronological holdout diagnostic, not parameter re-optimisation.", "- DSR is an approximation using the declared number of trials and effective sample size.", "- Block bootstrap preserves short-range dependence; Monte Carlo uses IID resampling.", ""]
    return "\n".join(lines)


def load_returns(path: str, date_column: str, return_column: str | None, equity_column: str | None) -> tuple[pd.Series, list[float]]:
    frame = pd.read_csv(path)
    if date_column not in frame:
        raise ValueError(f"missing date column: {date_column}")
    dates = pd.to_datetime(frame[date_column], errors="raise")
    order = dates.argsort()
    frame, dates = frame.iloc[order].reset_index(drop=True), dates.iloc[order].reset_index(drop=True)
    if return_column:
        if return_column not in frame:
            raise ValueError(f"missing return column: {return_column}")
        values = pd.to_numeric(frame[return_column], errors="coerce")
    elif equity_column:
        if equity_column not in frame:
            raise ValueError(f"missing equity column: {equity_column}")
        values = pd.to_numeric(frame[equity_column], errors="coerce").pct_change(fill_method=None)
    else:
        raise ValueError("specify --return-column or --equity-column")
    mask = values.notna() & values.map(math.isfinite) & (values > -1)
    return dates[mask].reset_index(drop=True), _finite(values[mask])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--date-column", default="date")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--return-column")
    source.add_argument("--equity-column")
    parser.add_argument("--trials", type=int, default=1, help="Total strategy/parameter trials considered")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--split", type=float, default=.7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-prefix")
    args = parser.parse_args()
    if not 0 < args.split < 1 or args.iterations < 1 or args.block_size < 1 or args.trials < 1:
        parser.error("split must be in (0,1); trials, iterations and block-size must be positive")
    dates, returns = load_returns(args.csv, args.date_column, args.return_column, args.equity_column)
    report = analyze(dates, returns, args.trials, args.iterations, args.block_size, args.seed, args.split)
    prefix = Path(args.output_prefix) if args.output_prefix else Path(args.csv).with_suffix("")
    json_path, md_path = prefix.with_name(prefix.name + "_robustness.json"), prefix.with_name(prefix.name + "_robustness.md")
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(markdown_report(report))
    print(f"Wrote {json_path}\nWrote {md_path}")


if __name__ == "__main__":
    main()
