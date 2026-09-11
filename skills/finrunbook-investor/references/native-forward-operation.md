# Independent forward paper investing

This contract replaces the active cohort/replay workflow. It starts with actual
present-time observations; old simulations remain historical artifacts. The
cadence helper is implemented separately from research and financial execution:
installing it does not start a service, validate a decision, or connect a broker.

## One expert, one lifecycle

```text
Cheap due check -> not due: log and stop
               -> due: own isolated research + candidate decision
                       -> one financial review + deterministic validation
                       -> approved: seal -> own paper queue -> observed fills
                       -> unresolved: preserve blocked result, no new order
```

No global research rounds, all-ten barrier, historical cutoff reconstruction,
automatic qualification exam, daily strategy rewrite, or six-pass readiness
loop. One expert's failure never blocks another expert's account. Keep the
existing general-purpose finance/data/validator skills; select them only when
needed rather than deleting tools used elsewhere in FinRunbook.

### State and scheduling

For each expert record `last_attempt_at`, `last_successful_research_at`,
`last_decision_at`, `next_review_at`, `processed_event_ids`, `active_attempt`,
and an append-preserved attempt history. Do not replace last success with a
failed attempt. A due check is a program, not an LLM judgment.

An expert is due for its initial report, an elapsed regular interval, its
declared next review, or a new relevant event. Apply its minimum interval,
failure cooldown and New York calendar-day attempt cap first. An active task
for that expert prevents a second dispatch. A new event does not bypass these
limits. No daily minimum is imposed; multiple daily tasks are supported where
the configured cap permits them. The default cadence is a starting hypothesis,
not an empirically optimized strategy.

Only a completed research task consumes its dispatched event IDs. Failed or
cancelled tasks retain them for a later authorized retry. A `blocked` task waits
for a genuinely new relevant event; elapsed cooldown alone must not repeatedly
dispatch the same missing-data problem. Collector events such as a newly available
required filing can unblock it. Events arriving during
a task remain unprocessed even if that task succeeds. Use stable event IDs,
actual availability timestamps and explicit target expert IDs. Event types such
as `valuation_threshold` or `risk_limit_breach` must come from declared numerical
rules, not another expert's opinion. Repeated news copies of the same disclosure
are one event. Source locators live in the neutral cache keyed by event ID, not
inside the scheduler's metadata-only event objects. A collector provides raw
evidence, not a shared market narrative.

Default profiles are in `forward-profiles.json`. A weekly quality/value expert
can run early for material disclosures; Macro can respond to separate economic
releases. Daily trend checks use completed bars under a declared signal rule.
Changing cadence changes research frequency, not the underlying investment method.

Record every check, including `not_due`, with its reason and the actual profile
and event-batch hashes. Record attempts, source
changes and failures separately. Check receipts and task histories may live in
one controller store, but workers receive only their own projection.

### Research boundary

#### Native-agent execution (new tasks)

The controller dispatches one isolated native author and one isolated native
reviewer. The author researches and writes directly; neither worker starts a
nested model process or API call. Use the host's native task tools for dispatch,
status, follow-up and cancellation. Python remains responsible for source
collection, arithmetic, schema checks, scheduling and paper execution.

Give the author its task, operative method path, own account snapshot, evidence
directory/index and output directory. Give the reviewer those same inputs plus
the finished report and candidate. A summary helps navigation but never replaces
the sources: both agents can inspect the relevant original cells and receipts.
Do not copy a multi-megabyte ledger into the controller context or compress away
the evidence needed to decide. Source access remains subject to host permissions.

Record actual native agent IDs, task/attempt IDs, start/finish times, supplied
paths and source hashes in the existing dispatch/checkpoint files. Set
`execution_mode: native_agents`. Record requested and observed model identity
separately; unknown identity or usage stays null. Do not fabricate a CLI
`runtime.json`, no-tool guarantee, or measured token count for a native agent.

