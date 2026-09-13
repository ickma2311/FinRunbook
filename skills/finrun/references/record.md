# Evidence and presentation contract

Use the initializer's `research-record.json` schema 1.0.0 with
`workflow: finrun-0.5`. Legacy records remain valid with their original gates.
Keep the scaffold's request, plan output contract, arrays and artifact paths.
`plan.selected_skills` may remain empty: the small method receipt replaces it.
Copy the catalog receipt to `methods.json`; it contains provenance, not research.

- Sources: `id: SRC-001`, title, publisher, URL or run-relative local path,
  retrieval timestamp, publication/as-of date, primary flag, available terms.
  Local snapshots require `sha256`. Do not retain source bodies when forbidden.
- Evidence: `id: EVD-001`, `source_id`, exact table/page/section locator, and
  extracted observation in `content`.
- Facts: `id: FACT-001`, statement, status, material flag, source_ids,
  evidence_ids; numerical facts add value, units, currency and period. Status is
  company-reported, provider-reported, verified, calculated, inferred,
  conflicting or insufficient-evidence. Inferences explain their reasoning.
- Calculations: `id: CALC-001`, description, expression, `inputs` mapping
  variable names to fact IDs, `input_fact_ids`, result, units and rounding.
  Example: expression `(current / prior - 1) * 100`, inputs
  `{"current":"FACT-002","prior":"FACT-001"}`, result in percent. Only
  finite numerical facts and +, -, *, /, ** expressions are supported. No eval,
  calls, attributes, file access or downloaded code. Break complex models into
  supported arithmetic with explicit inputs; do not invent a passing check.
  The market-data helper's specialized calculations retain their own schema;
  the validator recomputes these from hashed observations before accepting them.
- Review: `{"status":"completed","reviewer":"same-agent","notes":["Scope and checks actually performed; material gaps"]}`.
  Set this only after source-meaning, financial and language review. Record who
  reviewed; do not call a same-agent review independent.

## Standard presentation data

`report/report-data.json` retains schema_version, meta (title, language,
coverage_universe, decision_use, as_of_date), executive_view (headline, summary),
sections, methodology, sources and validation. Reference blocks use fact_ids,
calculation_ids and source_ids. The renderer copies the canonical ledgers from
the record; it rejects unknown references and unsafe URLs.

Sections carry an id, title, type, optional text, and evidence references.
Supported types are `analysis`, `table`, `chart`, and `ranking`:

```json
{
  "id": "history", "title": "Comparable revenue", "type": "table",
  "columns": [{"key":"period","label":"Fiscal period"},
              {"key":"revenue","label":"Revenue · USD m"}],
  "rows": [{"period":"FY2025", "revenue":{
    "value":120, "fact_ids":["FACT-001"], "basis":"actual",
    "period":"FY2025", "units":"USD million"}}],
  "fact_ids":["FACT-001"], "source_ids":["SRC-001"]
}
```

Cells are text, null (display N/A), or objects with value and references. Add a
calculation_ids array for derived cells. Keep units in column labels and cells;
use `basis` for actual, guidance, estimate or scenario. The renderer verifies
values against the ledger and allows `scale` for explicit display conversion
(e.g. 0.001 for USD millions to billions). Set `decimals` for display precision.
Charts use `label_key` and `value_key` naming columns of the same rows. Tables
sort numerically with nulls last; a per-section filter updates its rows/chart.
Keep unlike scopes in separate sections; do not use a global filter that leaves
dependent metrics stale. A narrative bridge can be a table with component and
amount, plus its reconciliation formula.

For a CSV datasheet, the first table is exported to `report/datasheet.csv`;
formula-like text is escaped to prevent spreadsheet execution, nulls stay empty.
Include period, units, basis and source IDs as columns for portable provenance.
Use an explicit requested XLSX only with a suitable available workbook library.

## Readability

Use financial panels, not a ledger-shaped narrative. Preserve detailed history,
scope and material KPIs. A renderer passing structure checks does not establish
that the answer is sufficiently comprehensive. For HTML, click metrics and
source links, test filters and sorting, then inspect mobile/print output.
Measure computed text/background contrast for default, hover, focus and selected
states: at least 4.5:1 for normal text and 3:1 for large text. Include effective
backgrounds through transparency. Keep browser results separate from financial
validation and disclose anything unverified.
