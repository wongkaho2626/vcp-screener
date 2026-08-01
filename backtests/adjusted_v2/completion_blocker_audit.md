# Completion Blocker Audit — 2026-08-01

## Decision

The goal is **not complete** and cannot be honestly completed from the data and
credentials currently available in this workspace. This is separate from the
strategy failures: no frozen candidate has passed its discovery gate. Trial
288's date-aligned reconstruction produced only 4.82% net CAGR, while the
user-requested 2022–2026 exploratory replay produced 0.05%. Even if a later signal
rule passed, the required Backtest Score above 80 could not be established on
the requested untouched OOS because survivorship bias remains unresolved.

## Third resumed-goal audit

The same external condition was rechecked for the third consecutive resumed
goal turn on 2026-08-01:

- no CRSP, WRDS, Nasdaq Data Link or Quandl credential variables are present;
- no new 2000–2005 CRSP/WRDS-equivalent daily price or security-master files
  were found in the workspace;
- no frozen specification has `open_formal_validation: true`, a formal
  validation pass, or an authorised untouched-OOS run;
- the latest predeclared Trial 324–327 family failed its train gate with 80
  trades, 0.07% CAGR, 0.062 Sharpe, 1.025 profit factor, -2.12% maximum
  drawdown and -0.29% CAGR after removing the five largest winners.

The itemised disposition of every hard condition is preserved in
`completion_matrix_2026-08-01.md`. This audit therefore confirms a repeated
external-state impasse, not a strategy success.

## Repeated blocking condition

1. The intended untouched OOS is 2000-01-01 through 2005-12-31. No daily price
   file for that interval, CRSP extract, WRDS extract, or equivalent security
   master exists anywhere in the repository.
2. No `WRDS_USERNAME`, `WRDS_PASSWORD`, `CRSP_USERNAME`, `CRSP_PASSWORD`,
   `NASDAQ_DATA_LINK_API_KEY`, or `QUANDL_API_KEY` is configured in the current
   process. Only presence/absence was checked; no secret value was printed.
3. The existing legacy PIT reconstruction covers 2006–2015, not 2000–2005. It
   retains 443 symbols but has only **69.74% member-day coverage**, ranging from
   60.7% in 2006 to 77.4% in 2015. It also drops corrupt or inadequately covered
   legacy/delisted names. Evidence: `backtests/pullback_oos/pit/coverage.json`.
4. The stronger 2016–2026 reconstruction has 91.39% member-day coverage but has
   already supplied discovery/internal-holdout evidence and therefore cannot be
   relabelled as untouched OOS. Evidence:
   `backtests/pullback_pit2016/coverage.json`.
5. The backtest-analyst rubric caps a result at **20/100** when lookahead or
   survivorship bias is confirmed and unresolved. The repository's own
   prespecified PIT addendum requires at least 90% recovered member-days to
   lift its survivorship cap; 70–90% remains partially mitigated and below 70%
   leaves the cap in force. Evidence: `backtests/pullback_oos/pit_addendum.md`
   and `backtests/pullback_oos/verification_report.md`.
6. Public-source recovery was attempted after this audit was first written:
   Yahoo failed most sampled inactive tickers; a small delisted archive
   overlapped only MEL; and the 7,195-stock CC0 Huge Stock Market archive
   recovered just **58.35%** of 2000–2005 S&P member-days (404/640 symbols).
   The Quandl WIKI universe matched 415/640 symbols. Both were rejected before
   strategy outcomes. Evidence:
   `backtests/data_source_audit/public_oos_coverage.{json,md}`.

This same missing-data condition has recurred throughout the research. It is
now a genuine external-state impasse: additional buy/sell hypotheses can change
returns, but cannot remove a score cap caused by absent OOS observations.

The user subsequently directed an existing-data run without relying on the
survivorship cap. That exploratory replay failed independently: raw score
25/100, 89 trades and 0.05% net CAGR. It does not alter the external-data
blocker or the completion definition.

## Minimum acceptable unblock dataset

Provide licensed access or repository-local files covering at least 2000–2005
with all of the following:

- daily raw or consistently adjusted OHLCV for active **and inactive/delisted**
  U.S. common stocks;
- stable security identifiers plus ticker/name-change history;
- point-in-time S&P 500 additions and removals, with effective dates;
- splits, distributions and delisting prices/returns sufficient to construct a
  consistent adjusted execution series;
- at least 90% measured S&P 500 member-day coverage, including crisis-era exits;
- SPY only as benchmark, never as a tradable fallback.

The loader must then validate identifiers, adjustment parity, delisting exits,
duplicate bars, gaps, membership-on-signal and membership-on-fill before any
frozen OOS specification is opened.

## Viable external sources

- [CRSP US Stock & Indexes data guide](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-data-descriptions-guide-crspaccess/)
  documents daily history from 1925 and explicit delisting price/return fields.
  It is the cleanest fit for this audit.
- [WRDS subscription information](https://wrds-www.wharton.upenn.edu/pages/about/what-wrds/)
  states that CRSP requires a separate institutional data licence in addition
  to WRDS access.
- [Norgate Data](https://norgatedata.com/index.php/pricing/) describes its U.S.
  equities product as survivorship-bias-free, subscription-only, and hosted in
  a Windows-local proprietary database; its
  [content table](https://norgatedata.com/data-content-tables.php) says delisted
  U.S. stocks require Platinum or Diamond coverage. Export and identifier/
  membership compatibility would need validation before use.

## Resume contract

Resume the goal when either:

1. working CRSP/WRDS credentials and entitlement are available in the runtime;
   or
2. the user supplies a survivorship-safe 2000–2005 daily dataset and security
   master satisfying the fields above.

On resume, first ingest and audit coverage without inspecting strategy returns.
Only after a candidate passes discovery and formal validation should its frozen
specification be run once on the untouched OOS. The success definition remains
unchanged: same frozen stocks-only strategy, score above 80, net CAGR at least
20%, and at least 30 independent OOS trades.
