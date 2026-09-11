---
name: finrunbook-investor
description: Operate independent forward-only paper-investing experts. Check each expert's research cadence and new events, dispatch an isolated research task only when due, record a sourced report and trade or no-change decision, and hand approved intents to a separate simulator. No historical backtests or real trading.
---

# FinRunbook Investor

Each expert owns its strategy, research history, decisions and simulated account.
Experts need not research every day, trade after every report, or wait for peers.
Use English reports and US-market sources for the current project unless the
user explicitly changes those settings.

## Active workflow

For new Arena jobs use the durable
[controller contract](../finrunbook-hourly/references/controller-operation.md).
It supersedes orchestration and next-open timing below with calendar eligibility,
stage recovery and fresh-reference-price paper execution. Preserve existing
methods, accounts and sealed records. The older native contract still defines
financial context isolation and independent review.

Read [native-forward-operation.md](references/native-forward-operation.md) when setting up,
dispatching, resuming or executing this workflow. It is the active contract;
the old round/qualification/replay controller is not an implementation of it.
The active execution mode for new tasks is **native agents**: the expert worker
does the financial analysis itself. Do not use a preparation worker to launch
another model through `forward_inference.py`, `codex_model.py`, `codex exec`, or
an equivalent shell/API launcher. Those helpers remain historical dependencies.
The earlier `references/forward-operation.md` is preserved byte-for-byte for
existing execution plans that pin it; use the native contract for new tasks.

1. **Check whether an expert is due, without an LLM.** Compare its last attempt,
   last successful research, next review time and unprocessed relevant events
   against its cadence, cooldown and daily attempt cap. Log skipped checks too.
   Use `scripts/forward_schedule.py`; default profiles are in
   [forward-profiles.json](references/forward-profiles.json).
2. **Research only due experts.** Start a fresh worker with `fork_turns: "none"`
   or an equivalent clean session. Supply only that expert's operative skill,
   own account, bounded own research memory and relevant dated raw evidence.
   Sharing raw source files is allowed; sharing experts' interpretations is not.
   Provide file paths and a short evidence index, not a lossy prompt-only packet.
   Let the worker inspect relevant source cells and collect missing evidence
   through authorized tools. Context isolation is not a ban on tools.
   Return artifact paths and a short status receipt to the controller.
3. **Produce a report and candidate decision in that worker.** Use the own
   expert skill for analysis and FinRunbook for the evidence ledger and English
   interactive report. An update covers material changes since its own last
   report; it need not repeat the entire company/industry study. Choose
   `rebalance` or `no_change`, with rationale and a next-review condition.
4. **Validate once, then repair only affected work.** Apply tone review within
   the author task. Use one separate fresh financial review, plus deterministic
   source, period, calculation and portfolio checks. Code computes aggregate
   status from validated findings. Missing critical evidence blocks the
   decision; optional gaps remain disclosed. No six-pass readiness loop.
   The reviewer is another native worker, not a nested CLI call. It can read the
   same source files. Allow one targeted author correction and one reviewer
   recheck; do not restart collection or the full report for a local defect.
5. **Execute separately, using code.** Seal valid reports and decisions first.
   Release this expert's approved paper intent without waiting for other
   experts. The simulator records subsequently observed eligible prices,
   simulated fills, cash, positions and returns. A proposal is never a fill.

The cadence helper tracks task lifecycle only. `finish --outcome completed`
does **not** validate a financial report or authorize a trade. A generic legacy
`verify-decision` receipt also does not establish compatibility with this new
per-expert execution contract.

## Keep the runtime small

- Load the expert's operative method, not its full qualification history,
  synthetic fixtures, every reference paper or all third-party finance skills.
  Source and method provenance remain available on disk.
- Use a shared neutral data cache and deterministic calculations. Request
  missing original documents rather than repeatedly searching a static catalog.
- Dispatch one expert author and one bounded reviewer per due task. Do not
  split planning, readiness, tone and every calculation into fresh large calls.
- Use one author and one reviewer, with at most one correction/recheck cycle.
  Declare a practical time and research scope before dispatch. Record actual
  host-provided usage when available; otherwise mark tokens unknown. Native
  dispatch does not inherit the retired launcher's hard token or timeout limits.
- Save successful stages. A renderer failure requires a renderer retry, not
  new financial research. A cancelled/failed task is not a no-change decision.

## Boundaries

Historical filings and price lookbacks can inform a decision made now. Do not
generate past-dated investment decisions or run historical strategy evaluations.
Use actual research, source-retrieval, decision-seal and execution timestamps.
All accounts are paper-only; no leverage or real broker orders are authorized.

Do not launch research, activate a recurring scheduler, or resume a stopped run
merely because this skill was redesigned or its helper was installed. A request
to check schedules is not a request to research. Honor the user's stop state.
Changing orchestration does not grant permissions or bypass a rejected action.
Do not retry a blocked export through native agents as a workaround. Existing
blocked runs stay stopped until an explicitly authorized continuation is resolved.

Old runs and the scripts/references they depend on remain for inspection and
reproducibility. Do not load `legacy-investor-workflow.md`, `runtime-binding.md`,
`experiment-protocol.md` or replay/qualification/recovery modules for a new
forward task. Their all-expert funding and repeated-review rules are retired
from the active flow, not silently removed from sealed old experiments.
