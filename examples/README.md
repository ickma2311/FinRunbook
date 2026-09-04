# FinRunbook examples

Two completed English interactive financial reports generated with the FinRunbook workflow. Their financial scope is **2021–2025**, not the latest available quarter. The research cutoff is September 3, 2026.

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

## What is in each package?

- `prompt.txt`: the English instruction that was run.
- `report/`: portable HTML, CSS, JavaScript and presentation JSON. No third-party browser library or financial API call is needed to view it.
- `research-record.json`: structured facts, precise evidence locators, source URLs and hashes, calculation inputs, and pinned skill revisions.
- `validation.json`: FinRunbook schema, reference-integrity and provenance checks.
- `model-audit.json`: numeric recomputation, primary-table checks and the report author's semantic-review scope.
- `editorial-review.json`: English tone review and recorded changes.
- `browser-tests.json`: browser interaction, chart geometry, responsive-layout and local-resource checks.

The same author performed the analysis and editorial/semantic review. Automated validation is not an independent audit and does not guarantee that issuer disclosures are correct.

## Re-run the prompts

Ask the FinRunbook router to run the contents of either `prompt.txt`. Normal working data belongs in ignored `runs/<run-id>/` directories. These curated example packages are deliberately outside `runs/` so they can be version-controlled and published. Review new packages for data rights and sensitive information before adding them here.

## Sources and limitations

Apple uses its FY2023 and FY2025 Forms 10-K, whose comparative financial statements together cover all five fiscal years. Cloud uses Amazon and Alphabet's 2023 and 2025 Forms 10-K plus Microsoft's five annual reports for FY2021–FY2025. Overlapping financial years are reconciled.

Apple's FY2023 has 53 weeks. AWS and Google Cloud use calendar years; Microsoft's fiscal years end in June. Google Cloud includes Workspace, while Azure is not the Intelligent Cloud segment. Missing Azure revenue and operating margins are not estimated. Microsoft's FY2025 Azure revenue disclosure is a threshold, not an exact value. Parent-company cash capex is not cloud-only or AI-only investment.

Packages contain attributed factual extracts and analysis, not copies of complete issuer filings. Source documents and third-party materials remain subject to their respective terms. No issuer endorsement, blanket commercial-data license, or independent audit assurance is claimed.
