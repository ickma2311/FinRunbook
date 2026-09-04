# FinRunbook

FinRunbook is an evidence-first runtime for financial research skills. It does
three things that a loose collection of prompts does not:

1. routes a user's request to the smallest useful set of specialist skills;
2. records sources, evidence, facts, calculations, decisions, and artifacts in
   a machine-readable run record while the work is happening; and
3. runs a fail-closed validation pass that updates the report with source
   citations and leaves unsupported claims visibly unresolved.

Use FinRunbook with **Codex, Claude Code, or OpenCode** from the project
directory. `AGENTS.md` defines the shared workflow; `CLAUDE.md` points Claude
Code to those same instructions.

## Live examples

Explore two completed English reports in your browser. No agent, installation,
or financial API key is needed to view them.

- [Apple: business quality, FY2021–FY2025](https://ickma2311.github.io/FinRunbook/apple-business-quality/report/)
- [Cloud computing: AWS, Azure, and Google Cloud, 2021–2025](https://ickma2311.github.io/FinRunbook/cloud-computing/report/)

[Browse all examples](https://ickma2311.github.io/FinRunbook/) or inspect the
[example packages and limitations](examples/README.md). These are historical
reports with a September 3, 2026 research cutoff, not live market dashboards.

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

## Use with Codex, Claude Code, or OpenCode

**Open your agent in the FinRunbook project directory, then ask your research
question.** You do not need to run the Python initialization script yourself.

Have your chosen agent installed and signed in (or configured with a model
provider), with Python 3 available for the workflow helpers. The agent needs
permission to read and write project files, run commands, and retrieve sources.
FinRunbook does not provide model credentials or paid data access.

### 1. Open the FinRunbook project directory

After cloning, stay in the `FinRunbook` folder. If you are opening a new terminal,
change to your clone's location:

```bash
cd /path/to/FinRunbook
```

Replace `/path/to/FinRunbook` with your local path. This is the folder containing
`AGENTS.md`, `CLAUDE.md`, and `skills/`.

### 2. Start your agent in that directory

Run **one** of these commands:

| Agent | Command |
| --- | --- |
| [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) | `codex` |
| [Claude Code](https://code.claude.com/docs/en/quickstart) | `claude` |
| [OpenCode](https://opencode.ai/docs/cli/) | `opencode` |

For a desktop or IDE-based agent, open the **FinRunbook folder as the project**
and start a task there instead.

### 3. Ask your research question

Type your question into the agent, not the shell. For example:

> Use FinRunbook to compare the durable growth drivers and principal risks of
> Datadog and Cloudflare over FY2021-FY2025. Produce an interactive financial
> report for an investor and use primary filings wherever possible.

If your agent has not picked up the project instructions, prepend:

> Read `skills/finrunbook/SKILL.md` and follow its workflow for this request.

The agent handles run initialization, research, report generation, tone review,
and final validation. Generated files stay under `runs/<run-id>/`; the default
interactive report is `runs/<run-id>/report/index.html`. Ask the agent to serve
the report locally and open it in your browser when it is ready.

### What happens next

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

### Optional: manual initialization and validation

These commands are for direct control or debugging. In normal use, the agent
handles these steps as part of the workflow.

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
