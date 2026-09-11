# Programmatic portfolio refresh

## Durable Arena service (active workflow)

Use the controller for new expert cycles, not the older manual apply sequence:

```sh
.venv-portfolio/bin/python portfolio/controller.py check --collect-events
.venv-portfolio/bin/python portfolio/controller.py status
.venv-portfolio/bin/python portfolio/service.py start
.venv-portfolio/bin/python portfolio/service.py status
# Stop only the identity-verified managed service:
.venv-portfolio/bin/python portfolio/service.py stop
```

Open `http://127.0.0.1:8798/live-portfolio/`; `/health` reports tick freshness and
valuation health. The process has file-backed logs and detached standard streams;
closing a terminal does not close the server. It is not cloud hosting or a login/
reboot service. The computer must remain available. Logs and service identity live
in `runs/arena-controller/`. `start` enables the five-minute maintenance loop; it
does not dispatch research. The separate hourly native-agent automation does that.

The maintenance tick retries only explicitly enqueued approved paper orders and
updates valuations. Limits remain whole-share, long-only, no leverage, 30% maximum
security weight, 10 bps adverse slippage, fresh completed post-seal minute bars.
An execution batch permits at most four attempts/120 seconds of provider work;
saturated queues can retry later than five minutes. Expiry is the current regular
session close if approved while trading, otherwise the next session close.
`no_change` preserves an existing order and its expiry; explicit replacement or
cancellation ends it. Missing prices retry; risk failures stop. No broker calls.

The controller owns claims, stage hashes, independent native-review bindings,
sealing, scheduler completion and publication. Read the
[native handoff and recovery contract](../skills/finrunbook-hourly/references/controller-operation.md)
before dispatching. Python never calls an LLM. Recorded attempts are not proof of
worker liveness. A missing confirmation becomes unknown; it does not clear a task.

`runs/arena-controller/receipts/` is an immutable write-ahead journal;
`state.json` is recoverable current state. The execution queue and attempt receipts
live alongside it. Accounts retain authoritative cash, holdings, seals and fills.
On a crash, repeat finalization or service tick: committed decisions/trades are
not duplicated. Do not rewrite registry progress notes or old financial artifacts.

Calendar defaults: Macro/Trend/Defensive daily sessions, Industry/Growth fixed
three-session windows anchored September 8, 2026, others first session each week,
all eligible at 08:45 ET. Hourly pickup may be later. Events/review commitments can
trigger earlier work; intervals/caps/cooldowns and stops still apply.

SEC/BLS access failures remain visible; repeated identical 403s back off up to
24 hours. Supply actual contact identification with `SEC_USER_AGENT` if appropriate;
never invent contact details or bypass denials. A blocked feed cannot suppress
independently due experts. The controller reports trigger coverage; numerical
checks use existing sealed rules only, with fresh matching account snapshots.

The sections below document standalone valuation/account utilities and legacy
manual application. They do not replace the managed controller's retry policy.
Run `refresh.py` directly for a valuation-only update; it never trades.

## Arena on a clean checkout

The default registry is local `portfolio/experts.json` when present; otherwise
the app uses `portfolio/experts.example.json`, which contains ten unstarted
experts and no investment records. Copy the example to `experts.json` to register
your own accounts, reports and schedule files. Paths are relative to the repo.
The local registry and generated `runs/` output are excluded from Git.

After installing the Python requirements below, an offline empty-state preview:

```sh
.venv-portfolio/bin/python portfolio/refresh.py --offline
.venv-portfolio/bin/python -m http.server 8783 --directory runs
```

Open `http://127.0.0.1:8783/live-portfolio/`. No research or trades start.
`apply_decision.py` uses the included standalone ledger helper at
`skills/finrunbook-investor/scripts/forward_account.py`; other investor/replay
launchers are not needed by Arena.

Offline regression checks (Node 18+ for the UI checks):

```sh
.venv-portfolio/bin/python -m unittest discover -s tests -p test_portfolio_refresh.py
.venv-portfolio/bin/python -m unittest discover -s tests -p test_apply_decision.py
.venv-portfolio/bin/python -m unittest discover -s tests -p test_forward_account.py
node tests/test_arena_ui.cjs
```

## Expert Arena page

