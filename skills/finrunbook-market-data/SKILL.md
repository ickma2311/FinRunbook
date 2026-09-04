---
name: finrunbook-market-data
description: Collect auditable price and volume history for FinRunbook, calculate returns, drawdowns and benchmark-relative performance, and attach the data to the run ledger. Use when a report needs market prices, valuation-date prices or trading/event context; not for issuer financial statements, trade execution or identifying buyers and sellers.
---

# FinRunbook Market Data

Supply market observations to the analytical skill, not a second investment
opinion. Yahoo via `yfinance` is the first adapter; the record and validation
contract are provider-neutral. This skill and its Python helper work without a
particular agent runtime or MCP server.

## Scope and inputs

- Confirm the issuer **and security** before choosing the exchange-specific
  ticker. A company name or ticker resemblance is not an identity check. Ask if
  the company, share class or listing is ambiguous; do not invent a public ticker
  for a private company.
- Resolve the interval, date window, currency, price basis, trading session and
  benchmark. Explain consequential defaults in the run. End dates are exclusive.
- Use daily `adj-close` for historical adjusted-return comparisons, with the
  provider's adjustment limitations disclosed. Use `close` when discussing a
  displayed price or intraday bars. Yahoo Close is not guaranteed historical
  as-traded pricing: split adjustments may already be present. Never label these
  calculations an independently reconstructed total return.
- Do not activate this skill just because a report concerns a public company.
  SEC/IR remain the sources for issuer financials and guidance. Price/volume
  observations do not identify sellers, demonstrate institutional net selling,
  or establish the cause of a price move.

## Collect into an existing run

Read [the data contract](references/data-contract.md) when interpreting results
or adding another adapter. From the FinRunbook repository root, use an existing
Python environment with the pinned optional dependency:

```bash
python3 -m pip install -r skills/finrunbook-market-data/requirements.txt
python3 skills/finrunbook-market-data/scripts/market_data.py \
  runs/<run-id> --symbols NVDA MSFT --benchmark SPY \
  --start 2025-01-01 --end 2026-01-01 --interval 1d \
  --price-basis adj-close
```

For intraday work select `--interval 5m --price-basis close`. Extended-session
bars require explicit `--include-extended`; default is regular session. The
helper does not silently switch basis, broaden dates, repair prices, retry
indefinitely or substitute another provider. `--max-age-hours` defines the
allowed endpoint gap (default 168 hours, not a real-time freshness guarantee).
Review the actual returned range: intraday retention and missing sessions can
limit coverage. No exchange-calendar completeness check is implemented.

The helper saves a new immutable JSON snapshot, then appends sources, exact
evidence locators, provider-reported facts, calculations and a `market_data`
receipt to `research-record.json`. Prior snapshots and source IDs are retained.
It invalidates old validation/editorial receipts; it does not regenerate or
publish the report. Normal success exits 0; a failed/empty/invalid series exits 1
after recording the failure. Configuration errors exit 2. Warnings must still
be inspected after exit 0. Concurrent run edits are not supported.

Inspect the snapshot and registered calculations before drafting. Same-day
daily bars and unfinished intraday bars are retained but excluded from summary
calculations. The closing-price return uses the first and last eligible bars
**actually returned**, not an assumed start-date close. A requested one-day
return therefore needs the previous session's close too. Drawdown is based on
the sampled closing prices, not the intraday peak-to-trough loss. Benchmark
returns use exact common timestamps, matching currency, timezone and basis;
there is no forward fill or FX conversion. Relative performance is a difference
in percentage points, not risk-adjusted alpha.

## Integrate and validate

Add this skill to `plan.selected_skills` with its purpose and inputs. Use the
new fact/calculation/source IDs in the report's presentation data, display the
observed date range and basis, and keep collection failures or coverage limits
visible. Preserve the router's report language; provider labels are not an
instruction to write the report in English.

After regenerating the report, run tone review and `finrunbook-validator`.
Its market-data checks verify snapshot hashes, quality flags, calculation
recomputation and ledger mappings. These checks cannot independently prove
Yahoo's accuracy or causal explanations. A failed required batch blocks final
delivery. After a successful replacement, a failed batch may be marked
`required: false` with an `exclusion_reason`, but only when no material claim or
calculation relies on it. Never delete the failed attempt to manufacture a pass.

## Data-use boundary

`yfinance` is an unofficial client, not a Yahoo data license. Its maintainers
describe the Yahoo API as intended for personal use. Do not treat installing
this skill as commercial redistribution permission. Keep downloaded snapshots
out of public demos and open-source commits until rights have been checked;
synthetic test fixtures are safe alternatives. Do not add paid services or
credentials without the user's approval.

References: [yfinance](https://github.com/ranaroussi/yfinance),
[Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html).