For a financial correction, return only the findings and affected paths to the
same author; then have the reviewer recheck the changed artifacts. Preserve the
original review and bind the final review to the final candidate hash. If the
original native workers are no longer available, a fresh replacement receives
only this expert's files and the relevant revision history; record the new ID.

The review uses the existing `forward_account.py` contract: `candidate_hash`,
`author_task_id` matching the candidate, actual native `reviewer_task_id`,
`parent_history_inherited: false`, `reviewed_at`, and required findings for
`material_evidence`, `calculations`, and `report_decision`. The controller
verifies distinct actual author/reviewer IDs and output provenance, then uses
the existing seal operation. Retain native dispatch and completion receipts;
match the review path/hash returned by the reviewer to the actual file, then
check its author/task/candidate bindings. A plausible agent ID inside an
author-written review file is not proof of an independent review.
Complete tone review and validator-driven artifact updates before constructing
the final candidate and requesting review. If validation changes a reviewed
financial artifact, refresh its bindings and recheck the affected revision
before sealing; never seal stale review hashes. IDs and hashes are bindings, not
proof that the reviewer performed sound financial analysis. A native reviewer
does not need a nested CLI usage receipt to be valid.

If the host cannot supply independent worker contexts, report that limitation
and leave approval pending; do not silently treat the author's self-review as
independent. Financial review is still necessary even though CLI orchestration
is retired from the active path.

#### Existing experiments and permissions

`forward_inference.py`, `codex_model.py`, old packets and run-specific controller
scripts remain untouched for historical inspection. Do not use their CLI-only
completion gates for new native tasks. In particular, do not delete or change a
skill file whose hash is pinned by an existing account. For a newly enrolled
expert, make a versioned operative snapshot with this runtime contract; remove
only superseded launch/budget instructions, preserving the investment method,
thresholds and universe. Record the source version and runtime change.

For a new authorized task on an existing account, retain the account, funding,
positions and pinned method unchanged. Record `execution_mode: native_agents`
and this contract's path/hash in the new dispatch and financial content. For
that task, this declared runtime contract supersedes only the pinned skill's
old CLI/no-tool/token-limit instructions, not its investment rules. Do not
re-enroll, refund, alter the skill hash, or rewrite earlier receipts. A strategy
change remains a separate future-effective change, not part of this migration.

A workflow redesign does not resume a stopped task, fund an account, enable a
timer or authorize an external transfer. A previously denied call stays denied;
do not reroute it through another tool to evade the decision. Resolve the
authorization before any continuation or migration of that blocked work.

Enroll each expert once with its own operative SKILL.md, method version/hash,
watchlist, cadence and account ID. Preserve existing method/source provenance;
do not claim that this redesign creates new qualifications or trained models.
Do not re-run literature qualification or load synthetic qualification fixtures
for each research task. Skill changes are separately versioned, future-effective
changes, not automatic reactions to a single losing trade.

The dispatch manifest contains:

- expert/task/attempt IDs, actual start time, own skill path/version/hash;
- own numeric account snapshot and pending-order IDs, with observation times;
- own latest report, unresolved thesis checks and compact factual memory;
- neutral event IDs and source references, each with date and content hash;
- permitted read/output locations, tool policy and declared task budget;
- `parent_history_inherited: false` and the actual isolation limitations.

Use a new worker with `fork_turns: "none"` per expert task. Do not give it the
parent chat, another expert's report, a consensus narrative or the leaderboard.
Independent contexts do not imply OS-level access restrictions; disclose the
host's actual boundary. Shared original filings and numerical data are allowed.
An expert's own prior analysis is memory, not new verified evidence.

The first report establishes the investment thesis and baseline. Later reports
can focus on what changed, how the own thesis is affected, valuation/risk
implications and the resulting action. They still need enough financial analysis
to support that action. An unchanged day does not require a rewritten report.

Use one expert worker for data follow-up, analysis, report and candidate decision.
Use FinRunbook's ledger, financial presentation and tone rules; `forward_binding`
selects this contract rather than the legacy `expert_binding` round adapter.
Load only the expert's applicable method and task-relevant data. An author-side
tone pass is sufficient; do not launch a separate editorial agent by default.

