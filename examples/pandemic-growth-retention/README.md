# Pandemic growth retention

[Open the interactive report](report/). Compare Zoom, Docusign, Shopify, Etsy and
Peloton over fiscal periods ending in 2019–2025. Research cutoff: September 3, 2026.

## What the example tests

- Seven annual observations for each company, with actual fiscal start/end dates.
- Two revenue-index baselines, annual growth, margins, cash flow and SBC intensity.
- A sortable annual comparison and operating-margin versus FCF-margin matrix.
- A reconciled FY2022–FY2025 margin bridge for each company.
- Sparse workforce checkpoints and explicitly identified scope/accounting changes.
- Click-through evidence, calculation inputs and a searchable source library.

The report is an operating-business comparison, not a valuation or investment
recommendation. Reported growth is not assumed to be organic or caused by the
pandemic. Revenue relative to the observed annual peak is not customer retention.

## Workflow and checks

The FinRunbook router selected `financial-analysis`, followed by English tone review
using the pinned writing skill and the FinRunbook validator. The financial-analysis
ratio helper was imported and tested. The package contains the original prompt,
evidence ledger, primary-source links, model checks, editorial receipt and browser
tests. The report author performed the semantic and editorial reviews; this is not
an independent audit.

## Important boundaries

Zoom and Docusign end their fiscal years in January, Peloton in June, and Shopify
and Etsy in December. In this report, FY2025 ends in 2025, not January 2026. These
periods are not synchronized and are not the latest available quarters.

Fourteen SEC annual filings and one issuer IR financial release supply the inputs.
Shopify FY2021–FY2022 uses the unaudited annual columns of its FY2022 release.
Later comparative values are preferred within the collected set; a complete
historical restatement exercise was not performed.

FCF is operating cash flow less cash capital expenditure, including separately
reported capitalized software at Etsy. It excludes acquisitions and is not cash
after all financing/investing obligations. SBC uses the cash-flow-reconciliation
expense add-back. Neither SBC nor employee totals measure net dilution or average
workforce productivity.

Peloton's FY2020–FY2021 income-statement presentation changed in its FY2022 report.
Its cash-flow-statement capex is $0.1 million above its MD&A reconciliation in each
of those years; the cash-flow statement is used consistently here. Full source
archives remain in the ignored working run and are not redistributed in this
package. Source hashes and locators remain in the ledger for traceability.

## Local viewing

From the repository root, serve `examples/` over HTTP:

```sh
python3 -m http.server 8771 --bind 127.0.0.1 --directory examples
```

Open `http://127.0.0.1:8771/pandemic-growth-retention/report/`.
The browser loads local static files only; no paid API or proprietary runtime is
needed to view the saved report. Direct `file://` viewing is not supported.
