# FinRunbook

Financial research in Codex, using local Python for evidence records, market-data
processing and validation. Research covers companies, earnings, industries,
financial statements, valuation and market prices. Radar helps discover topics
and organize follow-up reports.

This branch builds the `0.5.0-preview.1` candidate: one Finrun skill, a pinned
GitHub method catalog, local evidence checks, and portable HTML/CSV rendering.
The candidate is built locally; installation and public release are separate.
See [plugin packaging](plugin/README.md) for first-run catalog requirements.

## Repository layout

```text
skills/     Central index, research instructions and shared Python helpers
plugin/     Manifest, runtime allowlist and deterministic packaging
run/        Ignored outputs, downloads, caches, environments and builds
tests/      Public research and repository regression checks
examples/   Curated published reports and prompts
```

[skills/index.md](skills/index.md) describes the selectable methods. They are
retrieved as Markdown at immutable commits and cached with content hashes.
Methods are kept outside the plugin so instruction updates do not ship executable
code. Historical upstream attribution remains in [third-party notices](THIRD_PARTY_NOTICES.md).

All maintained Python helpers and their templates live in
[skills/finrun/](skills/finrun/README.md). Existing skill documents link to those
helpers; there is no second editable copy for packaging.

## Use from the repository

Clone normally, with no submodule initialization:

```bash
git clone https://github.com/ickma2311/FinRunbook.git
cd FinRunbook
```

Open this directory in Codex and ask a financial question. The research entry
point is `skills/finrun/SKILL.md`, including Radar topic discovery. Codex collects and reviews evidence. Python
does not invoke a model, run another agent CLI, schedule research or execute trades.
Use local Python 3.10 or newer. Core helpers use the standard library.

For direct helper use, from the project directory:

```bash
python3 skills/finrun/scripts/new_run.py \
  --compact --subject "Example company" --request "Analyze the latest earnings" \
  --request-language en
python3 skills/finrun/scripts/new_batch.py \
  --request "Find recent financial research topics" --language en \
  --timezone America/Los_Angeles
python3 skills/finrun/scripts/validate_run.py run/<run-id>
```

Initializers write to `run/` in the current working directory. The existing
`--runs-dir` flag remains available for explicit destinations and older scripts.
Creating a run produces a draft, not a completed financial report.

The optional Yahoo adapter requires the pinned dependency. Install it only when
needed in a workspace-local environment:

```bash
python3 -m venv run/.venv
run/.venv/bin/python -m pip install -r skills/finrun/requirements-market-data.txt
```

Follow the [market-data instructions](skills/finrunbook-market-data/SKILL.md)
for identity, dates, adjustments, provider failures and data-use limits.

## Evidence and completion

Keep sources, evidence locators, facts, calculations, assumptions and limitations
in `research-record.json`. Preserve fiscal periods, units, currency, comparable
definitions and the distinction between actual results and guidance. Follow the
user's output language independently of market geography.

The compact workflow records its method receipt and a short review with reviewer
identity and actual checks performed. The validator checks structure, provenance
and supported arithmetic;
a pass does not establish that a source or narrative claim is true. Review material
claims against source passages and verify HTML behavior separately.

Generated records, caches and builds stay under ignored `run/`. Curate intentionally
public outputs into `examples/` only after reviewing source rights. Historical
examples retain their original records and URLs.

## Tests

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Tests use synthetic data and local fixtures. They do not require Yahoo access,
an MCP server, vendor checkouts or internal investing code. Offline tests do not
prove current provider availability or live remote-catalog retrieval.

## Migration boundaries

Internal investing, portfolio accounting, hourly operation and their tests are
excluded from the active product. Original sources and historical runs remain
in the original checkout; a verified source archive supports this worktree refactor.
Original-folder cleanup and historical-run migration are deferred until the new
version is verified. External packaging sources and deployed services are untouched.
Plugin installation, catalog publication and deployment remain separate work.
Legacy `finrunbook-*` documents remain available for older records and are not
part of the new plugin bundle.

## Live examples

Start with a question and see a worked answer: what changed in earnings, which
numbers belong in your spreadsheet, or how companies compare. Read the report,
download its data, or adapt the prompt for your own companies. No agent,
installation or financial API key is needed to view the saved examples.

- [Review earnings: what changed?](https://ickma2311.github.io/FinRunbook/#earnings-update) — Lululemon, with comparable financials, margin adjustments and an editable table.
- [Prepare comparable financial data](https://ickma2311.github.io/FinRunbook/#data-cleaning) — three worked cases covering units/signs, quarter versus year-to-date, and cloud disclosure boundaries; download inputs, cleaned data, definitions and exceptions.
- [Compare companies before deeper research](https://ickma2311.github.io/FinRunbook/#company-comparison) — AWS, Azure and Google Cloud, keeping disclosure differences visible.
- Additional walkthrough: [check a thesis against new evidence](https://ickma2311.github.io/FinRunbook/#thesis-check) — a clearly labeled retrospective Lululemon illustration, not a tracked customer thesis.

Browse the full reports in English and Chinese:

- [Lululemon: earnings deterioration and recovery scenarios](https://ickma2311.github.io/FinRunbook/lululemon-earnings-update/report/)
- [Apple: business quality, FY2021–FY2025](https://ickma2311.github.io/FinRunbook/apple-business-quality/report/)
- [Cloud computing: AWS, Azure, and Google Cloud, 2021–2025](https://ickma2311.github.io/FinRunbook/cloud-computing/report/)
- [AI infrastructure capex and supplier exposure — English](https://ickma2311.github.io/FinRunbook/ai-infrastructure-capex-supply-chain/report/)
- [六家科技公司的资本配置 — 中文](https://ickma2311.github.io/FinRunbook/big-tech-investment-allocation/report/)
- [AI 产业链：增长、利润与资本回收 — 中文](https://ickma2311.github.io/FinRunbook/ai-industry-value-chain/report/)
- [美股大盘：20年收益与长期持有风险 — 中文](https://ickma2311.github.io/FinRunbook/sp500-20year-return-risk/report/)

[Browse all examples](https://ickma2311.github.io/FinRunbook/) or inspect the
[example packages and limitations](examples/README.md). These are historical
snapshots with September 3–4, 2026 research cutoffs. Each report labels its own
reporting periods; these are not live market dashboards. The S&P 500 / SPY
example retains three market-data validation warnings and excludes raw provider
snapshots. Publishing the analysis does not grant a third-party data license.
