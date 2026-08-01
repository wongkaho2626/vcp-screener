# Prespecified train-only family — constructive pivot retest

**Declared:** 2026-08-01 before implementing or computing any variant result.
This family consumes five trials (198-202). It is discovery only; 2022-2026
validation is inaccessible to the selector.

## Mechanism

The frozen pivot-retest entry improved recent PIT results but is statistically
weak and outlier-dependent. Its rule accepts any pivot touch-and-hold close,
including weak candles and breakout paths showing adverse-selection urgency.
A constructive retest should show either orderly breakout execution, demand on
the retest bar, or prompt confirmation that the pivot actually became support.

This is narrower than previously rejected families: it is not a generic
trend/RS/score/volume gate, an MA-support rule, or the rejected rebreak above
the entire breakout-to-pullback high. All features are specific to the frozen
pivot and retest event.

## Five frozen train cells

All cells use the frozen pivot-retest v2 rule, next-open fills, unchanged
portfolio constraints, baseline costs and exits. Only the stated entry timing
or entry veto differs.

1. `baseline`: first pivot touch with close >= pivot, window 15.
2. `breakout_no_gap_1pct`: baseline, but veto if breakout-session open is
   >=1.0% above the prior close. The threshold is inherited from the prior
   gap experiment; it is not fitted here.
3. `bullish_retest`: the first touch-and-hold bar must also close above its
   prior session close; otherwise reject the setup.
4. `strong_close_clv60`: first touch-and-hold bar must close in the top 40% of
   its own high-low range (`CLV >= 0.60`); otherwise reject.
5. `retest_high_confirm3`: after the first touch-and-hold, require within three
   sessions a close strictly above that retest bar's high; buy next open. A
   close below pattern stop invalidates. Unlike old `rebreak`, the reference
   is only the retest candle high, not the full post-breakout high.

All close-derived conditions execute no earlier than the following session.
`forward_outcome` is forbidden.

## Data and selection

- Discovery/train only: 2016-07-01 through 2021-12-31, PIT membership gated.
- Same 91.31%-coverage PIT data and fixed USD100k portfolio constraints.
- A non-baseline cell is eligible only if it has >=25 train trades, positive
  CAGR, Sharpe above baseline, PF >1.2, and **drop-top-5 expectancy >0**.
- Select the eligible cell with highest train Sharpe. Tie within 0.05 goes to
  the simpler cell in numbered order.
- If no non-baseline cell qualifies, close the family without reading
  validation. No threshold substitution or conjunction of cells.

## After selection

Freeze the selected rule in a separate spec before a single validation run.
Only then run relevant neighbouring sensitivity (CLV 0.5/0.7, confirmation
window 2/5, or gap 0.5/2.0) as diagnostics, never replacements. Validation and
untouched-OOS gates remain unchanged: score >80, net CAGR >=20%, >=30 trades
and all statistical/robustness requirements.
