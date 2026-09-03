---
name: finrunbook
description: Orchestrate evidence-first financial research from a user's question by clarifying material scope, selecting and sequencing specialist finance skills, and recording sources, evidence, facts, calculations, assumptions, and artifacts in a structured run file. Use for company, sector, market, earnings, valuation, accounting, SEC-filing, or investment-research tasks that may need multiple skills or an auditable output. Always finish by invoking the finrunbook-validator skill.
---

# FinRunbook

Turn a financial question into a reproducible research run, not a one-off
answer. Treat specialist skills as methods; treat the run record as the source
of truth.

## Start the run

1. Find the repository root containing this skill and `vendor/`.
2. Parse the request into subject, task type, as-of date, time span, audience,
   language, output formats, depth, and source constraints.
3. Ask the user when a missing choice would materially change the research.
   Good questions concern period, as-of date, audience, geography, comparison
   set, deliverable, or permission to use a paid source. Ask questions together
   when possible, but ask later too if evidence exposes a consequential
   ambiguity. Do not ask merely to confirm obvious defaults.
4. If the user is unavailable, continue with explicit defaults: their language,
   Markdown, information available as of today, primary sources first, and five
   fiscal years plus the latest interim period for public-company analysis.
5. Initialize `runs/<run-id>/research-record.json` with
   `scripts/new_run.py`. Record the raw request, clarifications, and every
   default or assumption before collecting evidence.

Read `references/orchestration.md` when selecting skills. Read
`references/run-record-schema.md` before editing the run record.

## Select the smallest useful skill set

Search `vendor/**/SKILL.md`, then read the complete file for each candidate
selected. Choose skills because their required inputs and outputs fit the
request, not because they exist. Prefer one lead analytical skill plus only the
data, document, model, and presentation skills it actually needs.

Record every selected skill in `plan.selected_skills`, including repository,
relative path, pinned commit, purpose, required inputs, expected output, and
execution order. If a skill requires unavailable credentials, a proprietary
terminal, or an unlicensed dataset, ask for access or choose a documented
fallback. Never imply that installing a skill grants data rights.

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

## Produce artifacts

Build deliverables from facts and calculations in the run record. Every
material sentence, number, chart, or table must resolve to source IDs, evidence
IDs, or a documented calculation. In Markdown, cite sources as `[^SRC-001]`.
For charts or slides, keep the same IDs in notes, metadata, or the accompanying
report.

Add each output to `artifacts` and set its status to `draft`. A polished visual
does not supersede the structured record.

## Validate before completion

Invoke `finrunbook-validator` on the run directory after all draft artifacts
exist. Resolve every blocking issue it reports and rerun it. Deliver an artifact
as final only when the validator has written `validation.json`, updated the run
record and report source block, and returned `PASS` or an explicitly disclosed
`PASS_WITH_WARNINGS`.