The user-facing page separates expert methods, recorded research status,
approved decisions and dated portfolio valuations. Full rationales, review
warnings and execution receipts remain available under audit details.
Short decision summaries are presentation copy bound to an exact decision ID;
a new decision invalidates the previous summary automatically.

The browser polls saved portfolio and scheduler files every 15 seconds. Scheduler
records expose last attempts, completed research and planned review times, not
process heartbeats. A recorded active attempt is not proof that an agent is still
running. Quote timestamps remain separate from status checks; reloading the page
does not collect prices, run research, or execute trades. No scheduler is enabled.

## Apply an approved decision once

`apply_decision.py` records a paper purchase/sale directly in the account ledger;
it does not launch a simulator, place broker orders, or run an LLM. Explicitly
select the expert and immutable decision ID, and record the user's authorization:

```sh
.venv-portfolio/bin/python portfolio/apply_decision.py \
  --expert defensive --decision <approved-decision-id> \
  --authorization 'User requested direct Python paper-ledger application'
.venv-portfolio/bin/python portfolio/refresh.py
```

The apply command uses newly collected, completed regular-session minute prices
no older than 180 seconds. It sizes whole shares from current marked NAV,
preserves the decision's price limits, 30% security cap and 10-bps cost assumption,
and commits the entire basket atomically. An append-only timing amendment keeps
the original next-open decision intact. Repeating the same decision is a no-op,
even after a crash following the authoritative account write. No cached-price
fallback or automatic retry is used for purchases. Closed markets, missing prices
and unsupported corporate actions leave the account unchanged.

Only `refresh.py` belongs in a five-minute valuation job. It never reapplies a
decision. Account JSON remains the fixed-format source of cash and holdings;
the HTML and portfolio JSON are derived views. No timer is enabled here.

## Refresh values

Run from the repository root (no LLM, research or trading):

```sh
.venv-portfolio/bin/python portfolio/refresh.py
```

One-time setup with Python 3.10 or later:

```sh
python3 -m venv .venv-portfolio
.venv-portfolio/bin/python -m pip install -r portfolio/requirements.txt
```

The dedicated environment supplies `yfinance` and `exchange_calendars` without
changing runtime packages pinned by earlier trading experiments.
Price collection runs in a separate **Python data worker**, not a model process.
It uses at most four workers, two bounded history requests per unique held ticker
(minute prices and corporate actions), and a 35-second hard network-worker
deadline. Shared holdings across experts reuse the same price. Cash-only accounts
make no price requests. There are no automatic retries. This is designed for a
five-minute caller; no scheduling service is installed or activated.

## Fixed files

| File | Role |
| --- | --- |
| `portfolio/experts.json` | Fixed registry: expert IDs, source account paths and expected account IDs. |
| `runs/live-portfolio/portfolio.json` | Fixed-format live read model: cash, holdings, prices, total value, status and provenance. |
| `runs/live-portfolio/prices.json` | Last collected prices, action checks and provider timestamps. |
| `runs/live-portfolio/index.html` | Dashboard reading the live JSON. |
| `runs/live-portfolio/history/YYYY-MM-DD/*.json` | Immutable valuation snapshots; no historical decisions regenerated. |

The **execution ledger remains the only writer of cash and shares**. The refresh
script reads it and projects its balance into the fixed JSON; never edit that
projection to buy or sell. Existing accounts are not moved or re-funded because
their sealed receipts contain paths and hashes. New experts get a registry entry
only after enrollment creates a real paper account. `account: null` means
`not_started`, not a fictitious $100,000 balance.

The registry currently includes all ten experts and the three actual forward
accounts. It deliberately excludes old backtests and the separate SPY plumbing
control. Registry source paths are relative to the repository; command defaults
are independent of the caller's working directory.

## Format and accounting

`portfolio.schema.json` defines version 1 of the output. Example excerpt:

```json
{
  "expert_id": "trend",
  "account_id": "trend-forward-20260909",
  "cash": "84985.9407591552734375",
  "holdings": {"GLD": 37},
  "positions": [{"symbol": "GLD", "shares": 37, "price": "405.38", "market_value": "14999.06", "price_as_of": "2026-09-09T18:13:00Z", "status": "fresh"}],
  "total_value": "99985.0007591552734375"
}
```

