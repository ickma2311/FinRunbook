# FinRunbook agent entry point

This repository contains the public financial-research code. Keep five top-level
product folders: `skills/`, `plugin/`, `run/`, `tests/`, and `examples/`.
Root documentation and `.github/` are repository infrastructure.

For financial research, read `skills/finrunbook/SKILL.md`; for topic discovery,
read `skills/finrunbook-radar/SKILL.md`. Select relevant instructions from
`skills/index.md`. Third-party methods are immutable upstream links, not installed
dependencies. Do not initialize submodules or assume a linked tool is available.
Use local Python and the shared helpers in `skills/finrun/scripts/`.

Store generated outputs under `run/<run-id>/` in the working directory. Keep each
research run's `research-record.json` current. Caches, environments and build
outputs also belong under ignored `run/`. Do not write into an installed skill.
Use US markets unless the user specifies otherwise; resolve output language from
the user's instructions independently of geography.

Before delivering financial research, follow `skills/finrunbook-validator/SKILL.md`.
Review source meaning separately from mechanical checks, and browser behavior
separately from financial validation. For code changes, run relevant regression
tests; do not fabricate research validation records for implementation work.

The code-layout phase retains existing research/review instructions. Consolidating
them into the small user-facing skill and building the plugin are phase two.
Do not add MCP dependencies, nested model launchers or automatic scheduling.
Internal investing, portfolio and hourly workflows are outside this product.
Preserve original checkouts, historical runs, pinned evidence and explicit stops.
Do not rewrite frozen examples to update old provenance paths. Never blanket-stage
generated runs or copy private reports into examples.
