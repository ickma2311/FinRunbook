# Runs

Create one directory per research run. Git ignores generated runs; only this
README is tracked. Local files remain available to the agent and report viewer.
Never force-add secrets, API keys, paywalled source bodies, or data whose terms
prohibit redistribution. Review selected examples before publishing them in a
separate directory.

Expected layout:

```text
runs/20260903-153012-datadog-vs-cloudflare/
  research-record.json
  report/
    index.html
    report-data.json
  editorial-review.json
  validation.json
  artifacts/
  sources/        # optional; only when local storage is permitted
```
