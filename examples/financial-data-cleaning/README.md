# Prepare comparable financial data

[Open the three worked cases](index.html) · [Reusable prompt](prompt.txt)

This example shows three common preparation tasks with real, source-linked values from the saved Cloud and Lululemon reports: units/signs, quarter versus year-to-date, and cloud disclosure comparability. It is a transformation demonstration, not an additional investment report.

## Downloads

- [Input observations](inputs.csv): source values and units, dates, scopes, fact IDs and source locators.
- [Cleaned data](cleaned-data.csv): explicit transformations, output definitions and input references.
- [Metric dictionary](metric-dictionary.csv): field meanings and missing-value conventions.
- [Exceptions](exceptions.csv): handled representation issues and unresolved economic differences.
- [All case data](data.json) and [transformation review](validation.json).

## Where the inputs came from

The [Cloud report](../cloud-computing/report/) uses a September 3, 2026 cutoff; the [Lululemon report](../lululemon-earnings-update/report/) uses September 4. Inputs are selected from their existing extracted ledgers. No original value was corrupted to create a problem. Azure's missing operating margin is a coverage annotation; its qualitative scope citation is not a numeric disclosure.

The source files already underwent the original reports' author-led review. This example does not re-extract PDFs or demonstrate arbitrary-file ingestion. Source fact IDs are namespaced by source package because the two reports reuse ID numbering. Calendar metadata and semantic mappings are explicitly authored for the selected cases; the arithmetic is deterministic. No financial figures are refreshed to the current date.

## What cleaning does and cannot do

Lululemon's thousands become millions; signed cash capex gets a separately labeled positive-outflow representation. Compatible H1 and Q1 cumulative measures produce a Q2 result reconciled against the directly reported quarter. This does not remove tariff refunds or create adjusted earnings.

Azure's revenue threshold remains a strict lower bound. Its missing operating margin stays blank. Microsoft's June fiscal year is not silently treated as a December calendar year. Google Cloud retains Workspace in its scope. Parent capex is not allocated to cloud or AI. These boundaries remain unresolved even after the table is clean.

CSV output contains numeric data and formulas as explanatory text, not executable spreadsheet formulas. Use the input IDs to review a transformation. A handled formatting exception is not a guarantee of economic comparability or source accuracy. No customer adoption, automated monitoring, benchmark accuracy or measured time savings is claimed.

[Back to examples](../index.html#data-cleaning)
