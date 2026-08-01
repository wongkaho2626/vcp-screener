# Backtest Verification Report — immediate post-detection entry v2

Evaluated 2026-08-01 from the pre-result `frozen_spec.md`. Untouched
2000-2005 OOS was not opened because validation failed.

## Backtest Score: 12 / 100 — Reject (validation-only preliminary score)

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 7 | 30 |
| B. Risk-Adjusted Performance | 5 | 25 |
| C. Robustness & Validation | 0 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| **Raw / final** | **12 / 12** | **100** |

## Executive summary

Entering immediately after a VCP detection raises trade count and exposure but
confirms that the pattern itself is not a buy signal. On 344 validation trades,
net CAGR is **-1.36%**, Sharpe **-0.246**, PF **0.83**, expectancy **-0.47%**,
and MDD **-11.53%**. Train was essentially flat (CAGR +0.25%, Sharpe +0.08),
so train/validation signs reverse. Every validation gate except trade count
fails. OOS remains sealed.

## Performance and significance

| Metric | Train 2016H2-2021 | Validation 2022-2026 |
|---|---:|---:|
| Trades | 347 | 344 |
| Net CAGR | +0.25% | **-1.36%** |
| Total return | +1.40% | -5.94% |
| Sharpe / Sortino | 0.080 / 0.118 | **-0.246 / -0.327** |
| Calmar | 0.024 | -0.118 |
| MDD | -10.66% | -11.53% |
| Profit factor | 0.94 | **0.83** |
| Expectancy | -0.11% | **-0.47%** |
| Win rate / payoff | 38.6% / 1.49 | 31.7% / 1.78 |
| t-statistic | 0.19 | **-0.52** |
| PSR | 57.4% | **30.1%** |
| Approx. DSR (196 trials) | 0.49% | **0.05%** |

Validation block-bootstrap CAGR 90% interval is **-5.12% to +2.31%**
(median -1.40%). Positive months are 46.3%; lake ratio is 98.9% and the
longest drawdown lasts 1,051 trading days.

## Robustness

| Validation cost | CAGR | Sharpe | PF |
|---|---:|---:|---:|
| 1x | -1.36% | -0.246 | 0.83 |
| 2x | -1.90% | -0.354 | 0.85 |
| 5x | -3.91% | -0.765 | 0.70 |
| 10x | -7.22% | -1.452 | 0.51 |

The prespecified one-session delay is worse: 348 validation trades, CAGR
**-2.63%**, Sharpe **-0.574**, PF **0.79**. Drop-top-5 expectancy is -1.26%
(PF 0.54); drop-top-10 is -1.73% (PF 0.38). Failure is not caused by a single
parameter or outlier ordering.

## Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Signal is `as_of_date` close, fill next open; future outcome ignored and unit-tested. |
| Survivorship | Mitigated | PIT membership gate; 91.31% member-day coverage; 599 stocks plus real SPY benchmark. |
| Snooping | Penalised | Spec frozen before result; DSR uses 196 trials. |
| Costs / liquidity | Addressed | Two-sided baseline and stress costs; original ADV/name/sector/cash constraints fixed. |
| Regime instability | Present | Train near zero, validation negative; Sharpe sign reverses. |

## Verdict

**12/100 — Reject.** Immediate pre-breakout entry converts sparse exposure
into a larger negative-expectancy book. It independently confirms the repo's
established conclusion that default VCP detections are candidate-generation
events, not standalone buy signals. The sealed OOS was correctly not opened.
