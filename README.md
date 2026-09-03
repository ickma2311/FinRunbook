# FinRunbook

FinRunbook is an evidence-first runtime for financial research skills. It does
three things that a loose collection of prompts does not:

1. routes a user's request to the smallest useful set of specialist skills;
2. records sources, evidence, facts, calculations, decisions, and artifacts in
   a machine-readable run record while the work is happening; and
3. runs a fail-closed validation pass that updates the report with source
   citations and leaves unsupported claims visibly unresolved.

The project is agent-neutral. `AGENTS.md` and `CLAUDE.md` point Codex and Claude
Code at the same workflow.

## Repository layout

```text
skills/finrunbook/             router and run-record workflow
skills/finrunbook-validator/   final validation and citation workflow
vendor/                        pinned third-party skill repositories
runs/<run-id>/                 generated records and deliverables
```

## Installed skill libraries

| Submodule | Typical strengths | License |
| --- | --- | --- |
| `anthropic-financial-services` | equity research, earnings, valuation, models, decks | Apache-2.0 |
| `finance-skills` | market data, valuation, earnings, startup research, UI | MIT |
| `octagon-skills` | SEC filings, financial statements, earnings and market data | MIT |
| `finance-accounting-skills` | accounting, audit, planning, treasury and valuation | MIT |

Each library remains independently licensed. See `THIRD_PARTY_NOTICES.md` and
the `LICENSE` file inside each submodule before redistribution or commercial
use. Some skills depend on paid APIs, MCP servers, or data whose terms are
separate from the repository's code license.

## Clone

```bash
git clone --recurse-submodules <repo-url>
cd FinRunbook
```

For an existing clone:

```bash
git submodule update --init --recursive
```

## Use with an agent

Ask the agent a normal question, for example:

> Compare the durable growth drivers and principal risks of Datadog and
> Cloudflare over FY2021-FY2025. Produce a Chinese Markdown report for a
> technically sophisticated investor and use primary filings wherever possible.

The orchestrator asks only questions whose answers materially change the work,
such as the as-of date, time span, audience, or output format. If the user does
not answer, it records explicit defaults instead of silently guessing.

To initialize a run manually:

```bash
python3 skills/finrunbook/scripts/new_run.py \
  --subject "Datadog vs Cloudflare" \
  --request "Compare durable growth drivers and principal risks" \
  --start-date 2021-01-01 \
  --end-date 2025-12-31 \
  --language zh-CN \
  --format markdown
```

To validate a completed run:

```bash
python3 skills/finrunbook-validator/scripts/validate_run.py \
  runs/<run-id>
```

Validation writes `validation.json`, updates `research-record.json`, and
refreshes generated validation and source blocks in `report.md`. A failed run
returns a non-zero exit code. The validator never invents a citation: it marks
the claim `[SOURCE NEEDED]` or leaves a blocking issue instead.

## Run contract

Every run contains at least:

- `research-record.json`: canonical structured state;
- `report.md`: human-facing output (or a manifest pointing to another format);
- `validation.json`: validator result and issue list.

The detailed contract is in
`skills/finrunbook/references/run-record-schema.md`.

## Project status

This is an initial, working orchestration and validation foundation. It does
not bundle third-party API keys, paid data rights, or investment advice. The
license for FinRunbook's own code should be selected before publishing the
repository; third-party notices are already separated so that decision does
not alter the submodules' licenses.