Record actual source publication/availability and retrieval times. Once the
evidence package is ready, record its actual cutoff and hash before final
judgment. Material sources must be available and retrieved by that cutoff;
the decision seal must be later. New material information after the cutoff is a
new revision/task, not a silently edited sealed decision. Historical filings and
price lookbacks are legitimate current inputs; past-dated decisions are not.

### Validation and budgets

Run deterministic ID, schema, period/unit, calculation, portfolio and timestamp
checks before requesting financial review. The separate reviewer first checks
the task's material evidence/calculations, then compares the report and candidate
decision. It sees only this expert's inputs. Record the financial findings once;
do not create independent LLM calls for each readiness/administrative status.

Code computes aggregate status from requirement-level findings. Optional missing
detail remains a disclosed limitation; missing decision-critical evidence blocks
new orders. Hashes, identity checks, totals, risk limits and status aggregation
are programming tasks. A schema error is not a reason to regenerate the entire
financial analysis. No unsupported fact may be repaired by inventing a citation.

Use one author task and one reviewer task, with at most one targeted correction
and one recheck. These are workflow stages, not limits on an agent's internal
model turns. Declare coverage and a practical time budget before starting;
the controller checks progress through native task status and interrupts at the
deadline, preserving completed files. Do not create a new daemon or timeout
launcher just to reproduce the retired CLI path.

Native task tools may not expose enforceable per-call token budgets or exact
usage. Record actual reported input/cached/output counts when available, null
otherwise. Disclose that hard token ceilings and a no-tool author environment
are not provided by this mode. If an explicit user requirement needs a hard
cost/token cap unavailable in the host, resolve that constraint before launching;
do not claim the old 40,000/300,000-token checks still apply. Never change models
or launch another model solely to obtain a usage receipt.

Allow one targeted correction within the task budget. If relevant new evidence
or a deterministic repair cannot resolve the issue, save `blocked` with the exact
missing input/error. Separate transient provider errors from financial defects;
a bounded retry reuses the exact task inputs and is logged. Exhausted tasks need
a new authorized dispatch after cooldown, not an unlimited background retry.

Retain stage artifacts and their dependency hashes. Reuse only verified own
unchanged inputs/results; invalidate affected dependents when evidence or code
changes. Presentation failure requires presentation repair, not new investment
research. An unverified HTML page is not a final delivered report; its status is
separate from validated structured financial content and execution eligibility.

### Candidate decision and independent account

Required decision fields: expert/account/task IDs, own skill hash, report path
and hash, evidence cutoff, account snapshot hash, `action`, rationale, next-review
condition, and actual seal time added by the controller after validation.

- `no_change`: retain existing positions; no new orders. Do not interpret this
  as liquidating into cash. Pending orders remain unless explicitly cancelled.
- `rebalance`: explicit target weights, execution policy and risk/price limits.
  An empty target map explicitly means liquidation, not no change.
- `blocked`, `failed`, `cancelled`, `not_due`: operational results, not decisions.

Existing defaults remain paper-only USD accounts with $100,000 initial capital,
long-only whole shares, no leverage, 30% target cap per security and 10 bps adverse
slippage. Record each account's actual enrollment/funding time. No initial buy
before that expert's first validated report and decision. Cash NAV may exist
while research is pending; never label a failure as a successful cash strategy.

Each expert releases its own approved intent immediately to its paper queue.
Keep at most one active target-allocation intent per account. A subsequent
rebalance names the pending intent it replaces; cancellation/replacement is
atomic and append-recorded. New research does not duplicate orders or erase
earlier decisions. An explicit no-change decision does not implicitly cancel an
already approved pending order.

### Simulator boundary

Research frequency is independent of fill frequency. Retain next-regular-session
open execution as the initial policy; multiple same-day reports do not imply
intraday fills. Fill time must be strictly later than the decision seal and
evidence cutoff, using actual subsequently observed prices. Never fill a newly
created decision at an opening price that has already occurred.

