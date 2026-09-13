# Finrun 0.5 privacy notice

Last updated September 13, 2026. Maintained by Chao Ma.

This notice covers the Finrun 0.5 local-execution plugin, including
0.5.0-preview.1 and 0.5.0-preview.2. It supplements the older website notice for this release.
Finrun provides instructions and local Python helpers; this release does not
operate a hosted research or MCP service.

## Prompts, source material and local files

Your agent may send your prompt, selected files and source material to its model
provider or tools you authorize. Finrun's publisher does not operate a research
upload endpoint in this release or automatically receive your local research
records. Your agent provider, browser and source providers have their own data
practices and retention policies. Review those before processing confidential
information.

Reports, evidence records, method receipts and caches are written under `run/`
in the workspace used by your agent. You control these local files and can
delete them or stop using the plugin. This does not delete information held by
your agent or a third-party provider; manage that through the relevant provider.

## Public method catalog

The bundled catalog helper requests the public FinRunbook method catalog from
GitHub, resolves an immutable commit and downloads selected Markdown methods.
These requests disclose ordinary network metadata to GitHub, including your IP
address, client request headers and the requested catalog or method paths.
The helper does not upload your prompt, research record or private workspace
files. It records the commit, content hashes and retrieval details in a local
cache. GitHub's handling of requests is subject to its
[privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Financial sources and optional dependencies

Research requests go to source providers chosen through the agent's available
tools. The optional Yahoo adapter requests the chosen symbols, dates and market
observations from Yahoo through its client library. Provider access, data-use
terms and privacy policies apply separately. Installing optional packages also
connects to the selected package registry. Do not include secrets or personal
information in queries unless necessary and authorized.

The bundled local helpers do not include publisher analytics, advertising
trackers, an account system or automatic report publication. This does not mean
the host agent, GitHub, package registries or data providers process no technical
information. A hash or source URL does not establish that research is accurate.

## Support and privacy requests

Use the [support instructions](support-0.5.md). Information you choose to send
may be used to respond, reproduce a problem or address a privacy request.
GitHub Issues are public and subject to GitHub's policies. Email is handled
through the maintainer's Gmail account and your email provider. Send only a
sanitized example; do not include credentials, identity documents or private
financial records in a public issue.

For privacy questions, contact [ickma2311@gmail.com](mailto:ickma2311@gmail.com).
A hosted service or materially different data handling will require an updated
notice before launch.
