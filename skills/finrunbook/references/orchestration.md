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
   [English writing instructions](https://github.com/softaworks/agent-toolkit/blob/3027f20f3181758385a1bb8c022d4041dfb4de84/skills/writing-clearly-and-concisely/SKILL.md);
   Chinese uses [Chinese writing instructions](https://github.com/KG3KAI/readable-human-writing/blob/cc669c7427ed921ffe15fae6fd91d8d4b9280676/SKILL.md) in `polish-only` mode,
   including when inferred from the current request. Explicit output-language
   requests override the main request language; English is the final fallback.
9. End with `finrunbook-validator` on the post-edit artifacts.

## Skill dictionary

Use [the central dictionary](../../index.md) for first-party instructions and
pinned upstream references. Check an entry's dependencies before selecting it;
an upstream instruction link does not install a provider or make it locally usable.

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
- Record the selected instruction URL and the immutable commit in that URL.
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
