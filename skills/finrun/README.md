# Shared Python helpers

This is the single maintained location for public research helper code and
templates. Run commands from the workspace with Python 3.10 or newer.

| Helper | Purpose | Instructions |
| --- | --- | --- |
| `scripts/new_run.py` | Initialize a draft research record and artifacts | [Research](../finrunbook/SKILL.md) |
| `scripts/new_batch.py` | Initialize or resume a Radar batch | [Radar](../finrunbook-radar/SKILL.md) |
| `scripts/market_data.py` | Collect and validate market observations | [Market data](../finrunbook-market-data/SKILL.md) |
| `scripts/validate_run.py` | Validate evidence, calculations and artifacts | [Validation](../finrunbook-validator/SKILL.md) |

The initializers default to the caller's `run/` directory and retain `--runs-dir`
as an override. `new_batch.py` loads its template relative to its own location;
the validator loads the sibling market-data helper. Neither depends on a vendor
checkout, internal investing code or an MCP service.

Only Yahoo collection needs an optional dependency, declared in
`requirements-market-data.txt`; use a workspace-local `run/.venv/` environment.
The existing data contracts and validation behavior are retained for this phase.
The single-skill entry point and packaging are implemented in phase two.
