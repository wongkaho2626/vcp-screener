# VCP Pullback-Then-Rebreak Verification Report

Generated 2026-07-14 from `outputs/rebreak_trade_log/VCP_Rebreak_Trade_Log.xlsx`
(source run: `rebreak_vcp_2026-07-11_000452.json`; 145 trades, 2016-03 → 2026,
S&P 500 CSV universe, commission + slippage included).

Rule under test: initial VCP breakout, MA20 touch-and-hold within 15 sessions,
then a close above the highest high from the initial breakout through the
pullback bar. Entry next session open; stop = max(pattern stop, 8% below fill);
otherwise exit after 60 sessions.

## Backtest Score: 10 / 100 — Reject

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 4 | 30 |
| B. Risk-Adjusted Performance | 2 | 25 |
| C. Robustness & Out-of-Sample | 4 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| **Raw total** | **10** | **100** |
| Caps applied | Survivorship bias unresolved → cap 20 (not binding) | |
| **Final score** | **10** | **100** |

The rebreak rule has no measurable edge: mean net return −0.11% per trade
(t = −0.10), profit factor 0.95, net P&L −$2,424. The flat-looking aggregate is
held up entirely by a handful of outliers and the 2016–2020 tape.

## Performance metrics

| Metric | Value | Status |
|---|---:|---|
| Trades | 145 | Adequate nominal count |
| Mean net return / trade | −0.11% | Fail |
| Median net return | −8.09% | Fail — typical trade rides to its stop |
| Win rate | 35.2% | Low |
| Average win / loss | +13.4% / −7.4% (payoff 1.80) | Coherent shape |
| Profit factor ($ P&L) | 0.945 | Fail (< 1.0) |
| Per-trade skew / excess kurtosis | +2.15 / +6.95 | Lottery-shaped |
| Mean holding period | 53 days | Matches 60-bar timeout design |

Exit decomposition: 82 stop exits average −8.2%; 62 timeout exits average
+10.4%. All profit comes from trades surviving to timeout; the stop-hit
majority (57%) fully consumes it.

## Statistical significance

| Metric | Value | Status |
|---|---:|---|
| t-statistic (mean return) | −0.105 | No evidence of edge; point estimate negative |
| PSR vs SR* = 0 (skew/kurt-adjusted) | 45.9% | Coin flip; fail |
| Bootstrap 90% CI on mean (5,000 resamples) | [−1.75%, +1.66%] | Straddles zero |
| DSR context | ≈ 0% | ≥ 181st variant tested (180 trials declared for frozen v1) |
| Effective sample | 145 trades / 10.3y, ~53-day overlapping holds | Borderline-adequate |

Framing caveat: these are **raw returns**; under the repo's excess-vs-SPY
convention a raw mean of ≈ 0 across the 2016–2026 bull tape implies decisively
negative excess expectancy. These numbers are an optimistic upper bound.

## Robustness

- **Fold split**: 2016–2020 n=56, mean +2.93%, t +1.53; 2021–2026 n=89, mean
  −2.02%, t −1.81. Sign flip across folds — fails the repo's robustness bar.
- **Outlier trim**: drop-top-5 → mean −1.57%, t −2.01; drop-top-10 → mean
  −2.42%, t −3.42. Without its best 5 trades the rule is significantly
  negative. Top winners (all timeout exits): MSTR +70%, EQT +43%, GILD +32%,
  TRMB +31%, GDDY +28%.
- **Edge Rank interaction**: Spearman(Edge, return) = −0.06 — sizing overlay
  would not rescue it; consistent with "overlays don't stack".
- **Cross-universe replication**: not run (no R2K rebreak log); moot given the
  above.

## Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent in reviewed design | Signal on close, next-open fill |
| Survivorship | Present, unresolved | Current-member-biased S&P 500 CSV |
| Data snooping | Present | Post-hoc variant after 180+ declared trials |
| Cost underestimate | Addressed | Two-sided commission + slippage in log |
| Liquidity | Addressed approximately | Entry ADV logged, well above position sizes |
| Bar alignment | Absent | Signal date ≠ entry date throughout |
| Regime overfit | Present | Positive only 2016–2020; negative after |

## Verdict

**10/100 — Reject.** Raw component total is 10 (t < 0, PSR < 50%, negative
expectancy, fold sign-flip, trim-fragile); the survivorship cap of 20 does not
bind. Scores below frozen v1 (20/100) because it lacks even v1's marginally
positive in-sample fold. Log as another entry-timing null — do not tune the
rebreak window, stop, or timeout in response to this result. The only
defensible paths remain survivorship-free data or a new predeclared hypothesis
on untouched/prospective data.
