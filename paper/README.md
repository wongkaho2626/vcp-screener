# Prospective paper-tracking of frozen VCP Strategy v1

This directory is the **only legitimate path to a Backtest Score ≥ 70**. The
historical CSV backtests are permanently capped at 20 by their unresolved
survivorship bias, and with 181 declared trials any new in-sample result is
indistinguishable from data mining. Prospective records clear both caps by
construction: signals are written down (and committed) before their outcomes
exist.

## Daily workflow

```bash
/opt/anaconda3/bin/python3 scripts/screen_vcp.py            # live screen
python3 scripts/paper_track.py record reports/vcp_screener_<stamp>.json
python3 scripts/paper_track.py mark                         # advance lifecycles (yfinance)
python3 scripts/paper_track.py report                       # stats + score readiness
git add paper/ && git commit -m "chore(paper): daily mark"  # notarise timestamps
```

Committing after each run matters: git history is the tamper-evident record
that every signal predated its outcome.

## Contract

- Rules are a verbatim restatement of `references/frozen_strategy_v1.md`
  (embedded in the ledger's `protocol` block). They must not change; a change
  is a v2 with a restarted clock.
- No interim tuning, filtering, or early stopping in response to accumulating
  results. Score evaluation happens only once every readiness gate passes
  (≥ 30 closed trades, ≥ 1 year of history).
- The primary metric is per-trade excess vs SPY over the holding dates, per
  house convention.

## Files

- `ledger.json` — append-only setup/trade ledger (committed).
- `reports/` — timestamped readiness reports (committed).
