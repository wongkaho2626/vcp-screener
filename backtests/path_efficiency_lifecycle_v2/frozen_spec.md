# Trial 334–339 — Signed Path-Efficiency VCP Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

Prior momentum rules measured only endpoint returns. Two stocks can have the
same ten-session return even when one advances persistently and the other
whipsaws around its starting price. The latter is more likely to trigger a VCP
hard stop or surrender gains. No prior repository experiment used the path of
intermediate closes to distinguish these states.

The declared hypothesis is that a still-valid VCP becomes buyable when its
ten-session price path changes from noisy to directionally efficient above its
pivot and SMA20, and should be sold when directional efficiency turns
non-positive or the SMA20 trend fails.

## Frozen causal rule

For close index `t`, define signed ten-session efficiency as:

```text
(close[t] - close[t-10]) /
sum(abs(close[i] - close[i-1]) for i=t-9..t)
```

The value is in `[-1, +1]`; zero is used if the denominator is zero. For each
point-in-time eligible daily VCP setup:

1. enter when signed efficiency crosses from `<= +0.30` on the preceding
   available setup row to `> +0.30` on the current close;
2. additionally require the current close to be strictly above both the frozen
   VCP pivot and the causal SMA20;
3. fill at the next session's open;
4. exit at the next open after the first later close whose signed efficiency is
   `<= 0` **or** whose close is below causal SMA20;
5. require another fresh `<= +0.30` to `> +0.30` crossing before re-entry and
   allow at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
A setup is invalid after a close below its frozen pattern stop. Every feature
ends at the signal/exit close and every scheduled fill occurs no earlier than
the next open. No future row, future return, SPY value or future universe state
is used.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
capital, ten-position/name/sector/ADV constraints, 8% maximum risk, commission,
slippage, cash treatment and all other portfolio controls remain unchanged.
SPY is benchmark-only and cannot be held.

The outcome-free density check was run before this freeze and inspected only
signal counts, not future returns: the fixed +0.30 rule emitted 111 train
signals before portfolio rejections. The check also reported +0.20 and +0.40
counts for feasibility only; neither alternative may replace the frozen +0.30
primary result after outcomes.

Count the ten-session efficiency horizon, +0.30 crossover, joint pivot/SMA20
entry confirmation, efficiency-zero/SMA20 exit, fresh reset requirement and
three-attempt lifecycle as six new multiplicity units, raising the declared
total from 333 to 339.

## Sequential gate

Evaluate 2016-07-01 through 2018-06-30 train first. Train requires all of:

- at least 60 completed trades;
- net CAGR at least 10%;
- Sharpe at least 0.75;
- profit factor above 1.20;
- MDD better than -15%;
- positive expectancy after removing the five largest trades.

Only a full train pass permits the unchanged rule to access the already-used
2020–2021 internal discovery holdout. That holdout requires at least 60 trades,
net CAGR at least 15%, and the same quality gates before any separate formal
validation specification may be frozen. Formal validation and untouched OOS
remain sealed otherwise.
