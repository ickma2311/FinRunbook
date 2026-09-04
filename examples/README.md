# FinRunbook examples

Six completed interactive financial reports generated with FinRunbook: **four English and two Chinese**. The research cutoff is September 3, 2026. Reporting periods vary by example; these are saved snapshots, not live dashboards.

## View online

[Open the example gallery](https://ickma2311.github.io/FinRunbook/).

GitHub Pages publishes only this directory. Updates to `examples/` on `main`
run the packaging checks and deploy automatically through
`.github/workflows/pages.yml`. Working runs and raw source documents are not
included in the deployment.

## View locally

From the FinRunbook repository root:

```sh
python3 -m http.server 8771 --bind 127.0.0.1 --directory examples
```

Open <http://127.0.0.1:8771/>. Serve the directory over HTTP: the report renderer fetches its adjacent JSON file, so opening an HTML file directly with `file://` is not supported.

| Example | Report | Main analytical feature |
| --- | --- | --- |
| Apple | [Open report](apple-business-quality/report/) | Product and geography mix, cash allocation and an EPS bridge separating income and share-count effects |
| Cloud computing | [Open report](cloud-computing/report/) | AWS and Google Cloud comparison, separate Azure disclosures and explicitly scoped parent capex |
| Pandemic growth retention — English | [Open report](pandemic-growth-retention/report/) | Five businesses across FY2019–FY2025; indexed revenue, profitability/cash matrix, margin bridges and acquisition limits |
| AI infrastructure — English | [Open report](ai-infrastructure-capex-supply-chain/report/) | Four hyperscalers, eight suppliers, capital-spending filters and named relationship evidence |
| 六家科技公司的资本配置 — 中文 | [打开报告](big-tech-investment-allocation/report/) | 五年趋势、实际财年日期、支出口径和现金桥接 |
| AI 产业链 — 中文 | [打开报告](ai-industry-value-chain/report/) | 模型、硬件、云和应用；财务筛选、增长桥接、推理成本情景 |

## Why these examples?

The three additions demonstrate cross-company capital allocation, an industry value
chain, and buyer–supplier relationships. Selection considered existing validation and
editorial records, first-party sources, interactive controls, comparison limits and
suitability for a static public package. Selection is not a new independent audit or
a guarantee of financial accuracy.

The two Chinese reports retain their original Chinese text and controls. The English
supply-chain example now opens actual evidence and calculation details from its
existing ledger instead of displaying IDs alone; its financial data and conclusions
are unchanged.

## What is in each package?

- `prompt.txt`: the original instruction, in its original language.
- `report/`: portable HTML, CSS, JavaScript and presentation JSON. No third-party browser library or financial API call is needed to view it.
- `research-record.json`: structured facts, precise evidence locators, source URLs and hashes, calculation inputs, and pinned skill revisions.
- `validation.json`: FinRunbook schema, reference-integrity and provenance checks.
- `model-audit.json` or `model-tests.json`, where available: original numeric-recomputation receipts. The English supply-chain report has no separate model-audit receipt; none is implied.
- `semantic-validation.json`, where available: original same-agent review and disclosed limitations.
- `editorial-review.json`: language-specific tone review and recorded changes.
- `browser-tests.json`: browser interaction, chart geometry, responsive-layout and local-resource checks.

The same author performed the analysis and editorial/semantic review. Automated validation is not an independent audit and does not guarantee that issuer disclosures are correct.

## Re-run the prompts

Ask the FinRunbook router to run the contents of a package's `prompt.txt`. Normal working data belongs in ignored `runs/<run-id>/` directories. These curated example packages are deliberately outside `runs/` so they can be version-controlled and published. Review new packages for data rights and sensitive information before adding them here.

The original validation and model receipts retain their original scope and timestamps.
New `publication-review.json` receipts describe packaging and browser checks only.
Original raw-file names and hashes may remain in evidence locators for traceability;
those source archives are not included. Use the publisher URLs to consult documents.

## Sources and limitations

The pandemic-growth report uses 14 SEC annual filings and Shopify's FY2022 IR
release, whose annual financial tables are unaudited. It covers annual fiscal
periods ending in 2019–2025, without calendarization. Etsy FCF subtracts separately
reported capitalized software; acquisitions, impairments and sparse workforce
checkpoints remain visible. See its [package notes](pandemic-growth-retention/README.md).

Apple uses its FY2023 and FY2025 Forms 10-K, whose comparative financial statements together cover all five fiscal years. Cloud uses Amazon and Alphabet's 2023 and 2025 Forms 10-K plus Microsoft's five annual reports for FY2021–FY2025. Overlapping financial years are reconciled.

Apple's FY2023 has 53 weeks. AWS and Google Cloud use calendar years; Microsoft's fiscal years end in June. Google Cloud includes Workspace, while Azure is not the Intelligent Cloud segment. Missing Azure revenue and operating margins are not estimated. Microsoft's FY2025 Azure revenue disclosure is a threshold, not an exact value. Parent-company cash capex is not cloud-only or AI-only investment.

The Chinese capital-allocation report uses issuer-specific five-year windows (ending
in FY2026 for NVIDIA and Microsoft and FY2025 for the other companies). The Chinese
AI report separates annual and quarterly observations, and its cost simulator is
illustrative rather than a company forecast. The English supply-chain report spans
2023 through the research cutoff; supplier revenue is not additive across layers.

Packages contain attributed factual extracts and analysis, not copies of complete issuer filings. Source documents and third-party materials remain subject to their respective terms. No issuer endorsement, blanket commercial-data license, or independent audit assurance is claimed.
