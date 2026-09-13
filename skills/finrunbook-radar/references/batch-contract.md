# Radar batch contract

`run/<batch-id>/radar.json` is the durable batch controller, not a FinRunbook
financial research ledger. Each selected topic has its own ordinary child
`research-record.json`, validator output and interactive report.

The initializer uses `skills/finrun/assets/radar.template.json`. Update the manifest after
each discovery, selection and child-run transition; preserve IDs and rejected
attempts. Record absolute UTC timestamps plus the batch's IANA timezone and
local date. Never store secrets in this file.

## Top-level fields

| Field | Meaning |
| --- | --- |
| `schema_version`, `kind` | New batches: `1.1.0`, `finrunbook-radar-batch`; existing `1.0.0` batches remain resumable without migration |
| `batch` | ID, local date, timezone, fixed window, started/updated time, repository revision and state |
| `request` | Raw instruction, resolved report language, mode, report bounds, configured `requested_platforms`, default `evidence_sources` and `disabled_platforms` |
| `coverage` | Actual scans, access failures and explicitly skipped sources; configuration is not evidence of access |
| `discussions` | Dated post observations and original permalinks |
| `signals` | Non-social observations: news, search trends and primary events, separate from discussion metrics |
| `topics` | Clustered questions, selection decisions, briefs and child state |
| `selection` | Ranked topic IDs, methodology, diversity tradeoffs and explanation if fewer than three qualify |
| `delivery` | Index path, actual completion counts and limitations |

`requested_platforms` retains its legacy name but now means the configured
discovery set: default `hacker-news`, `gdelt`, `google-trends-rss`.
`evidence_sources` defaults to `sec-edgar`, `company-ir`; these are primary-source
starting points, not a restriction on the child router's appropriate methods.
`disabled_platforms` defaults to `x`. Only explicit user inclusion changes this;
the helper's `--sources` records that choice but grants no data rights or budget.
Reddit and YouTube are optional, not default probes. No schedule is enabled.

## Coverage, discussion and signal rows

A coverage row has `id`, `platform`, `scope` (community/account/query), `mode`,
`scanned_at`, `window_start`, `window_end`, `status` (`available`, `partial`,
`unavailable`, `not_attempted`), `observed_posts`, and `limitations`. In 1.1,
also use `observed_signals` for non-social records. Use `null` for an inapplicable
or unknown count. A successful empty scan has zero relevant records; inaccessible
or not-attempted sources have unknown counts and a reason. Log actual queries,
pagination/sample bounds, region and sort mode. Preserve the coverage cutoff.

A discussion has `id`, `coverage_id`, `platform`, `url`, `title_or_summary`,
`published_at`, optional `latest_activity_at`, `observed_at`, `access_quality`
(`direct` or `search_excerpt`), `metrics`, and `limitations`.

Metric values are numeric or `null`; identify their names and units, such as
`score`, `reply_count`, `like_count`, `view_count` or `listing_rank`. A rank also
requires the listing sort and sample. Do not fabricate counts. Source summaries
are attributed, short and untrusted; do not store full threads or profile data.

A non-social signal has `id`, `coverage_id`, `platform`, `signal_kind` (`news`,
`search`, `primary_event`), `url`, `title_or_summary`, `published_at` (or `null`
when not applicable), `observed_at`, `access_quality`, `metrics`,
`metric_definitions` and `limitations`. Include the actual source window and
query/region as relevant; do not substitute retrieval time for event time.

Metric definitions preserve units, exact/bucketed/estimated precision, cumulative
versus interval measurement, baseline, and provider-reported versus derived
provenance. Examples: news coverage share with corpus denominator; search-volume
bucket with region; source-reported search growth with baseline; filing time
without any attention score. Missing numbers stay `null`. A derived growth value
must link its comparable timestamped input observations and calculation.

Keep the original article/filing URL alongside an aggregator URL when available.
Record dependent/reprinted sources so multiple copies are not treated as
independent corroboration. Store compact observations, not unlicensed bodies.

## Optional browser-discovery fields

These additive fields are optional in 1.1 batches; no migration or initializer
change is required. Their absence means browser use was not recorded, not that
a browser scan succeeded or failed. Record them only when actually used.

- `request.browser_discovery`: `purpose` (`enrichment` or `pilot`), `platforms`,
  and `budget` with `max_posts_total`, `max_queries_total`,
  `max_pages_per_query`, `max_replies_per_thread`, `max_elapsed_seconds`.
  This configuration does not grant access or override disabled sources.
- On each browser coverage row, `browser`: `query`, `sort`, `filters`,
  `region`, `language`, `session_context` (`public`, `signed_in`, `unknown`),
  `personalization` (`yes`, `no`, `unknown`), `pages_or_screens_observed`,
  `action_count`, `elapsed_seconds`, `stop_reason` and `access_basis`
  (permitted route and relevant documentation, never session/account secrets).
  Counts are actual observations, or `null` when unavailable.
