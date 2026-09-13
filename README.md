# Finrun for Codex

Turn financial questions into sourced answers, interactive reports and usable
data sheets. **Finrun is one plugin for research and topic discovery in local
Codex.** Analyze companies, earnings and industries, or ask it to find financial
developments worth investigating.

**[Install Finrun](https://chatgpt.com/plugins/plugins_6aa37a5c5a3c8191b0724563dc0166bd)**
· [Website](https://finrun.ickma2311.workers.dev/)
· [Setup guide](https://finrun.ickma2311.workers.dev/setup/)
· [See examples](https://finrun.ickma2311.workers.dev/#examples)

Version **0.5.0-preview.2** is published in the OpenAI Plugins Directory.

## Get started

1. Open the [Finrun plugin listing](https://chatgpt.com/plugins/plugins_6aa37a5c5a3c8191b0724563dc0166bd)
   and install it for Codex.
2. Start a new local Codex task in a writable workspace and select **@Finrun**
   from the plugin picker.
3. Ask your question. Add a period, language or output format when it matters.
4. Review the answer, sources and any generated report or data sheet.

You do not need to clone this repository to use the plugin.
Requires local Codex, Python 3.10+, a writable workspace and access to the
requested sources. This edition is not supported in ChatGPT web. Your agent
usage and any data-provider charges still apply; no separate Finrun account is
needed. See the [setup guide](https://finrun.ickma2311.workers.dev/setup/) for
requirements and troubleshooting.

## Try a question

After selecting **@Finrun**, ask:

- **Company risks:** “Analyze NVIDIA’s main business and financial risks.”
- **Earnings:** “Compare the latest earnings of Microsoft and Alphabet.”
- **Industry research:** “Compare AWS, Azure and Google Cloud.”
- **Data sheets:** “Build an Excel workbook of Apple’s financial statements for
  the last five fiscal years.”
- **Topic discovery:** “Find three financial developments worth researching.”

You always use the same Finrun skill. **Radar is its topic-discovery method**:
ask for a shortlist, or choose topics for further research.

## What you get

| Your request | Output |
| --- | --- |
| A focused question | A concise sourced answer |
| Substantial company, earnings or industry analysis | An interactive HTML report and structured JSON |
| A financial data sheet | CSV by default; request an Excel workbook explicitly for XLSX |
| Topics worth investigating | A shortlist, with follow-up research when requested |

Substantial research keeps sources, evidence, calculations and limitations with
its outputs under `run/` in your task’s workspace. Reports preserve fiscal
periods, units and the distinction between reported results, guidance and
estimates. Local checks support the work, but do not guarantee accuracy.
Review important claims against the original sources. Outputs are research
materials, not personalized investment advice.

## Explore saved examples

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

## For contributors

Clone the repository when you want to develop Finrun, edit its methods or run
the helpers directly:

```bash
git clone https://github.com/ickma2311/FinRunbook.git
cd FinRunbook
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

No submodule initialization is needed. Core helpers use Python 3.10+ and the
standard library. Yahoo market-data support has an optional dependency; see
[helper documentation](skills/finrun/README.md).

```text
skills/     Finrun entry skill, method catalog and shared Python helpers
plugin/     Package manifest, build tooling and public website source
run/        Ignored research outputs, caches, environments and builds
tests/      Research and repository regression checks
examples/   Curated published reports and prompts
```

- [Entry skill](skills/finrun/SKILL.md): the shared research and discovery workflow.
- [Method catalog](skills/index.md): methods retrieved at immutable commits and
  cached with hashes. Method text cannot authorize executable code or expand
  the user's permissions.
- [Plugin packaging](plugin/README.md): build the allowlisted bundle and verify
  it before installation or publication.
- [Website maintenance](plugin/website/README.md): build and deploy the public site.
- [Third-party notices](THIRD_PARTY_NOTICES.md): attribution and applicable notices.

Generated runs and build artifacts stay under ignored `run/`. Preserve historical
examples and their original provenance; publish new examples only after reviewing
source rights. Legacy compatibility documents are excluded from the plugin.
Internal investing, portfolio and scheduled workflows are outside this product.

## Support

[Get support](https://finrun.ickma2311.workers.dev/support/)
· [Report a bug](https://github.com/ickma2311/FinRunbook/issues)
· [Privacy](https://finrun.ickma2311.workers.dev/privacy/)
· [Terms](https://finrun.ickma2311.workers.dev/terms/)
