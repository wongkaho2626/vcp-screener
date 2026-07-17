# VCP Index Forward-PE Experiment

Generated: 2026-07-15 17:14:27

Baseline (all trades) mean excess vs SPY: **-1.17%** — the no-filter row below must reproduce it exactly (sanity check).

Index forward P/E (bottom-up consensus, ~weekly) used two declared ways: (1) trailing-5y percentile as a market-valuation regime gate, (2) rel PE = stock trailing PE / index forward PE, cut at 1.5. No threshold sweep.

## Cohorts (excess vs SPY is the alpha test)

| Cohort | N | Mean excess | t | 95% CI | Excess win% | Mean ret | Win% | PF |
|---|---|---|---|---|---|---|---|---|
| all (no filter) | 285 | -1.17% | -1.83 | [-2.37, 0.07] | 35.40% | 1.37% | 44.90% | 1.31 |
| market pctile <= 50 (cheap mkt) | 90 | -1.65% | -1.61 | [-3.63, 0.34] | 30.00% | 0.44% | 41.10% | 1.09 |
| market pctile > 50 (dear mkt) | 195 | -0.94% | -1.17 | [-2.48, 0.69] | 37.90% | 1.81% | 46.70% | 1.42 |
| rel PE <= 1.5 | 244 | -1.07% | -1.58 | [-2.4, 0.28] | 36.90% | 1.42% | 44.30% | 1.32 |
| rel PE > 1.5 | 29 | 1.12% | 0.48 | [-3.01, 5.81] | 34.50% | 3.66% | 62.10% | 2.09 |
| rel PE undefined | 12 | -8.56% | -5.29 | [-11.35, -5.25] | 8.30% | -4.97% | 16.70% | 0.30 |

## Declared contrasts (Welch t)

| Contrast | N (a/b) | Mean a | Mean b | Welch t |
|---|---|---|---|---|
| cheap vs dear market (excess) | 90/195 | -1.65% | -0.94% | -0.54 |
| cheap vs dear market (raw ret) | 90/195 | 0.44% | 1.81% | -0.87 |
| rel PE <= 1.5 vs > 1.5 (excess) | 244/29 | -1.07% | 1.12% | -0.91 |

Spearman(rel PE, excess), n=273: **-0.052**

Spearman(market pctile, excess), n=285: **-0.024**

## PEG <= 2 vs > 2 within market-valuation halves

| Regime | N (a/b) | Mean PEG<=2 | Mean PEG>2 | Welch t |
|---|---|---|---|---|
| market pctile <= 50 | 58/15 | -0.64% | -4.96% | 2.08 |
| market pctile > 50 | 77/50 | 0.16% | -1.19% | 0.70 |

## Fold split (2021) — rel PE <= 1.5 vs > 1.5

| Fold | N (a/b) | Mean low rel PE | Mean high rel PE | Welch t |
|---|---|---|---|---|
| < 2021 | 81/13 | -1.43% | 2.86% | -1.07 |
| >= 2021 | 163/16 | -0.90% | -0.30% | -0.20 |

## Outlier trim — best gated cohort (rel PE > 1.5)

- full: n=29, mean 1.12%, t 0.48
- drop top 5: n=24, mean -3.37%, t -2.46

## Caveats

- Excess-vs-SPY is market-neutral by construction: a market-level valuation
  gate is structurally expected to be null on it (see breadth/vol/200DMA).
- rel PE mixes a trailing stock PE with a forward index PE; it is a
  detrending device, not a like-for-like valuation ratio.
- Vendor forward-PE history may be restated; treated as best-effort PIT.
- Raw-return rows are beta in a 2016–2026 bull tape, not edge.
