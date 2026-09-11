# Durable Arena operation

This replaces only orchestration and execution timing in the older native
contract. Preserve sealed records and investment methods. Python never calls a
model; the host dispatches fresh native research and review contexts.

## Commands

Prefix these with `.venv-portfolio/bin/python portfolio/controller.py`:

- `check --collect-events`: save bounded feed coverage and calendar eligibility.
- `claim --expert ID --authorization 'actual authorized scope'`: claim an eligible
  task or return its unfinished stage. Never invent authorization.
- `record-result --job ID --stage research|review --result PATH`: save native
  observations and artifact hashes.
- `correct --job ID --findings 'specific findings'`: one targeted revision/recheck.
- `finalize --job ID`: validate, seal, finish the schedule, enqueue, and publish.
  Repeat after crashes; successful research is not regenerated.
- `service-tick`: retry eligible authorized paper orders and value holdings.
  `--offline` rebuilds from saved data without fetching or applying trades.
- `status`: read current state and bounded work descriptions.

`runs/arena-controller/receipts/` is the immutable journal. `state.json` is its
recoverable projection. Account files remain authoritative for balances and
decisions. Store worker outputs in the claimed job folder; never rewrite receipts,
holdings or historical files manually. Do not hand-edit registry progress notes.

## Native result format

The controlling agent records actual native tool observations, not worker-authored
assertions of independent review. Example structure (replace all placeholders):

```json
{
  "status": "completed",
  "native_observation": {
    "worker_id": "ACTUAL_NATIVE_ID",
    "tool": "ACTUAL_NATIVE_STATUS_TOOL",
    "observed_at": "ACTUAL_UTC_TIMESTAMP",
    "status": "completed"
  },
  "artifacts": {
    "candidate": "/absolute/job/candidate.json",
    "report": "/absolute/job/financial-content.json",
    "evidence": "/absolute/job/evidence.json",
    "html": "/absolute/job/report/index.html"
  },
  "presentation": {"status": "unverified"}
}
```

Research requires all four artifacts. Review supplies `review` instead, bound to
the candidate and actual distinct reviewer ID. Candidate task ID matches the
author's native ID. Use the account helper's required financial findings and
fresh-context declaration. Run FinRunbook validation and tone review before
freezing candidate/review hashes. Record scoped browser QA separately; unverified
HTML is not a delivered visual-QA PASS.

Use `running` only after native dispatch; verify status with native tools. Over
five minutes without confirmation means unknown, not stopped. Inspect/stop an old
worker before replacement. Native isolation does not imply OS access isolation.

Capacity/provider/runtime failures use `status: retryable`, `error_kind` and a
concrete `error`; respect `retry_at`. Missing financial evidence is `blocked`, not
an approved cash decision. Cancellation requires native cancellation confirmation.
Do not auto-resume terminal jobs. Preserve artifact paths instead of sending the
controller all research text. One author and independent reviewer per expert;
two authors plus one reviewer may run within available host capacity.

## Timing and recovery

08:45 ET means eligibility, not guaranteed dispatch. Three-session periods anchor
to September 8, 2026. A report completed within its period satisfies regular
cadence. Events and existing future review commitments remain independent.
Keep minimum intervals, daily caps, cooldowns and explicit stops.

New rebalances select `fresh_reference_price_ledger` explicitly. Retry with a
completed post-seal regular-session bar every five minutes, subject to provider
capacity. Expiry is current session close if sealed while open, otherwise next
session close. Later `no_change` keeps the original pending order and expiry.
Risk failures stop; missing quotes retry; idempotency prevents duplicate fills.

Resume only the incomplete stage. A review-capacity failure resumes review; a
publication failure repeats finalization without new financial research. Do not
clear legacy active attempts or import stopped experiments automatically.

First release one due expert end to end. After actual native review, finalization
and publication succeed, release remaining eligible experts. Synthetic tests
establish software behavior, not investment performance.