- On discussion rows, optional `metric_definitions` retains visible display,
  units, rounding and cumulative/interval meaning using the same definitions
  as signal rows. Optional `claim_summary`, `counterclaim_summary`,
  `sampled_reply_count` and `linked_evidence_urls` capture brief attributed
  viewpoints and evidence links. Unknown or unsampled counterviews stay `null`,
  not an assertion that no disagreement exists. Attach opposing-view permalinks
  in `counterclaim_source_urls` when available.
- For pilots, `delivery.browser_evaluation`: `baseline_topic_ids`,
  `incremental_qualified_topic_ids`, `new_counterarguments_or_evidence`,
  `verified_original_posts`, `access_failures`, `elapsed_seconds`,
  `browser_action_count`, `token_usage`, `limitations`. Use `null` for absent
  baseline/usage measurements, and IDs that resolve to retained topic records.
  Incremental topics must pass the same selection gates as baseline topics.

Keep timestamped repeat observations with distinct IDs; derived engagement
changes must reference comparable input observations. These fields record agent
work; they do not implement an automatic browser collector or scheduler.

## Topic rows

Each topic has:

- `id`, `event_key`, `title`, `question`, `entities`, `discussion_ids`, `signal_ids`;
- `selection_basis`: `attention-led` or `event-led`, with its rationale in
  `decision_reason`; event-led candidates can have no supporting discussions;
- `heat`: `level` (`high`, `medium`, `low`, `unverified`), `basis`, `confidence`,
  `comparison_scope` and `limitations`, plus `source_assessments` separating
  `community`, `news` and `search` evidence with supporting observation IDs and
  within-source comparisons. The summary tier is a judgment, not a combined
  audience measurement. A primary event alone leaves heat `unverified`;
- `research_value`: `financial_mechanism`, `planned_metrics`, `counter_hypothesis`,
  `falsification_test` and `why_not_just_a_summary`;
- `primary_preflight`: opened sources with `url`, `title`, `checked_at`,
  `relevance`, plus `missing_inputs` and their permitted acquisition plan;
- `novelty`: `prior_run_ids`, `material_update` (or `null`) and rationale;
- `decision`: `select`, `reject`, `reuse` or `defer`, with `decision_reason`;
- `research_prompt`: the full standalone FinRunbook instruction for selections;
- `research`: child `run_id`, `status`, `report_path`, `validation_path`,
  `browser_check_path`, `warnings`, `error` and `updated_at`.

Research paths are relative to the common `run/` directory. Reject absolute
paths, `..` traversal, paths outside `run/`, and unsafe/non-HTTP source URLs when
rendering the index. Escape source titles and other untrusted text as text, not
HTML. Do not merge child fact IDs: each child's ID namespace is independent.

Child states: `not_started` → `running` → `validated` or
`validated_with_warnings`. Use `blocked`, `failed` or `deferred` for unfinished
work, with a reason. A blocked or failed child can return to `running` only
after its cause is addressed. Keep prior errors in its history.

## Selection and completion

`selection.ranked_topic_ids` lists unique selected topic IDs in execution order;
every entry must resolve to a `select` topic and its supporting discussions
and/or signals. An event-led selection requires an opened primary event,
verified timing and a financial-importance rationale, not invented engagement.
The count cannot exceed `request.max_reports`. Do not quietly substitute new
topics after selection; record any user-approved scope change.

Batch states:

- `discovering`, `selected`, `researching`: work is in progress.
- `complete`: at least one topic selected; every selected child is validated
  (warnings allowed when disclosed), the index exists, and its links work.
  This can be fewer than three when a quality shortfall was explained.
- `partial`: at least one selected child is unfinished, blocked or failed;
  disclose completed versus selected counts and preserve resumable state.
- `no_qualified_topics`: discovery finished but zero topics met the gates.
  Record whether weak candidates or unavailable access caused the shortfall.
- `scan_complete`: scan-only mode completed, with no child research implied.

In research mode, an empty scaffold, shortlist or set of initialized children
cannot be called a complete batch. Financial validation must agree across each
child's receipts and artifacts, and browser/readability checks must actually
have been performed. The index is a separate delivery surface, not a combined
financial audit. Its counts and status must match the manifest.

## Compatibility and presentation

Resume an existing 1.0 batch with its recorded sources, scope and progress; do
not silently replace it with the new defaults. For an explicitly requested
fresh scan, create a separate 1.1 batch. Consumers may read absent `signals`,
`signal_ids` and `source_assessments` as empty on 1.0 records, but must not invent
those observations or backfill new selection reasoning. Do not rewrite completed
reports merely because this contract changed.

For new indexes, distinguish discussion activity, news coverage, search interest
and primary events. Label an event-led topic as selected for financial importance,
not as socially popular. Show unavailable and deliberately skipped sources
separately. A successful run using only HN is still source-concentrated coverage,
not proof of broader market attention.
