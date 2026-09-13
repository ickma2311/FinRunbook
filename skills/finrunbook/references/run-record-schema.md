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

New runs also declare `editorial_review.required: true`. The final language pass
records completion, languages, reviewer, upstream skills and their revisions, reviewed
artifacts, a relative `change_log_path`, protected-content preservation, and
unresolved issues. The change log is an internal JSON audit artifact, not a
replacement for the report. Older records without this field remain readable.
`upstream_skills` is a list of `{name, path, commit, languages}` objects for
editors actually applied: English uses `writing-clearly-and-concisely`, Chinese
uses `readable-human-writing`, and other languages may use local rules only.
The JSON change log contains `result` (`edited` or `no-change`) and `changes`
(objects with `field`, `before`, `after`, and `reason`; empty for `no-change`).
The completion receipt records an agent's review, not an automated guarantee
of factual equivalence or professional tone.

For new runs, `request` should also contain `report_archetype` (`finance-report`
or `research-memo`) and `decision_use`. For `finance-report`, record its output
contract under `plan.output_contract`, including the coverage universe rule,
comparison periods, common metrics, sector KPIs, required bridge or ranking,
valuation requirement, and planned artifacts. These fields are additive and do
not change schema version `1.0.0`.

The default `finance-report` output formats are `interactive-html` and `json`,
represented by `report/index.html` and `report/report-data.json`. The JSON is
the presentation contract and must carry fact, calculation, and source IDs for
every material block. Markdown is reserved for an explicitly selected
`research-memo`; PDF, XLSX, and PPTX are optional finance-report exports.

Start from `skills/finrun/assets/research-record.template.json` or use `skills/finrun/scripts/new_run.py`.

## Report language

Resolve `request.language` before research: explicit output-language choice →
main language of the current request → English if undetermined. Preserve that
choice in artifact languages, presentation metadata and rendered text.
`request.language_resolution` records `source`, `request_language` (when
supplied by the router), and `fallback`. The source is
`explicit-output-language`, `request-language`, `request-script-heuristic`, or
`english-fallback`. These additive fields do not invalidate older runs.

With `new_run.py`, the router uses `--language` for an explicit output choice
and `--request-language` for its inference of the main instruction language.
The helper does not parse arbitrary natural-language output preferences. Its
unflagged fallback recognizes predominantly Chinese prose, then falls back to
English; for other languages or ambiguous mixed/quoted text, pass the router's
semantic choice. A template's null language is unresolved, not an English default.

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
- `provider-reported`: transcribed third-party market observation, not an
  independently verified exchange feed or a company-reported financial fact;
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

## Optional market-data receipts

Price-based runs may add `market_data` with `schema_version: 1.0.0` and a
`batches` array. Each receipt identifies an immutable run-relative snapshot,
its SHA-256, whether it is required, and mappings to sources, input facts,
evidence and calculations. The validator checks these mappings and recomputes
the supported metrics. See
`skills/finrunbook-market-data/references/data-contract.md` from the repository
root. These fields and the `provider-reported` status are additive; runs without
market-data receipts keep their previous behavior.
