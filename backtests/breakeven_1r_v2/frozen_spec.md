# Frozen specification — pivot-retest plus 1R break-even stop v2

**Declared:** 2026-08-01, before implementation or results. Trial 197.

## Hypothesis

The pivot-retest entry is causal and improves recent PIT performance, but its
validation expectancy is carried by a few large winners. A position that has
closed at least one initial risk unit above entry has demonstrated follow-
through; allowing it subsequently to become a full initial-stop loss is an
avoidable left-tail leak. After the first close at +1R, raise the resting stop
to the cost-adjusted entry price starting the next session. This should reduce
round-trip losses while leaving unlimited upside and the 60-bar timeout intact.

This rule is distinct from rejected percentage/ATR trailing stops, fixed profit
targets, MA-break exits and scale-outs: it makes one irreversible structural
ratchet, takes no profit, and never trails above entry.

## Frozen signals

- Buy signal: exact frozen pivot-retest v2 rule (post-detection causal breakout,
  pivot touch-and-hold within 15 sessions, next-open entry).
- Initial risk `R = cost-adjusted entry - initial stop`, where initial stop is
  unchanged `max(final-contraction low, entry*0.92)`.
- At a session close `>= entry + R`, arm break-even. The entry-price stop is
  active from the following session only. If that session gaps below entry,
  fill at its open; otherwise a touch fills at entry, with existing sell cost.
- Before activation, initial resting stop is unchanged. After activation, stop
  never moves again. The unchanged 60-bar time exit still applies.
- All other sizing, cash, maximum positions, sector/name/ADV limits and
  5+5 bps per-side cost model remain fixed. No leverage; SPY benchmark-only.

## Split, PIT requirements and OOS lock

Train 2016-07-01..2021-12-31; validation 2022-01-01..2026-06-30; sealed
untouched OOS 2000-01-01..2005-12-31. Use membership-gated point-in-time S&P
500 stocks and require >=90% member-day coverage. Segments run independently.

Open OOS once only if validation simultaneously has net CAGR >=20%,
preliminary Backtest Score >80, >=30 trades, positive Sharpe/Sortino/Calmar,
PF>1.2, and train/validation same-sign Sharpe with efficiency >0.5. Otherwise
close the hypothesis; no retuning.

## Prespecified robustness

2x/5x/10x costs; neighbouring activation thresholds 0.75R and 1.25R as
diagnostics only; anchored folds; block bootstrap; trade Monte Carlo;
drop-top-5/10; PSR/DSR using 197 trials; MDD, Sharpe, Sortino, Calmar, PF,
trade count and activation/exit-reason counts. Frozen 1R cell alone decides.

Final success still requires the identical frozen strategy on untouched OOS
to score >80, earn net CAGR >=20%, and execute >=30 independent trades.
