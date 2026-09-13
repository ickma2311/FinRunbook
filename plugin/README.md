# Finrun plugin packaging

Version `0.5.0-preview.1` contains one public skill and local Python helpers.
Maintained runtime sources live in `skills/finrun/`; the package copies only
`runtime-files.json` entries. It excludes the method catalog/library, historical
skills, MCP/app connections, generated reports, tests and private workflows.

Build from the repository with Python 3.10 or newer:

```bash
python3 -B plugin/build.py
```

Each build creates an isolated `run/.build/<version>-<unique>/finrun/` root,
a deterministic ZIP and `BUILD.json` with per-file and archive SHA-256 hashes.
Repeated builds of unchanged sources have identical archive bytes. The receipt
records the exact source snapshot even when implementation is uncommitted.
It does not install, publish, update a marketplace or change an older release.

## First use and release boundaries

Read [package requirements](INSTALL.md). The new catalog and `skills/methods/`
must be published before an empty-cache default-branch request can succeed.
A compatible published test commit can be selected explicitly. Unpublished
fixture transport tests establish helper behavior, not live GitHub acceptance.
Do not mark this candidate generally usable until published-catalog retrieval
and a new installed Codex task have passed.

Run the offline regression suite before delivery:

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Use the plugin-creator manifest validator and skill-creator entry validator when
available. Separately exercise the extracted bundle in a workspace outside its
root; inspect actual browser rendering, evidence drawers, numeric sorting,
filters, missing values, responsive output and computed contrast. Synthetic
fixtures do not certify financial source accuracy or research completeness.

Keep acceptance receipts beside the build under ignored `run/.build/`.
Installation and publication require their own authorized step; preserve prior
releases and do not write into an installed skill.
