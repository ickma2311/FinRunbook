# Orchestration guide

## Routing sequence

1. Classify the question: company, earnings, filing, valuation, sector,
   accounting, portfolio, market, or presentation.
2. Identify required evidence: filings, statements, prices, estimates,
   transcripts, macro series, internal files, or user-supplied data.
3. Select a lead skill that defines the analytical structure.
4. Add data or document skills only for inputs the lead skill cannot obtain.
5. Add modeling or artifact skills only when the requested output requires them.
6. End with `finrunbook-validator`.

## Useful starting points

| Need | Candidate skill locations |
| --- | --- |
| Company initiation or thesis | `vendor/anthropic-financial-services/plugins/vertical-plugins/equity-research/skills/initiating-coverage/` |
| Earnings analysis | `vendor/anthropic-financial-services/plugins/agent-plugins/earnings-reviewer/skills/earnings-analysis/`, `vendor/finance-skills/plugins/market-analysis/skills/earnings-recap/` |
| Sector overview or competition | `vendor/anthropic-financial-services/plugins/agent-plugins/market-researcher/skills/sector-overview/`, `competitive-analysis/` |
| SEC filings | `vendor/octagon-skills/skills/sec-10k-analysis/`, `sec-10q-analysis/`, `sec-8k-analysis/`, `sec-proxy-analysis/` |
| Statements and segments | `vendor/octagon-skills/skills/income-statement/`, `cash-flow-statement/`, `balance-sheet/`, `sec-segment-reporting/` |
| Valuation and models | `vendor/anthropic-financial-services/plugins/agent-plugins/model-builder/skills/`, `vendor/finance-skills/plugins/market-analysis/skills/company-valuation/` |
| Accounting or audit | `vendor/finance-accounting-skills/skills/financial-analysis/`, `audit-checklist/`, `revenue-recognition/`, `three-statement-modeling/` |
| Market or estimate data | `vendor/finance-skills/plugins/data-providers/skills/`, `vendor/octagon-skills/skills/analyst-estimates/` |
| Slides or interactive output | Anthropic `pptx-author` skills or `vendor/finance-skills/plugins/ui-tools/skills/generative-ui/` |

Paths are hints, not a fixed menu. Search all `SKILL.md` files because
submodule contents change when deliberately upgraded.

## Selection rules

- Reuse the strongest analytical workflow, but do not inherit an unavailable
  data dependency without checking it.
- Record the selected submodule commit from `git submodule status`.
- Avoid duplicate skills that produce the same intermediate result.
- Prefer primary-source extraction over third-party normalized values when the
  question turns on definitions, fiscal periods, or management wording.
- Use structured-provider data for screening and breadth, then verify material
  conclusions against primary documents.
- For private companies, state the evidence boundary early. Do not manufacture
  public-company-style precision from sparse disclosures.

## Material clarifications

Ask when two plausible interpretations lead to materially different work:

- fiscal versus calendar period;
- historical cutoff versus latest available information;
- company-provided peers versus analyst-selected peers;
- reported, adjusted, or both;
- investor, operator, lender, student, or general audience;
- memo, Markdown, spreadsheet, slides, web page, or machine-readable JSON;
- permitted use of paid sources or supplied credentials;
- investment recommendation versus descriptive research.

Record the answer and timestamp in `request.clarifications`. If proceeding
without an answer, store the chosen assumption in `request.assumptions`.

