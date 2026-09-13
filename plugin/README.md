# Plugin phase

This folder will contain the Finrun plugin manifest, packaging code and release
metadata. Plugin implementation is deferred until after the code refactor.

The maintained skill/helpers belong under `skills/`; future packaging copies only
declared runtime files into an ignored build directory under `run/.build/`.
Do not maintain an editable second copy here or import the old MCP release.

Phase two implements the small Codex-only entry point, GitHub catalog retrieval,
revision pinning/cache fallback, distilled methods, simplified evidence/review
contract, portable rendering and packaged-skill acceptance tests. Installation
and publication remain separate actions.
