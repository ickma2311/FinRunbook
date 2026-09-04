# Market data contract (version 1.0.0)

Each collection writes `artifacts/market-data/MD-<unique-id>.json`. This is a
normalized **client response**, not a capture of Yahoo's original HTTP payload.
No raw data are embedded automatically in public report files.

## Snapshot

- `request`: adapter, tickers, benchmark, inclusive start, exclusive end,
  interval, price basis, session and allowed endpoint-gap hours.
- `retrieved_at`: collection time in UTC, not the last trade time.
- `series[]`: provider, client version, exact request parameters, source URL,
  ticker, exchange, currency, exchange timezone, status, errors and ordered bars.
- `bars[]`: timezone-aware timestamp, OHLC, adjusted close, volume, dividends
  and splits; unavailable values remain null, never zero-filled.
- `analyses[]`: method, expression, result, units, actual comparison period and
  references to exact snapshot cells (`series`, `bar`, `field`). Percent returns
  use a scale of 100; relative returns use percentage points.
- `quality_issues[]`: severity, code, affected series and explanation. Errors
  block required batches; warnings disclose insufficient observations, excluded
  incomplete bars, endpoint gaps, potentially truncated starts and adjustments.

Yahoo calls use `auto_adjust=False`, `back_adjust=False`, `repair=False`,
`actions=True`, `keepna=True`, `rounding=False` and a bounded timeout. Preserve
provider metadata and returned values. `adj-close` uses the returned adjusted
close; never silently substitute Close. A historical request retrieves today's
available history, **not** a point-in-time vintage. Later corrections and
corporate-action adjustments can change earlier values.

## Ledger integration

`research-record.json.market_data` has `schema_version` and `batches`. Each batch
contains its ID, run-relative snapshot path, SHA-256, `required` flag,
`source_ids`, cell-to-evidence/fact mappings and analysis-to-calculation mappings.
Sources are `type: market-data`, `primary: false`, with retrieval time, snapshot
hash and explicit terms. Numerical inputs have status `provider-reported`:
transcribed provider observations, not independently verified exchange data.

Only cells needed by generated calculations become numerical input facts.
Other chart values can cite the snapshot source and exact locators. Calculated
facts reference normal `CALC-*` entries, which record all input fact IDs,
formulas, units, price basis and periods. IDs are append-only. Snapshots are
internal evidence, not added as human-facing artifacts requiring tone review.

Adding a batch resets validation to `NOT_RUN`, marks existing deliverables
`draft`, and resets a required tone-review receipt to `pending`. The HTML/PDF
itself is not rebuilt: regenerate before delivery. Do not edit a run in another
process while collecting; the helper lock protects other collector calls only.

## Another provider

Implement an adapter returning the same `series` contract, including explicit
provider, version, parameters, URL, exchange, currency, timezone and bars. Select
it explicitly in the adapter registry and CLI. Review that provider's adjustment
semantics, time conventions and licensing before reuse. No commercial provider
or credentials are configured by this skill.

## Validation limits

The validator recomputes the defined metrics and matches ledger inputs to
snapshot cells. Independent unit tests check known numeric examples. This does
not prove issuer/security mapping, market data vendor correctness, exchange
session completeness, commercial rights, or news-to-price causality. No trading,
short-sale identity, funds-flow inference, analyst consensus or options support
is included in this first adapter.
