# Train-Only Oracle Exit Residual Audit

**LOOKAHEAD / NON-DEPLOYABLE / NON-SCOREABLE.** Oracle entry and exit
choices inspect future prices. This is a mechanism diagnostic only; it
is not a strategy, Backtest Score or permission to open validation/OOS.

Records: 90; median entry delay 5.0 sessions; median oracle hold 27.0 sessions; median oracle return 13.02%.

| Causal state on close before oracle exit | Overall | Early fold | Late fold | Drop top 5 | Prior status |
|---|---:|---:|---:|---:|---|
| five_day_close_high | 84.4% | 84.6% | 84.2% | 84.7% | strength exit; near prior profit-taking/high rules |
| two_up_closes | 62.2% | 61.5% | 63.2% | 62.4% | strength exit; price-staircase analogue |
| down_close | 11.1% | 11.5% | 10.5% | 10.6% | weakness exit; directly tested family |
| below_sma10 | 5.6% | 5.8% | 5.3% | 5.9% | weakness exit; directly tested family |
| trailing_drawdown_5pct | 1.1% | 0.0% | 2.6% | 1.2% | giveback exit; trailing-stop family |
| gain_10pct | 57.8% | 59.6% | 55.3% | 55.3% | profit exit; target/scale-out family |

## Decision rule

A proxy is only hypothesis-generating if it appears before at least
60% of oracle exits in both chronological halves and after removing
the five largest oracle returns, and if its mechanism was not already
tested. No thresholds are searched or changed in this audit.

**No proxy qualifies.** The simple causal exit states either lack stable oracle coverage or belong to already rejected exit families.

Validation and best-available OOS were not accessed.