Size using the last eligible known closing snapshot, then check cash, tradability,
price limits and portfolio risk against execution observations. Do not let an
overnight gap silently create leverage or violate the declared fill-time risk
policy. A price-limit failure leaves the intent unfilled and creates a review
event; it need not invalidate unrelated long-lived industry research.

Keep financial content, model/runtime identity and ledger entries immutable once
sealed. Do not include mutable status pages in the financial execution identity.
An event ID/account/decision/session idempotency key prevents duplicate fills.
Persist simulated fills, positions, cash, fees/slippage, distributions and NAV
from code. Reconcile cash/shares; missing prices or unsupported corporate actions
block settlement rather than create made-up returns. A failed research task does
not prevent marking existing holdings with observed prices.

The existing NautilusTrader kernel may be reused as a calculation engine, but
the old cohort launcher and `verify-decision` path must not be used as the new
adapter. It currently requires complete-session prices, so it cannot promise
live intraday fills. A new per-account adapter must verify this contract, handle
pending-order replacement and idempotent ledger updates, and be tested before
operational settlement. Reconstructing accounting from genuinely recorded forward
events is not a historical strategy backtest; never regenerate past decisions.

Keep SPY buy-and-hold and the declared universe's quarterly-rebalanced equal-weight
benchmark. SPY's 100% reference allocation is an explicit benchmark-only exemption
from the expert security-weight cap. Match each expert's funding
time and execution assumptions; show elapsed time and exposure for comparisons
across different start dates. Benchmarks are deterministic, not extra agents.

## Files and supported helper

```text
runs/<forward-session>/
  schedule-state.json          controller task metadata; never sent wholesale
  events.json                  neutral metadata; source locators stay in cache
  checks/                      logged due/not-due checks
  experts/<expert>/
    profile.json               own skill reference, cadence and account ID
    account.json               simulated numeric state with observation times
    tasks/<task-id>/
      dispatch.json            own-only input manifest
      research-record.json    source/fact/calculation ledger
      report/                  English HTML + report-data.json
      decision.json            candidate then hash-sealed approved record
      validation.json          financial validation, distinct from task status
      review.json              material semantic findings
    orders/                    accepted/cancelled/replaced paper intents
    ledger/                    actual observed simulated execution records
```

The scheduler creates only task metadata, not the financial files above. From
the repository root:

```bash
python3 skills/finrunbook-investor/scripts/forward_schedule.py init \
  --policy skills/finrunbook-investor/references/forward-profiles.json \
  --state runs/<forward-session>/schedule-state.json
python3 skills/finrunbook-investor/scripts/forward_schedule.py check \
  --policy skills/finrunbook-investor/references/forward-profiles.json \
  --state runs/<forward-session>/schedule-state.json \
  --events runs/<forward-session>/events.json --log
```

The events file is a JSON array of `{id, type, available_at, expert_ids}` entries;
an empty array is valid. `start` uses the same inputs plus `--expert`; it records
the attempt but does not launch a worker. `finish` records its outcome using
`--state`, `--expert`, `--attempt`, `--outcome` and, for completed tasks, `--report`
and `--decision` paths. Artifact hashes establish identity, not financial truth.
Run `--help` for the exact supported CLI. No timer, research model, funding or
trade is activated by these commands. Use product scheduling tools only after
the user explicitly asks to enable recurring operation.

## Delivery and release test

Display per expert: last attempt/success, next review or skip reason, current
task, report links, decisions, pending orders, fills and account/benchmark returns.
Show real process liveness separately from heartbeat and artifact progress.
Cancellation must stop that task's worker and update status while preserving files.

Before enabling the new full runner, test one expert end to end with a declared
budget; test no-change, optional gaps, missing required sources, interrupted
workers, cooldown, order replacement and duplicate settlement. Then scale to the
ten independent experts. Offline synthetic tests establish software behavior,
not investment quality or executed real-world trades.
