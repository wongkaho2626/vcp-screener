# Data Source: yfinance (Yahoo Finance)

The screener pulls all price and quote data from Yahoo Finance through the
[`yfinance`](https://pypi.org/project/yfinance/) library. **No API key is
required.** Install it once with `pip install yfinance`.

The client lives in `scripts/yf_client.py` (class `YFClient`) and exposes the
same method surface the pipeline was built against, so the calculators, scanner,
scorer, and report generators are unchanged.

## What comes from where

### 1. Index constituents (bundled snapshots)
Yahoo does not expose index membership, so each universe is read from a bundled
file rather than the network:

- **Files:** `scripts/data/sp500_constituents.json`,
  `scripts/data/russell2000_constituents.json`
- **Shape:** `[{symbol, name, sector, subSector}, ...]`
- **Used in:** Phase 1 (universe definition) and for name/sector labels in the report.
- **Selection:** `--index {sp500,russell2000,both}` (default `sp500`). `both`
  merges the two lists and de-duplicates the handful of symbols that appear in
  each. `--universe SYM ...` overrides with a custom list.

Class-share tickers are stored in Yahoo's hyphen form (e.g. `BRK-B`, `BF-B`).

**S&P 500 snapshot.** Large-cap, carries proper company names and GICS sectors.
Generated from the public `datasets/s-and-p-500-companies` CSV. Membership drifts
slowly (a few names a year).

**Russell 2000 snapshot.** ~1,980 small-cap symbols. This is a **symbol-only**
list: `name` mirrors the symbol and `sector` is `"Unknown"`, so Russell-only
names bucket under "Unknown" in the report's sector distribution (S&P labels are
never overwritten by these placeholders when `--index both` is used). The
Russell 2000 **reconstitutes every June**, so this list drifts more than the S&P
500 — refresh it before relying on it heavily. Delisted/renamed tickers simply
return no Yahoo data and are skipped by the pipeline.

**Refreshing the snapshots.** Use the bundled helper (needs internet; no key):

```bash
# Both indices
python3 scripts/refresh_constituents.py --index both

# Just one
python3 scripts/refresh_constituents.py --index sp500
python3 scripts/refresh_constituents.py --index russell2000

# Offline Russell fallback: hand it a manually downloaded IWM holdings CSV
python3 scripts/refresh_constituents.py --index russell2000 --russell-csv ~/IWM_holdings.csv
```

Sources: S&P 500 from the `datasets/s-and-p-500-companies` GitHub CSV; Russell
2000 from the iShares **IWM** ETF holdings file (IWM tracks the Russell 2000).
The refresh script keeps only equity holdings from IWM and drops cash/derivative
rows. If iShares changes its CSV layout or the domain is unreachable, download
the holdings CSV manually and pass `--russell-csv`.

### 2. Quotes (derived from history)
`get_batch_quotes(symbols)` issues **one** bulk `yf.download(period="1y")` call
for the whole list (yfinance threads and chunks internally), then derives each
quote from that history:

- `price` — latest close
- `yearHigh` / `yearLow` — max/min over the trailing ~252 sessions
- `avgVolume` — mean volume over that window (`volume` = latest session as a fallback)
- `name` / `sector` — from the bundled constituents snapshot
- `marketCap` — left at `0` in the bulk path (the screener never filters on it)

Crucially, the full histories fetched here are **cached in the client**, so
Phase 2 reuses them with no additional network round-trips.

### 3. Historical prices
`get_historical_prices(symbol, days)` returns
`{symbol, historical: [{date, open, high, low, close, adjClose, volume}, ...]}`,
**most-recent-first**. It serves from the batch cache when possible, otherwise
makes a single `yf.Ticker(symbol).history(...)` call.

Prices are fetched **unadjusted** (`auto_adjust=False`): `close` is the raw
session close (used for pivots and stops) and `adjClose` carries the
split/dividend-adjusted close.

## Request budget (default screen)

| Phase | Operation | Network calls |
|-------|-----------|---------------|
| 1 | Index constituents (S&P 500 / Russell 2000) | 0 (bundled files) |
| 1 | Bulk quote download (whole universe) | 1 bulk request |
| 2 | SPY 260-day history | 1 |
| 2 | Candidate histories | 0 (served from Phase-1 cache) |

Historical single-ticker mode (`--history --ticker SYM`) makes just **2**
requests: the ticker's history and SPY's.

## Notes & caveats

- Yahoo Finance is a free, unofficial data source. It occasionally rate-limits
  or returns short histories for thinly traded / recently listed names; the
  pipeline already tolerates fewer bars than requested and warns when the oldest
  part of a scan window is truncated.
- `marketCap` is `0` in cross-sectional output. If you need it, extend
  `YFClient` to populate it from `Ticker.fast_info` — but note that's one extra
  network call per symbol.
- No daily call cap or paid tier applies; there is no `--api-key` flag anymore.
