# Public Untouched-OOS Data Coverage Audit

Period: 2000-01-01 through 2005-12-31

## Result

- Huge Stock Market archive: 404/640 symbols; **58.35%** member-day coverage.
- Per-year coverage: 2000 51.52%, 2001 55.25%, 2002 57.38%, 2003 59.64%, 2004 60.62%, 2005 65.56%.
- Quandl WIKI ticker list: 415/640 symbols (64.84%).

**Decision: REJECT.** The tested archive is below the prespecified 90% member-day threshold. It also supplies ticker-keyed adjusted OHLCV, not permanent identifiers or explicit delisting returns, so passing coverage would still require a separate identity/corporate-action audit.

Archive SHA-256: `d9317c8fb2d63b9b00db5f933b6c9639d2bf7ea3b918169bb5cec5903dce85a1`
