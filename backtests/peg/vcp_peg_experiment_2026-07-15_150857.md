# VCP Trailing-PEG Experiment

Generated: 2026-07-15 15:08:57

Baseline (all trades) mean excess vs SPY: **-1.17%** — the no-filter row below must reproduce it exactly (sanity check).

Trailing PEG at detection date, from free Yahoo data: PE = fill price / TTM street EPS (last 4 reported quarters, point-in-time by announcement date); growth = YoY change in TTM EPS. PEG bands are the textbook <=1 / <=2 / >2 cuts, declared up front. This is a *trailing* PEG — no historical forward estimates exist in free data.

## Data coverage

- insufficient_history: 3
- no_earnings_data: 1
- nonpositive_growth: 73
- nonpositive_ttm: 5
- ok: 200
- stale_history: 3

## Cohorts (excess vs SPY is the alpha test)

| Cohort | N | Mean excess | t | 95% CI | Excess win% | Mean ret | Win% | PF |
|---|---|---|---|---|---|---|---|---|
| all (no filter) | 285 | -1.17% | -1.83 | [-2.37, 0.07] | 35.40% | 1.37% | 44.90% | 1.31 |
| PEG defined | 200 | -0.79% | -1.09 | [-2.17, 0.7] | 37.50% | 1.31% | 45.50% | 1.30 |
| PEG <= 1 (cheap) | 82 | -0.65% | -0.51 | [-3.1, 1.94] | 32.90% | 1.45% | 42.70% | 1.32 |
| 1 < PEG <= 2 (fair) | 53 | 0.54% | 0.41 | [-1.94, 3.17] | 50.90% | 2.32% | 50.90% | 1.57 |
| PEG > 2 (expensive) | 65 | -2.06% | -1.81 | [-4.24, 0.24] | 32.30% | 0.31% | 44.60% | 1.07 |
| growth <= 0 (PEG undefined) | 73 | -0.97% | -0.69 | [-3.62, 1.86] | 34.20% | 2.59% | 47.90% | 1.61 |
| TTM EPS <= 0 (loss-maker) | 5 | -6.37% | -2.10 | — | 20.00% | -2.29% | 20.00% | 0.68 |
| no/stale/short data | 7 | -10.12% | -5.99 | [-13.06, -6.95] | 0.00% | -6.89% | 14.30% | 0.04 |

## Declared contrasts (Welch t on excess vs SPY)

| Contrast | N (a/b) | Mean a | Mean b | Welch t |
|---|---|---|---|---|
| PEG <= 2 vs PEG > 2 | 135/65 | -0.18% | -2.06% | 1.28 |
| PEG defined vs growth <= 0 | 200/73 | -0.79% | -0.97% | 0.11 |

Spearman(PEG, excess) on defined-PEG trades (n=200): **-0.054**

Spearman(TTM growth, excess) where growth defined (n=271): **0.079**

## Fold split (2021) — PEG <= 2 vs > 2

| Fold | N (a/b) | Mean cheap-ish | Mean expensive | Welch t |
|---|---|---|---|---|
| < 2021 | 49/19 | -1.69% | -2.27% | 0.28 |
| >= 2021 | 86/46 | 0.67% | -1.97% | 1.36 |

## Outlier trim — best PEG band (1 < PEG <= 2 (fair))

- full: n=53, mean 0.54%, t 0.41
- drop top 5: n=48, mean -1.55%, t -1.67

## Caveats

- Trailing PEG (realized growth), not the forward PEG practitioners quote;
  the two can disagree badly around earnings inflections.
- Yahoo street EPS is as-announced (point-in-time by event date) but the
  vendor may restate history; treat as best-effort PIT, not IBES-grade.
- Band cuts are conventional but the multiple-cohort table is still
  multiple testing; judge on the declared contrasts + fold + trim, not
  the single best cell.
- Excess-vs-SPY is market-neutral by construction; valuation regime
  effects on the index itself are invisible here.