The excerpt is illustrative, not a new market observation. Decimal amounts are
strings; shares are positive integers; unavailable values are `null`. Total value
is cash plus shares times prices. Simple P/L is total value minus initial capital;
it is withheld for recognized subsequent external cash flows. No interest, taxes
or unrecorded dividends are invented. Split/dividend events after the account's
basis date require execution-ledger reconciliation, so the affected valuation
is withheld. Different expert funding dates are not directly comparable.

## Purchase prices and decision evidence

The dashboard separates **Avg. buy price (fill)** from **Latest market price**.
The former is the weighted-average recorded paper fill price for shares still
held, including simulated slippage but excluding fees. **Cost basis** includes
purchase fees. Partial sells reduce both balances proportionally; this is a
display-only weighted-average method, not tax-lot accounting. Slippage is already
inside the fill price and is never added twice. Missing, unsupported or
unreconciled acquisition histories leave cost and holding P/L unavailable.

**Unrealized P/L** is holding market value minus remaining cost basis.
**Account P/L since funding** is total account value minus initial funding;
these are distinct measures. The `price` field remains the timestamped market
observation for backward compatibility; it is never a purchase-price field.

Positions retain the decision IDs associated with their remaining acquisition
history. Each expert's `decisions` contains the recorded rationale, review
warnings, and execution-policy changes separately. Exact research and evidence
JSON files are hash-checked against the sealed decision and copied to
`runs/live-portfolio/evidence/<sha256>.json`; missing or mismatched files receive
no verified link. Decision receipts are projected under `decisions/<sha256>.json`.
A hash match establishes artifact identity, not investment correctness. Generic
registered HTML reports remain separately labeled as latest research reports.
The snapshot links immutable copies, so later source edits cannot silently
change the evidence behind an earlier saved snapshot.

## Failure and concurrency rules

- A nonblocking lock skips overlapping refreshes. Account files are read-only.
- Source hashes/revisions bind balances. If an account changes during the price
  fetch, it is labelled `account_changed` and its total withheld for this refresh.
- Missing/invalid prices never become zero. Last saved valid prices can appear
  with `stale` status and their original timestamps; they are not live values.
- During the regular session, prices older than ten minutes are stale. Outside
  the session, the last scheduled close is labelled `market_closed`. XNYS supplies
  the US-equity reference calendar, including holidays and early closes.
- The newest incomplete minute is excluded. Provider metadata must identify a
  supported USD US listing. Yahoo prices/actions are not independently audited,
  guaranteed real-time, or licensed for redistribution by this code.
- Historical snapshot and HTML are written atomically, with the live JSON
  published last. A failed write does not partially replace the prior live JSON.
  Each snapshot includes its small normalized price observations, original
  provider bar values, retrieval times and action checks for later auditing.
- Exit codes: `0` successful or overlapping run skipped; `2` degraded account or
  price data (page still updated); `1` configuration/infrastructure failure.

For an offline rebuild: `.venv-portfolio/bin/python portfolio/refresh.py --offline`.
The browser checks the saved JSON every 15 seconds, but it **does not fetch prices**.
Run the Python command every five minutes through an explicitly enabled scheduler
when ready. No timers have been enabled by this implementation.

Open through the existing local server:
`http://127.0.0.1:8783/live-portfolio/`.
Generated balances, provider data and history stay in ignored `runs/`; only the
code, schema and registry belong in source control. No public upload is performed.

## Ongoing research workspace

Arena separates the portfolio overview, dated activity and research library.
Each expert has a persistent workspace rather than a detail card appended to a
report. Sorting, filtering and pagination operate on recorded events; no sample
history or inferred trades are added. Data diagnostics remain secondary.

`research_history` indexes every sealed decision report and scheduler report
artifact that has a recorded path and hash. Reports without decisions can appear
independently. A matching scheduler artifact and decision report are deduplicated.
Missing or changed artifacts remain unavailable, not successful reports.

Historical reports open an escaped reading view under
`research/<content-hash>/index.html`, generated deterministically from the exact
hash-verified JSON. This is formatting, not fresh analysis; original draft labels,
metadata and limitations remain present. The current registered styled report is
separately available as the latest report and is never reused as an old decision's
report. Reports/decisions in this archive are limited to the registered account
and scheduler records; unrelated old experiments are deliberately not imported.
