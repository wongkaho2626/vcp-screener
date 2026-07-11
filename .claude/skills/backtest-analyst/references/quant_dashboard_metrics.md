# Professional Quant Dashboard — Metric Formulas

Full reference for the "balanced institutional dashboard" metric set. Organised by
category to match Phase 2 / Phase 6 of SKILL.md. Load this file when the user wants
the complete metric panel, not just the core checklist.

---

## Performance

| Metric | Formula | Notes |
|---|---|---|
| **Total Return** | `(end_value / start_value) - 1` | Simple cumulative return over full period |
| **CAGR** | `(end_value/start_value)^(252/n_days) - 1` | Annualised geometric growth rate |
| **Annual Return (arithmetic)** | `mean(daily_returns) * 252` | Contrast with CAGR — diverges when volatility is high (variance drag) |
| **Monthly Return** | Resample daily returns to monthly compounding: `Π(1+r_daily) - 1` per month | Report as a table or heatmap by calendar month/year |

## Risk

| Metric | Formula | Notes |
|---|---|---|
| **Annualised Volatility** | `std(daily_returns) * sqrt(252)` | Use sample std (ddof=1) |
| **Maximum Drawdown (MDD)** | `min[(equity_t - running_max_t) / running_max_t]` | Report magnitude + start/trough/recovery dates |
| **Value at Risk (VaR)** | 5th (or 1st) percentile of the return distribution, historical or parametric: `mean - z*σ` | State confidence level and method (historical vs parametric vs Cornish-Fisher) |
| **Conditional VaR / Expected Shortfall (CVaR)** | `mean(returns | returns <= VaR)` | Average loss in the tail beyond VaR — always ≥ VaR in magnitude |
| **Downside Deviation** | `sqrt( mean( min(r_i - MAR, 0)^2 ) )` | MAR = minimum acceptable return (often 0 or risk-free rate); only penalises sub-MAR returns |
| **Ulcer Index** | `sqrt( mean(DD_t^2) )` | DD_t = % drawdown at time t; penalises depth AND duration of drawdowns |

## Risk-Adjusted

| Metric | Formula | Notes |
|---|---|---|
| **Sharpe Ratio** | `(R_p - R_f) / σ_p` (annualised) | Flag > 3 on daily-frequency data as suspect |
| **Sortino Ratio** | `(R_p - R_f) / DownsideDeviation` | Only penalises downside vol |
| **Calmar Ratio** | `CAGR / |Max Drawdown|` | Typically computed over trailing 3 years in industry use |
| **MAR Ratio** | `CAGR / |Max Drawdown|` (full sample period) | Same formula as Calmar but uses the full backtest period instead of trailing 3yr — state which one you're reporting |
| **Information Ratio** | `(R_p - R_b) / TrackingError` | Requires a benchmark series; measures skill per unit of active risk |
| **Omega Ratio** | `Σ max(r_i - θ, 0) / Σ max(θ - r_i, 0)` | θ = threshold return (often 0); probability-weighted gains vs losses |
| **Sterling Ratio** | `CAGR / (avg(|Top-N Drawdowns|) - 10%)` | N commonly = 3; the -10% adjustment is the classic convention, some implementations omit it — state which variant used |
| **Burke Ratio** | `CAGR / sqrt( Σ DD_i^2 )` | Uses sum of squared drawdowns (only the distinct drawdown troughs, not every bar) — penalises large drawdowns more than Sterling but less punitively than Ulcer-based measures |

## Trade Statistics

| Metric | Formula | Notes |
|---|---|---|
| **Profit Factor** | `Gross Profit / Gross Loss` (Gross Loss as positive number) | > 1.5 decent, > 2 strong; < 1 is a losing system |
| **Win Rate** | `winning_trades / total_trades` | Meaningless without Payoff Ratio alongside it |
| **Average Win** | `mean(profit of winning trades)` | |
| **Average Loss** | `mean(|loss| of losing trades)` | Report as positive magnitude |
| **Payoff Ratio** | `Average Win / Average Loss` | Also called Win/Loss Ratio |
| **Expectancy** | `(WinRate * AvgWin) - ((1-WinRate) * AvgLoss)` | Expected $ (or R-multiple) per trade; must be > 0 |
| **Kelly Fraction** | `W - (1-W)/R` | W = win rate, R = Payoff Ratio; gives the theoretically optimal bet fraction — always report a fractional Kelly (e.g. 25–50%) as the practical recommendation, never full Kelly |

## Distribution

| Metric | Formula | Notes |
|---|---|---|
| **Skewness** | `E[(r-μ)^3] / σ^3` | Negative skew = large infrequent losses (common in short-vol / mean-reversion strategies) — a key red flag |
| **Excess Kurtosis** | `E[(r-μ)^4] / σ^4 - 3` | > 0 = fat tails vs normal distribution |
| **Tail Ratio** | `|95th percentile return| / |5th percentile return|` | > 1 means right tail (gains) fatter than left tail (losses) — favourable |

## Portfolio (requires a benchmark or multi-asset context)

| Metric | Formula | Notes |
|---|---|---|
| **Alpha** | `R_p - [R_f + Beta*(R_m - R_f)]` (CAPM) | Annualise consistently with Beta's estimation window |
| **Beta** | `Cov(R_p, R_m) / Var(R_m)` | Regression slope of strategy returns on benchmark returns |
| **Tracking Error** | `std(R_p - R_b)` (annualised) | Dispersion of active returns vs benchmark |
| **Correlation** | `Corr(R_p, R_b)` (Pearson) | Report alongside Beta — low correlation + positive alpha is the ideal diversifier profile |
| **Diversification Ratio** | `(Σ w_i * σ_i) / σ_portfolio` | Only applicable to multi-asset/multi-strategy books; > 1 indicates diversification benefit, higher is better |

## Statistical Validation

| Metric | Formula | Notes |
|---|---|---|
| **t-statistic** | `mean(r) / (std(r)/sqrt(n_eff))` | Use effective sample size (autocorrelation-adjusted), not raw n |
| **Probabilistic Sharpe Ratio (PSR)** | See `statistical_tests.md` | Bailey & López de Prado (2012) |
| **Deflated Sharpe Ratio (DSR)** | See `statistical_tests.md` | Corrects for multiple-trial selection bias |
| **Bootstrap Confidence Intervals** | Resample returns (or trades) with replacement, N=1,000–10,000 iterations; recompute the statistic each time; report the 5th/95th percentile of the resampled distribution | Apply to Sharpe, CAGR, Max Drawdown, or any metric where the analytic sampling distribution is unclear or non-normal. Block-bootstrap (not iid resampling) if returns are autocorrelated |

---

## Suggested Full Dashboard Table Order

When the user asks for the "full dashboard" or "professional quant dashboard," present it in this order (matches how most institutional tearsheets are organized):

```
Performance → Risk → Risk-Adjusted → Trade Statistics → Distribution → Portfolio → Statistical Validation
```

Omit the Portfolio category if no benchmark/multi-asset context is available, and omit Trade
Statistics if the input is a returns series rather than a trade log — state explicitly which
categories were skipped and why rather than silently dropping them.
