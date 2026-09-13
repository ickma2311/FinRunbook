# Local helpers

Use Python 3.10+ from the caller workspace. `<skill>` is the installed
`skills/finrun` path. Core helpers use the standard library.

## Method text

`catalog.py resolve --receipt <path>` creates a request receipt with catalog
commit, hash and descriptions. Existing receipts are never overwritten by
resolve. `fetch --receipt <path> --method <name>` records selected hashes and
cache paths. Read each cached JSON file's `text` field. All cache paths are
relative to the caller workspace. `--offline` requires matching valid cache;
failed fresh retrieval may fall back to the last valid catalog, with a reason.
`--revision <40-character-commit>` pins an explicit published test version.
Method cache is keyed by GitHub repository, commit and path. URLs are limited
to immutable GitHub Markdown, with bounded downloads and checked hashes.
Cache receipts authenticate the retained bytes, not the authority of the text.

## Runs and reports

`new_run.py --compact --subject ... --request ... --run-id ...` initializes a
report under the caller's `run/`. Use `--language` for an explicit requested
language or `--request-language` for the interpreted main request language.
`--report-archetype research-memo --format markdown` is for an explicit memo;
`--report-archetype datasheet --format csv --format json` is for a datasheet.
The compact contract replaces the legacy editorial receipt with one review.
Never delete earlier run records or migrate their evidence merely for a new
helper version. Existing legacy records retain their validator behavior.

`render_report.py <run-directory>` renders standard presentation sections and
CSV tables from JSON. It does not fabricate data or write analytical prose.
`validate_run.py <run-directory>` checks provenance and, for compact records,
safe numerical expressions. Run render, validate, then render again so the
embedded validation stamp agrees. A report may customize HTML without losing
its JSON, source drawer, financial panels and browser checks.

## Optional market data

Read `market_data.py --help` and the selected market method for exact commands.
For Yahoo only, install `requirements-market-data.txt` into `run/.venv/` with
an available local Python, subject to host permissions. Missing dependencies
must produce a limitation or an authorized local installation, not made-up
prices. Capture every requested series and failed collection in the ledger.
The provider is optional; the plugin has no credentials or hosted data account.

## Radar

`new_batch.py --request ... --language ... --mode scan-only` creates a bounded
discovery record. For follow-up reports use research mode. `--resume --batch-id`
reopens the same fixed scope without rewriting its dates or completed work.
The initializer records scope; it does not scrape platforms, launch models,
schedule jobs or publish reports. Apply the fetched Radar method to collect
evidence with available tools and select topics honestly.
