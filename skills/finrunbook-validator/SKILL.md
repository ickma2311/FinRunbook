---
name: finrunbook-validator
description: Validate a FinRunbook research run before delivery. Use at the end of every FinRunbook workflow, or when asked to audit an existing run, to check source and evidence integrity, period and unit consistency, calculations, citation coverage, and artifact provenance; then update the structured record and Markdown report with validation status and a formatted source list. Fail closed rather than inventing citations.
---

# FinRunbook Validator

Audit the research record first and presentation artifacts second. A fluent
report is not evidence.

## Run deterministic checks

1. Locate the run directory and read `research-record.json` completely.
2. Read `references/validation-rules.md`.
3. Run `scripts/validate_run.py <run-directory>`.
4. Read `validation.json` and inspect every error and warning.

The script validates structure and provenance links, refreshes generated
validation and source blocks in `report.md`, updates `research-record.json`,
and returns a non-zero exit code for `FAIL`.

## Perform semantic validation

Deterministic checks cannot establish that a sentence accurately represents a
source. For every material fact:

- reopen the exact source or permitted local copy;
- follow its evidence locator;
- verify entity, fiscal period, filing type, units, currency, sign, scale,
  reported-versus-adjusted basis, and whether the value is guidance or actual;
- independently recompute material calculations from recorded inputs;
- compare conflicts without silently choosing one;
- ensure analytical inferences are labeled and cite the underlying facts.

Prefer primary evidence for company-reported facts. A secondary provider can
corroborate or accelerate discovery but does not repair a mismatch with the
issuer's filing.

## Update the run

Correct the record when support exists. Add or repair source metadata,
locators, evidence links, fact statuses, periods, calculations, and artifact
citations. Rerun the deterministic validator after each correction batch.

When support cannot be obtained:

- set the fact to `insufficient-evidence` or `conflicting`;
- mark the affected artifact `blocked` if it changes the conclusion;
- place `[SOURCE NEEDED]` next to the unsupported claim when it remains in a
  draft; and
- keep a blocking issue in `validation.json`.

Never create a URL, quote, locator, or source-to-claim mapping from memory.

## Completion gate

- `PASS`: no errors or warnings; artifacts may be `validated`.
- `PASS_WITH_WARNINGS`: no errors; warnings are disclosed in the delivery.
- `FAIL`: at least one blocking error; do not present the artifact as final.

Finish only after `validation.json`, `research-record.json`, and the source and
validation blocks in `report.md` agree.
