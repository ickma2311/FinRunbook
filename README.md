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
skills/finrunbook-market-data/ optional prices, volume and benchmark evidence
skills/finrunbook-tone-review/ language-aware financial editorial pass
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
| `agent-toolkit` | English clarity and concision via `writing-clearly-and-concisely`, subject to financial tone guardrails | MIT |
| `readable-human-writing` | Chinese editorial polish when the resolved report language is Chinese | MIT |

Each library remains independently licensed. See `THIRD_PARTY_NOTICES.md` and
the `LICENSE` file inside each submodule before redistribution or commercial
use. Some skills depend on paid APIs, MCP servers, or data whose terms are
separate from the repository's code license.

## Clone

```bash
git clone --recurse-submodules https://github.com/ickma2311/FinRunbook.git
cd FinRunbook
```

For an existing clone:

```bash
git submodule update --init --recursive
```

## Use with an agent

Ask the agent a normal question, for example:

> Compare the durable growth drivers and principal risks of Datadog and
> Cloudflare over FY2021-FY2025. Produce an interactive financial report for an
> investor and use primary filings wherever possible.

The orchestrator asks only questions whose answers materially change the work,
such as the as-of date, time span, audience, or output format. If the user does
not answer, it records explicit defaults instead of silently guessing.

Every new run ends with `finrunbook-tone-review` before regeneration and final
validation. Reports follow **an explicit output-language request, otherwise the
main language of the current request, otherwise English if undetermined**.
Chinese requests therefore produce Chinese reports unless another output
language is specified. English prose uses the
pinned `writing-clearly-and-concisely` skill; Chinese prose uses
`readable-human-writing` in polish-only mode. Other languages use FinRunbook's
financial editorial rules without being translated. The review preserves figures, citations, uncertainty,
rankings, and the finance-report structure, and records an internal
`editorial-review.json` change log.

To initialize a run manually:

```bash
python3 skills/finrunbook/scripts/new_run.py \
  --subject "Datadog vs Cloudflare" \
  --request "Compare durable growth drivers and principal risks" \
  --start-date 2021-01-01 \
  --end-date 2025-12-31
```

For manual initialization, pass `--language en` when the user explicitly asks
for an English report, even if the request is Chinese. Otherwise pass the
request's main language with `--request-language zh-CN` (or `en`, `es`, etc.).
With neither flag, the helper recognizes predominantly Chinese prose and
otherwise falls back to English. The agent, not this limited heuristic, must
interpret explicit output-language instructions and ambiguous mixed text.
The resolved language and its selection basis are saved in the run record.

To validate a completed run:

```bash
python3 skills/finrunbook-validator/scripts/validate_run.py \
  runs/<run-id>
```

Validation writes `validation.json`, updates `research-record.json`, and
updates presentation-data validation status (or generated validation and source
blocks in an explicitly requested Markdown memo). A failed run
returns a non-zero exit code. The validator never invents a citation: it marks
the claim `[SOURCE NEEDED]` or leaves a blocking issue instead.

## Run contract

Every run contains at least:

- `research-record.json`: canonical structured state;
- `report/index.html` and `report/report-data.json`: default report surface and
  structured presentation data (or explicitly requested exports);
- `editorial-review.json`: final editorial review and wording changes;
- `validation.json`: validator result and issue list.

The detailed contract is in
`skills/finrunbook/references/run-record-schema.md`.

Generated runs stay local: Git ignores everything under `runs/` except
`runs/README.md`. Do not force-add research records, provider snapshots, or
reports. Review data rights and remove sensitive information before publishing
selected examples separately.

## Tests

Run the synthetic workflow and market-data tests without API keys or network
access:

```bash
python3 -m unittest discover -s tests -v
```

## Optional market data

For prices, event reactions or benchmark comparisons, the router selects
`skills/finrunbook-market-data/`. Its first adapter uses the optional pinned
`yfinance` dependency; no paid provider or API key is configured. Install its
`requirements.txt` in your Python environment and follow its `SKILL.md` for the
collector command. Pure operating/industry analysis does not require it.

The collector preserves response snapshots, request parameters, timestamps and
ledger mappings. Validation checks hashes and recomputes supported metrics;
it does not independently verify the vendor or infer who sold. Yahoo's data-use
terms are separate from the client's open-source license. Downloaded market
snapshots are ignored by Git by default and must not be copied into public demos
without checking redistribution rights. Synthetic tests require no network.
Ignoring snapshots does not establish rights for provider values copied into
research records or public report files; review those before publishing too.

## Project status

This is an initial, working orchestration and validation foundation. It does
not bundle third-party API keys, paid data rights, or investment advice.
No license has yet been selected for FinRunbook's own code. Third-party
submodules retain their respective licenses, listed in `THIRD_PARTY_NOTICES.md`.
