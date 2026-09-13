# Finrun skill and shared helpers

[SKILL.md](SKILL.md) is the single research and Radar entry point. It selects
pinned online methods and keeps one accountable agent responsible for the answer.
Run Python 3.10+ commands from the caller workspace; outputs default to `run/`.

| Helper | Purpose |
| --- | --- |
| `scripts/catalog.py` | Resolve and cache a pinned method catalog and selected text |
| `scripts/new_run.py --compact` | Initialize the compact evidence and review contract |
| `scripts/new_batch.py` | Initialize or resume a bounded Radar batch |
| `scripts/market_data.py` | Collect market observations and recompute supported metrics |
| `scripts/render_report.py` | Render portable HTML/JSON or CSV with evidence links |
| `scripts/validate_run.py` | Validate evidence, calculations, receipts and artifacts |

Read [helper commands](references/helpers.md) and the
[evidence/presentation contract](references/record.md). The standard-library core
has no MCP or vendor runtime dependency. Only Yahoo collection needs the optional
pinned dependency in `requirements-market-data.txt`; install it when needed into
the caller workspace's `run/.venv/`.

Legacy initializers and records keep their original validation behavior when
`--compact` is absent. Historical skill documents are retained in the repository,
but only this skill and the declared runtime files enter the plugin archive.
