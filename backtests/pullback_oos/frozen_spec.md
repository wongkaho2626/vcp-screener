# Frozen spec — Pre-2016 out-of-sample replication of the MA20 pullback entry

**Declared:** 2026-07-18, before any pre-2016 detection or trade result was
computed. Nothing below may change after results are seen; any post-hoc
observation goes in a clearly-labelled "hypothesis-generating" section.

## Hypothesis

The shipped MA20 pullback-entry overlay (validated 2016–2026: +1.36 pp paired
vs breakout entry, t 3.13, replicated on R2K) **replicates on 2006–2015 S&P
data that no experiment in this repo has ever touched**.

- **Declared direction (one-sided):** paired Δ (pullback excess − breakout
  excess, same detection) > 0.
- **Success:** pooled paired Δ > 0 with t(Δ) ≥ 2, same sign in both folds,
  surviving trims.
- **Failure to replicate:** pooled Δ ≤ 0, or |t| < 2, or fold sign-flip.

## Why this experiment

The programme's closing verdict requires "new data + a new predeclared
hypothesis". `SP500_Historical_Data.csv` reaches back to 1999; all ~180+ prior
trials used only 2016–2026. The 2006–2015 decade is genuinely unseen data for
this pipeline, available offline. The pullback overlay is the only shipped
positive claim awaiting validation on data it was not developed on.

## Frozen rule (all values = shipped defaults, zero re-tuning)

1. **Detection**: `scripts/backtest_vcp.py` frozen defaults — stride 5d,
   lookback 120d, outcome 60d, min-contractions 2, T1 depth ≥ 10%,
   contraction ratio ≤ 0.70, breakout volume ratio 1.5, `--limit 0`,
   `--years 10`, run against the CSV truncated at **2015-12-31** (anchors the
   as-of walk at end-2015 ⇒ scan ≈ Feb-2006 → Dec-2015).
2. **Breakout leg**: breakout-bar close, skipped if extension > 5% above
   pivot (`max_extension_pct=5.0`) — identical to `trade_simulator` rule.
3. **Pullback leg**: `plan_pullback_entry(..., window=15, ma_period=20)` —
   first post-breakout bar whose low touches SMA20 and whose close holds it;
   close below the pattern stop while waiting kills the setup.
4. **Exits (both legs, identical)**: `simulate_exit` — hard stop
   max(pattern stop, entry − 8%) + 60-bar timeout.
5. **Metric**: per-trade excess vs the synthetic equal-weight benchmark
   (`csv_client` "SPY") over the trade's own holding dates. Primary statistic:
   **paired Δ on detections where both legs traded.** Secondary (context
   only): per-leg mean excess, fill rate, missed-trade cost.
6. **Costs**: both legs are one round trip on the same name ⇒ 10–100 bps/side
   costs cancel *exactly* in the paired Δ. The unpaired fill-rate asymmetry is
   reported separately; cost stress applies only to absolute (context) legs.

## Robustness bar

- **Fold split**: entry date 2006-01-01…2010-12-31 vs 2011-01-01…2015-12-31
  (declared here; contains the 2008–09 bear — a regime no prior fold had).
- **Trims**: drop top-5 and top-10 paired Δ; sign must hold.
- **Cross-universe**: NOT runnable — no pre-2016 R2K price CSV exists.
  Recorded as a limitation; the 2016–2026 S&P + R2K result is the
  cross-period/cross-universe counterpart of this test.

## Multiplicity statement

~180+ strategy trials have touched this price history overall, but none
touched pre-2016 bars. The tested rule is the winner of the original 4-variant
pullback scan (pivot-15d, pivot-30d, MA10, MA20), so this replication carries
a selection-of-winner discount: a lone p ≈ 0.05 would be weak; the bar is
t ≥ 2 with fold and trim stability. Only the MA20 variant is evaluated —
the other three variants are NOT run, to avoid a new search.

## Data caveats (declared up front)

- Survivorship: the CSV holds ~2026 constituents; pre-2016 the bias is worse
  than in-sample (names chosen up to 20y later). The **paired** design cancels
  most of it (both legs trade the same surviving names), but absolute excess
  numbers are optimistic ceilings and are context only. Analyst survivorship
  cap (20) applies to any deployability claim, not to the paired replication
  verdict.
- Benchmark is the synthetic equal-weight index of the same universe, not
  tradable SPY — harsher than real SPY (equal-weight of eventual survivors).
- Close-based fills, no slippage model beyond the cost note above.

## Give-up criteria (no iteration allowed on these)

If the paired Δ fails (≤ 0, |t| < 2, or fold sign-flip): record
"failure to replicate out-of-sample" — do NOT try other MA periods, windows,
tolerances, date ranges, or sub-samples. One evaluation round of
backtest-analyst on the declared outputs; further rounds only for missing
metrics or actual code bugs.
