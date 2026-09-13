# Finrun 0.5 preview for Codex

This archive contains one skill and local Python helpers. Extract it so the
plugin root is `finrun/`, with `.codex-plugin/plugin.json` immediately inside.
Install through a supported Codex plugin flow when ready. Building this archive
does not install it, change a marketplace, update an existing plugin, or publish
a release. A new Codex task is needed to test a newly installed skill.

Requirements: Python 3.10+, a writable workspace outside this installation,
available source-reading tools and network access to the public GitHub catalog.
Yahoo collection optionally requires the pinned dependency in
`skills/finrun/requirements-market-data.txt`, installed into the workspace's
`run/.venv/`. Core helpers need no third-party Python package, Node, server,
Finrun account, API key or MCP connection.

Invoke `$finrun` with a question. Brief questions produce sourced answers;
substantial reports produce portable HTML/JSON, and datasheets can produce CSV.
Reports and method caches are written under the current workspace's `run/`.
The package fetches public catalog/method text from GitHub without uploading
prompts or research records. Financial-source access uses the host's available
tools and source/provider rules. Installation does not grant paid data access.

The catalog is resolved from the default branch of
`https://github.com/ickma2311/FinRunbook`. Version 0.5 requires the compatible
catalog marked `finrun-catalog: 1` and its first-party methods. Until that catalog
is published, an empty-cache production first run fails with an actionable
message. A published compatible test commit can be selected with the helper's
`--revision` argument. Offline work requires matching validated cached methods;
the plugin does not silently substitute instructions from another revision.

This preview's local build/acceptance receipt accompanies the archive. It lists
tested behaviors separately from live catalog publication, installed-Codex
acceptance and financial-source availability. Source URLs or mechanical passes
are not financial audit assurance. No automatic trading, scheduling, remote
storage, account linking or publication is included.
