# Frozen specification — pivot-retest with pivot-failure exit v2

**Declared:** 2026-08-01 before implementation/results. Trial 203.

## Hypothesis

The pivot-retest entry assumes the broken VCP pivot has changed from resistance
to support. If a later daily close falls back below that exact frozen pivot,
the entry thesis is invalid even when the wider 8%/contraction-low stop has not
been reached. Exiting at the next open should cut failed retests earlier,
release fixed portfolio slots, and preserve the unlimited winners that made
break-even/trailing exits harmful.

This is not an MA-break exit, percentage trail, profit target, scale-out or
arbitrary tighter initial stop. Its level is fixed by the original pattern and
never moves.

## Frozen rule

- Entry: exact baseline pivot-retest v2 (15-session window, next-open fill).
- Store the as-of-date pivot with the position.
- Starting after entry, the first close strictly below the frozen pivot creates
  a sell signal; exit at the following session's open, including sell costs.
- Resting initial hard stop remains active and takes precedence intraday; the
  60-bar time exit remains. No same-close fill and no retroactive use of lows.
- Original USD100k, Edge sizing, maximum positions, cash, name/sector/ADV
  limits and 5+5 bps per-side costs are unchanged. Stocks-only PIT S&P 500;
  SPY benchmark-only.

## Sequential gate

1. Train only (2016-07-01..2021-12-31). Proceed to validation only if >=30
   trades, net CAGR and Sharpe both exceed baseline pivot-retest, PF>1.2, and
   drop-top-5 expectancy remains >0.
2. Freeze this same rule (no parameter exists) and run validation once
   (2022-01-01..2026-06-30). Open untouched 2000-2005 OOS only if validation
   has score >80, net CAGR >=20%, >=30 trades, positive Sharpe/Sortino/Calmar,
   PF>1.2 and train/validation efficiency >0.5.

PIT member-day coverage must remain >=90%. Report costs 2x/5x/10x, folds,
bootstrap/Monte Carlo, trims, PSR/DSR at 203 trials and full risk/trade metrics.
Failure at either gate closes the hypothesis without reading the next set.
