# Orchestration guide

## Routing sequence

1. Classify the question: company, earnings, filing, valuation, sector,
   accounting, portfolio, market, or presentation.
2. Classify the artifact as `finance-report` or `research-memo`. Default
   financial company/sector/earnings work to `finance-report`; do not infer
   `research-memo` merely because the request asks for greater depth, a deep
   dive, or many sources. Reserve it for an explicit Deep Research mode or a
   literature-, methodology-, or evidence-mapping deliverable.
3. Identify the decision use and required evidence: filings, statements, prices, estimates,
   transcripts, macro series, internal files, or user-supplied data.
4. Select a lead skill that defines the analytical structure.
5. For `finance-report`, identify the comparable financial panel, sector KPI
   panel, bridge or ranking, and valuation need before research begins.
6. Add data or document skills only for inputs the lead skill cannot obtain.
7. Add modeling or artifact skills required by the output contract. A report
   that claims financial winners and losers usually needs structured extraction
   or modeling even when its visual implementation is simple.
8. Run `skills/finrunbook-tone-review/SKILL.md` after drafting/translation;
   preserve the analytical structure and protected facts, then regenerate
   affected outputs. Use the router's resolved report language, not an English
   default applied again at editing time. English uses the pinned
   `vendor/agent-toolkit/skills/writing-clearly-and-concisely/SKILL.md`;
   Chinese uses `vendor/readable-human-writing/SKILL.md` in `polish-only` mode,
   including when inferred from the current request. Explicit output-language
   requests override the main request language; English is the final fallback.
9. End with `finrunbook-validator` on the post-edit artifacts.

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
| Prices, volume, returns and benchmark comparisons | `skills/finrunbook-market-data/` (Yahoo adapter first; optional dependency, explicit data-use limits) |
| Other market or estimate data | `vendor/finance-skills/plugins/data-providers/skills/`, `vendor/octagon-skills/skills/analyst-estimates/`; verify actual tool/credential availability |
| Slides or interactive output | Anthropic `pptx-author` skills for slides; `references/interactive-report-profile.md` for the portable web report. The current `generative-ui` skill is limited to an in-chat widget. |
| Final tone and editorial review | `skills/finrunbook-tone-review/`; English uses `vendor/agent-toolkit/skills/writing-clearly-and-concisely/`; Chinese uses `vendor/readable-human-writing/` |

Paths are hints, not a fixed menu. Search all `SKILL.md` files because
submodule contents change when deliberately upgraded.

## Selection rules

- Reuse the strongest analytical workflow, but do not inherit an unavailable
  data dependency without checking it.
- Treat a generic `sector-overview` or `competitive-analysis` skill as a report
  outline, not a substitute for comparable financial extraction and modeling.
- Prefer an equity-research workflow for investor-facing company and sector
  analysis; prefer the market-researcher workflow for a deliberately descriptive
  landscape or non-financial market-entry study.
- Do not select a conversation-hosted widget skill as the primary renderer for
  a FinRunbook finance report. In particular, the current `generative-ui` skill
  depends on Claude's `show_widget` runtime. It can inform a one-off in-chat
  view, but the final report must be a portable static application driven by
  `report-data.json`.
- Record the selected submodule commit from `git submodule status`.
- Avoid duplicate skills that produce the same intermediate result.
- For price-based work, use the local market-data collector to keep timestamp,
  adjustment, source and calculation conventions consistent. Preserve failed
  attempts and review incomplete/stale bars before using the observations.
  Do not select a second technical-analysis skill solely to retrieve the same
  history. Installing a provider skill does not connect its MCP server.
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
- finance report versus research memo; ask only when the request genuinely
  supports both and the decision use cannot be inferred.

Record the answer and timestamp in `request.clarifications`. If proceeding
without an answer, store the chosen assumption in `request.assumptions`.
