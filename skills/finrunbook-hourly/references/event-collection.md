# Official event collection

Run `python3 skills/finrunbook-hourly/scripts/check_due.py --collect-events --log`
from the repository root. This collects public metadata, then assesses eligibility;
it does not launch research or trades. The agent performs later skill stages.

## Coverage and routing

- SEC Submissions API: companies in registered account universes, using the
  CIK map in `event-sources.json`. Validate the returned CIK. Unknown tickers
  are configuration gaps; listed ETFs are explicitly excluded from company
  filing coverage. Do not infer fund filings from a sponsor's company filings.
- 10-K / 10-Q: `annual_filing` / `quarterly_filing`. Amendments: `amendment`,
  never an assumed restatement. 8-K: `material_disclosure`; an explicit Item
  2.02 additionally emits `earnings`. One accession/type produces one event.
- Federal Reserve monetary-policy RSS: `policy_change` for Macro. A press
  release is not automatically a rate decision or market shock.
- BLS CPI, Employment Situation and PPI release feeds: `macro_release` for Macro.
- An expert receives only event types already accepted by its cadence profile
  and company events only from its registered universe. Several events can be
  handled by one research attempt. This does not expand pinned investment rules.

These release feeds do not detect price risk, monthly Trend signals, news/social
discussions, BEA releases or semantic valuation changes. The Arena controller also
checks fresh saved holdings against sealed weight caps and observed pending-order
prices against approved bounds. Missing quotes/rules remain uncovered. The check
receipt includes a trigger-coverage matrix; only already accepted event types can
trigger each expert's research.

## Durable state

`runs/hourly-event-cache/state.json` stores per-source baseline/seen IDs, emitted
events and evidence references. `raw/<sha>.json` wraps each original UTF-8 response;
`body_sha256` hashes `body.encode('utf-8')`, not the wrapper file.
`collections/<id>/` has immutable `events.json`, `evidence-index.json` and
`collection.json`. The hourly check links the collection receipt and freezes the
event batch used by dispatch. No generated data belongs in Git.

First successful collection baselines each source independently, without emitting
archive items. A failed first fetch does not create a baseline. Later newly seen
items must have publication times at/after that baseline and not in the future.
Event `available_at` is the actual first local observation, conservatively later
than publication; it is not a claim of real-time delivery. SEC acceptance times
are retained as provider metadata, not a historical backtest clock.

RSS/Atom deduplication uses item identity plus dated release, so recurring releases
at the same latest-release URL remain distinguishable. Undated items cause a
source error. Revisions with the same identity/date are not a separate trigger.
If an account cannot be read, SEC collection defers without advancing issuer
watermarks, because complete company-to-expert routing is unavailable. Macro
feeds and other experts' regular schedule checks still run.
Future items are not marked seen. Already emitted events persist across feed
rollover and cooldowns; the scheduler's `processed_event_ids` consumes them only
after completed research. A failed source never clears existing events.

## Limits and failure handling

Two concurrent requests, at most five SEC request starts per second per collector,
eight-second request deadlines, four-MB response caps,
and no automatic network retries. Seventeen sources in the current configuration
take at most roughly ninety seconds of network work; normal runs should be much
shorter. Holding a nonblocking collector lock prevents simultaneous state writes.
The state file is published after immutable collection files. No sleep daemon.

Use `SEC_USER_AGENT` to supply your real application/contact identification if
required by SEC access policy; the default identifies the public project URL.
Do not invent a contact address or bypass a provider denial. Network permissions
for unattended runs still apply. HTTP errors, invalid JSON/XML, mismatched issuer
IDs and missing dates are coverage errors, not evidence of no releases. Repeated
403 failures back off for 1/2/4 hours up to 24 hours. Skipped denied feeds remain
uncovered; receipts retain sanitized HTTP status/body excerpts and recovery hints.
Notify on new/changed failures or recovery, not each known outage.
After recovery, the first successful fetch baselines an uninitialized source;
disclose that the outage interval was not monitored.

Exit codes: 0 healthy collection/check; 2 partial source or expert coverage with
a usable saved check; 1 fatal setup/collection failure. On exit 1 do not present
an old feed as fresh. An explicit schedule-only check can still run, labeled as
such, without claiming event coverage.

## Official source documentation

- [SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [BLS release feeds](https://www.bls.gov/feed/)
- [Federal Reserve feeds](https://www.federalreserve.gov/feeds/feeds.htm)
