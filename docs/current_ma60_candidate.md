# Current MA60 Research Candidate

Status: **user-directed experimental override; validation failed**.

The canonical implementation is `scripts/current_ma60_candidate.py`. Frozen
historical trial scripts retain their original 20-session settings for exact
reproduction.

## Current buy rule

```python
stock_slope = stock_sma60_today / stock_sma60_10_sessions_ago - 1
spy_slope = spy_sma60_today / spy_sma60_10_sessions_ago - 1

condition = (
    stock_close > stock_sma60_today
    and stock_slope > 0
    and stock_slope > spy_slope
)
```

Buy only on `False -> True`, confirm after the close, and fill no earlier than
the next eligible ticker open. PIT S&P 500 membership is required on signal
and fill. The actual fill date must be inside the user-supplied calendar in
`backtests/ma60_period_gate_v2/frozen_spec.md`.

## Current exit

- Initial hard stop: 8% below raw entry open.
- Arm after a completed close reaches entry + 3R.
- Thereafter trail 24% below the highest completed close, active next session.
- No timeout.
- A finite calendar endpoint is inclusive. At the first subsequent ticker
  session outside every allowed window, sell at that session's open with
  `exit_reason=period_exit`. This opening liquidation takes precedence over an
  intraday hard/trailing-stop test on the same session.
- The final window beginning 2025-04-07 is open-ended, so it has no calendar
  exit until an end date is supplied.

## Evidence warning

Trial 569–572 selected slope10 on train, but validation exposure-matched excess
CAGR was -6.93% and drop-best-five expectancy was -1.08%. OOS remained sealed.
The exact calendar dates may also be post-hoc. This override records the user's
chosen research configuration; it is not evidence that the configuration is
tradeable or superior to the frozen 20-session incumbent.

## Regenerated performance

Trial 573 evaluated this exact combined specification. CAGR was 19.71% train,
16.61% validation, 15.34% on the contaminated best-available OOS partition and
16.39% full-period. Full exposure-matched excess CAGR was -2.96%. The raw
normalized Backtest Score was 82, but unresolved survivorship coverage and no
untouched OOS capped the final score at 20/100 (Reject). The report and all
trade/equity artifacts are under `backtests/current_ma60_candidate_v2/results/`.
