# Market-price analysis

Use the bundled `market_data.py`, not a replacement Yahoo downloader. Read its
`--help` and use optional local dependencies only when needed. Record identity,
exchange, currency, provider, retrieval timestamp, requested interval, observed
dates and every failed collection.

Use completed sessions and distinguish calendar endpoints from sessions.
Preserve adjustment, split and dividend conventions. Match benchmark adjustment
basis; price indices and total-return series differ. Choose the benchmark for
the question, not for a favorable result.

Compute returns, drawdowns and volume comparisons from retained snapshots.
Check the initial denominator, sufficient history, missing/duplicate bars,
partial sessions and corporate actions. Failed symbols must not disappear
silently from the ranked universe. Rate limits remain coverage gaps.

Separate observations, sourced events and causal hypotheses. Volume cannot
identify sellers, institutional flows or motives. A nearby earnings release
does not explain the entire move. Market observations complement SEC/IR financial
evidence; they do not replace it.

Deliver dated metrics and exact boundaries. Do not infer a buy/sell conclusion
without requested and supported valuation work. Operating-only questions do
not need market-price collection.
