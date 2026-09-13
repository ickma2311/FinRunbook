---
name: finrunbook-validator
description: Validate a FinRunbook research run before delivery. Use at the end of every FinRunbook workflow, or when asked to audit an existing run, to check the finance-report output contract, source and evidence integrity, period and unit consistency, calculations, citation coverage, and artifact provenance; then update the structured record and Markdown report with validation status and a formatted source list. Fail closed rather than inventing citations.
---

# FinRunbook Validator

Audit the research record first and presentation artifacts second. A fluent
report is not evidence.

## Run deterministic checks

1. Locate the run directory and read `research-record.json` completely.
2. Read `references/validation-rules.md`.
3. Run `python3 skills/finrun/scripts/validate_run.py <run-directory>` from the repository root.
4. Read `validation.json` and inspect every error and warning.

The script validates structure and provenance links, refreshes generated
validation and source blocks in `report.md`, updates `research-record.json`,
and returns a non-zero exit code for `FAIL`.

For runs declared as `finance-report`, it also fails when the plan has not set
the coverage rule, comparison periods, common metrics, core bridge or ranking,
valuation decision, planned artifacts, and sector KPIs where applicable. This
checks that the analytical model was planned; semantic review must still judge
whether the populated report is decision-useful.

For the default interactive output, it also checks that the HTML consumes
`report-data.json`, that the initialization scaffold has been replaced, and
that presentation blocks map back to recorded facts, calculations, and sources.

When a run contains `market_data` receipts, it also verifies snapshot hashes,
recomputes returns/drawdowns/volume and benchmark comparisons, and checks the
input and calculation mappings against the run ledger. A required failed batch
or a mismatched value blocks delivery. Warnings include incomplete bars and
coverage gaps. Review the security identity, currency, adjustment basis and
actual observed dates semantically; a valid receipt does not independently
verify the provider or show the identity or motivation of traders.

For runs that require editorial review, verify that the tone pass and its change
log are complete, protected content is declared preserved, and no unresolved
editorial issue remains. This receipt is not proof of semantic equivalence:
compare material edits against the evidence during semantic validation.

## Check rendered HTML before delivery

For interactive reports, follow the
[color and readability checks](references/interactive-report-profile.md#color-and-readability-checks).
Use the actual browser render and inspect the recorded measurements, including
non-hover controls and applicable focus/selected states. Fix failed contrast
checks and rerun affected states after the final style changes.

`validate_run.py` checks data and provenance; it does not launch a browser or
measure CSS contrast. Its `PASS` must not be presented as a visual-accessibility
pass. Keep browser results separate from the financial validation status. If
browser measurement is unavailable, explicitly mark the presentation unverified
and disclose that limitation rather than inventing a pass. Do not present an
interactive report with known contrast failures as final.

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
