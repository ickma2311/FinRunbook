# Research run record

`research-record.json` is the canonical state of a FinRunbook run. It is
append-friendly and designed to survive handoffs between agents.

## Required top-level fields

| Field | Purpose |
| --- | --- |
| `schema_version` | Contract version; currently `1.0.0` |
| `run` | ID, timestamps, status, and repository revision |
| `request` | Raw request, normalized scope, clarifications, assumptions |
| `plan` | Selected skills and ordered execution steps |
| `sources` | One entry for every acquired source |
| `evidence` | Exact source excerpts, cells, or values with locators |
| `facts` | Assertions with provenance and epistemic status |
| `calculations` | Reproducible transformations of facts |
| `artifacts` | Generated outputs and their status |
| `validation` | Latest validation status and issue summary |

Start from `assets/research-record.template.json` or use `scripts/new_run.py`.

## Identifier conventions

- sources: `SRC-001`, `SRC-002`, ...
- evidence: `EVD-001`, `EVD-002`, ...
- facts: `FACT-001`, `FACT-002`, ...
- calculations: `CALC-001`, `CALC-002`, ...
- issues: `ISSUE-001`, `ISSUE-002`, ...

IDs are stable within a run. Never renumber an ID after an artifact cites it.

## Source entry

Required: `id`, `type`, `title`, `publisher`, `retrieved_at`, and at least one
of `url` or `local_path`.

Recommended fields include `published_at`, `as_of_date`, `filing_type`,
`accession_number`, `period_end`, `primary`, `license_or_terms`, `sha256`, and
`notes`. A URL identifies the exact document, not a search-results page.

## Evidence entry

Required: `id`, `source_id`, `locator`, and `content`. `locator` must be
specific enough for another reviewer to find the item. Add `period`, `units`,
`currency`, and `extracted_at` when relevant. Keep excerpts short; respect
copyright and data terms.

## Fact entry

Required: `id`, `statement`, `status`, `material`, `source_ids`, and
`evidence_ids`.

Allowed statuses:

- `company-reported`: accurately transcribed but not independently confirmed;
- `verified`: checked against the cited evidence and applicable calculation;
- `calculated`: derived from recorded inputs;
- `inferred`: an analytical interpretation, not a reported fact;
- `conflicting`: credible sources disagree;
- `insufficient-evidence`: support is missing or too weak.

Optional numeric fields are `value`, `units`, `currency`, `period`, and
`confidence`. Never encode confidence as a substitute for evidence.

## Calculation entry

Record `id`, human-readable `description`, `expression`, `input_fact_ids`,
`result`, `units`, and `rounding`. Use explicit formulas such as
`(FACT-003.value / FACT-002.value) - 1`, not “calculated growth.”

## Artifact entry

Record a path relative to the run directory, format, language, status, and the
fact IDs used. Allowed statuses are `draft`, `validated`, and `blocked`.

## Update discipline

Write the source before its evidence, the evidence before its fact, and facts
before artifacts. Update `run.updated_at` after each research batch. Store a
source body locally only if its terms allow it; otherwise store metadata,
locators, and short compliant excerpts.

