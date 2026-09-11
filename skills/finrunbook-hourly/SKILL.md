---
name: finrunbook-hourly
description: Run one Arena eligibility and recovery cycle using the durable Python controller, isolated native research and independent review. Dispatch only due experts and enqueue approved paper decisions; supports check-only requests and does not install a timer.
---

# FinRunbook Hourly

Check hourly; research only when due. Read the [controller contract](references/controller-operation.md)
before dispatching or recovering work. English reports, US markets, existing accounts
and pinned methods. No nested model launchers, backtests or forced trades.

## Check

From the repository root:

```sh
.venv-portfolio/bin/python portfolio/controller.py check --collect-events
```

This saves eligibility and coverage, not a research result. Read [event collection](references/event-collection.md)
when diagnosing feeds. Source failures must not suppress independently due experts.
SEC/BLS denials remain partial coverage, never evidence of no events. Respect saved
retry times; do not bypass denials.

Macro/Trend/Defensive become regularly eligible each trading session at 08:45 New
York. Industry/Growth use three-session windows; others the first trading session
each week. Events and review commitments may trigger earlier work. Preserve
minimum intervals, caps, cooldowns and stops. Missed windows coalesce. Trend still
uses its completed-month investment signal.

For a check-only request stop here. A due flag alone does not authorize research.

## Dispatch or resume

Read [Investor](../finrunbook-investor/SKILL.md) for authorized operation.
Inspect existing jobs before claiming due experts. Resume the first incomplete
stage; do not regenerate research after capacity, execution or publication
failures. Do not resume terminal blocked/cancelled work implicitly.

Use fresh native authors and independent reviewers with `fork_turns: "none"`.
Each receives only its own skill, snapshot, bounded prior research and raw sources.
Never share the controller journal, other experts' narratives or the leaderboard.
Up to two authors and one reviewer may run within host capacity. A stale worker
record means unknown liveness; inspect native status, never silently clear it.

Use `record-result` for observed task results and `finalize` for validation,
sealing, schedule completion, paper handoff and publication. Allow one targeted
correction/recheck. Keep financial approval separate from HTML verification.
Do not hand-write operational receipts or rewrite registry status notes.

## Paper operations and delivery

New rebalance candidates explicitly use `fresh_reference_price_ledger`.
Finalize enqueues only that approved decision under current authorization.
The managed service retries eligible orders and values holdings every five minutes;
it never launches research. `no_change` retains holdings and pending intents,
including their original expiry. An approved plan is not a fill.

Read [portfolio operations](../../portfolio/README.md) before using the service.
Do not retry historical orders blindly, fund accounts, change strategies or risk
limits, place broker orders, upload publicly or enable additional timers.

Link completed reports, decisions and Arena. Distinguish waiting for price, market
closure, risk block, expiry, application and publication. A successful review may
produce no trade. For recurring checks stay quiet on unchanged non-actionable
state; notify on completed research, ledger changes, changed failures/recovery or
required input. Synthetic plumbing tests are not actual investment research.
