# Local generated files

Write research outputs to `run/<run-id>/`, public-source caches to `run/.cache/`,
optional Python environments to `run/.venv/`, and build outputs to `run/.build/`.
Only this README is tracked. Do not force-add private research, provider responses,
environment files or release archives.

The initializers default to `run/` in the caller's working directory; `--runs-dir`
still accepts an explicit location. Historical outputs in an original checkout
remain there until a separately verified migration. Do not silently rewrite their
records or hashes to substitute new paths.
