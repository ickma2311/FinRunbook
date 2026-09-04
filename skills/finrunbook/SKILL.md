---
name: finrunbook
description: Orchestrate evidence-first financial research from a user's question into a finance-industry report or an explicitly requested research memo. Clarify material scope, select and sequence specialist finance skills, build comparable financial analysis, and record sources, evidence, facts, calculations, assumptions, and artifacts in a structured run file. Use for company, sector, market, earnings, valuation, accounting, SEC-filing, or investment-research tasks that may need multiple skills or an auditable output. Always finish by invoking the finrunbook-validator skill.
---

# FinRunbook

Turn a financial question into a reproducible, decision-useful financial
analysis, not a one-off answer. Treat specialist skills as methods; treat the
run record as the source of truth.

## Choose the report archetype first

Classify both the subject and the required artifact before choosing specialist
skills:

- Use `finance-report` by default for company, sector, market, earnings,
  valuation, credit, accounting, and investment-analysis requests. Its depth
  changes coverage and model detail, not the amount of methodological prose.
- Use `research-memo` only when the user explicitly asks for deep research,
  literature review, methodology, evidence mapping, or an open-ended thematic
  investigation without a financial decision lens.
- Follow an explicit user choice of memo, deck, model, webpage, or another
  artifact. Artifact format does not change the analytical archetype.

For `finance-report`, read and follow
`references/finance-report-profile.md` and
`references/interactive-report-profile.md`. Record the archetype and decision
use in the run. Do not let the evidence ledger dictate the narrative structure.

## Start the run

1. Find the repository root containing this skill and `vendor/`.
2. Parse the request into subject, task type, report archetype, decision use,
   as-of date, time span, audience, language, output formats, depth, and source
   constraints.
3. Ask the user when a missing choice would materially change the research.
   Good questions concern period, as-of date, audience, geography, comparison
   set, deliverable, or permission to use a paid source. Ask questions together
   when possible, but ask later too if evidence exposes a consequential
   ambiguity. Do not ask merely to confirm obvious defaults.
4. Resolve report language in this order: an explicitly requested output
   language, otherwise the main language of the current research request,
   otherwise English when the language cannot be determined. Infer language
   from the user's instructions, not quoted sources, company names, tickers,
   English financial terms, or the language of this skill. For mixed-language
   requests, use the main instruction language; clarify only if the choice is
   genuinely ambiguous and consequential. Do not carry the product's English
   audience preference over a clear Chinese request.
   Other defaults are an interactive static web report backed by structured JSON,
   `finance-report`, a finance-professional audience, information available as
   of today, primary sources first, and five fiscal years plus the latest
   interim period for public-company analysis. Infer the decision use from the
   request; use investment research for company and sector work when no
   operator, lender, transaction, or academic lens is evident.
5. Initialize `runs/<run-id>/research-record.json` with
   `scripts/new_run.py`. Pass an explicit user output-language choice through
   `--language`; otherwise pass the inferred main request language through
   `--request-language`. Do not pass `--language en` as a routine default.
   The CLI's unflagged Chinese-prose heuristic is only a convenience fallback,
   not a parser for explicit language instructions or every language. The agent
   must interpret requests such as “分析 Tesla，用英文输出” as `--language en`
   and “Analyze Tesla, write the report in Chinese” as `--language zh-CN`.
   Record the resolved language and its selection basis along with the raw
   request, clarifications, and assumptions before collecting evidence. Use it
   consistently in report prose, UI labels, exports, and presentation metadata;
   preserve source quotations, identifiers, and technical terms when needed.

Read `references/orchestration.md` when selecting skills. Read
`references/run-record-schema.md` before editing the run record.

## Select the smallest useful skill set

Search `skills/*/SKILL.md` and `vendor/**/SKILL.md`, then read the complete file for each candidate
selected. Choose skills because their required inputs and outputs fit the
request, not because they exist. Prefer one lead analytical skill plus only the
data, document, model, and presentation skills it actually needs. Include
`finrunbook-tone-review` as the final language pass before validation.

When the analysis needs prices, valuation-date prices, trading volume, returns
or benchmark comparisons, select `skills/finrunbook-market-data/SKILL.md`.
It records provider observations and calculations directly in the run ledger;
do not rewrite a one-off Yahoo downloader. Confirm the security identity first,
and preserve its adjustment, session and timestamp boundaries. Do not add it to
a purely operating/industry report that does not use market prices. Market
data do not replace SEC/IR financials or establish who traded or why.

Record every selected skill in `plan.selected_skills`, including repository,
relative path, pinned commit, purpose, required inputs, expected output, and
execution order. If a skill requires unavailable credentials, a proprietary
terminal, or an unlicensed dataset, ask for access or choose a documented
fallback. Never imply that installing a skill grants data rights.

For a finance report, a generic sector or company narrative skill is not
sufficient by itself. Add the extraction, comparable-metrics, statements,
valuation, or model-building method needed to populate the output contract.
When a specialist skill assumes unavailable data, preserve its analytical
structure and document a primary-source fallback rather than silently dropping
the financial model.

## Research with an evidence ledger

Update `research-record.json` throughout execution—not only at the end.

- Add a `sources` entry immediately after acquiring a document or dataset.
- Add evidence with an exact page, section, table, cell, line, or filing anchor.
- Add each material assertion to `facts`; attach its source and evidence IDs.
- Store transformations in `calculations`, including inputs, expression,
  period, currency, units, and rounding.
- Distinguish reported facts, verified facts, calculations, inferences,
  conflicts, and insufficient evidence.
- Keep estimates, guidance, actual results, fiscal periods, calendar periods,
  and trailing periods separate.
- Preserve contradictory evidence. Do not overwrite it with a preferred value.
- Do not store secrets or source bodies whose redistribution terms forbid it.

Prefer issuer filings and official regulators for reported company facts,
official statistics for macro facts, and original datasets or first-party
documentation for methodology. Use secondary sources for context or discovery,
and label them accordingly.

## Build the analytical model before prose

For `finance-report`, define the coverage universe, comparison periods, metric
dictionary, sector-specific KPIs, and any valuation or share proxies before
drafting. Normalize comparable metrics and keep non-comparable metrics in
separate panels. A missing estimate or proprietary market-share series is not
permission to invent precision; use a labeled proxy, show the calculation and
confidence, or state `not available`.

Lead with measured outcomes and the analyst's view. Keep source mechanics,
epistemic classifications, and extended caveats in the methodology or appendix
unless they change the decision. The report should read as an analysis built
from an evidence ledger, not as a narration of the evidence-collection process.

## Produce artifacts

Build deliverables from facts and calculations in the run record. Every
material sentence, number, chart, or table must resolve to source IDs, evidence
IDs, or a documented calculation. Put those IDs in the structured presentation
data and expose them through the report's source drawer. For charts, slides, PDF
or spreadsheets, keep the same IDs in notes, metadata, or an accompanying data
artifact.

A `finance-report` does not use Markdown as its final product surface. Its
default deliverables are `report/index.html` and
`report/report-data.json`: a portable, responsive static application that can
be opened from any ordinary static host. PDF, XLSX, or PPTX are optional exports
when the decision or user requires them. Markdown remains available for an
explicit `research-memo`, but is not a hidden prerequisite for the web report.

Add each output to `artifacts` and set its status to `draft`. A polished visual
does not supersede the structured record.

## Review tone and validate before completion

Read and run `skills/finrunbook-tone-review/SKILL.md` from the repository root
after drafting and any requested translations. It uses
`writing-clearly-and-concisely` for English reports and
`readable-human-writing` for Chinese reports, whether explicitly requested or
inferred from the current request, with the financial-report
structure and factual content protected. Record the review, regenerate affected
outputs, and then validate.
The closing sequence is tone review → regeneration → validator → delivery;
never leave unvalidated tone edits as the final step.

Invoke `finrunbook-validator` on the run directory after all draft artifacts
exist. Resolve every blocking issue it reports and rerun it. Deliver an artifact
as final only when the validator has written `validation.json`, updated the run
record and report source block, and returned `PASS` or an explicitly disclosed
`PASS_WITH_WARNINGS`.
