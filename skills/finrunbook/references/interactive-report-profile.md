# Interactive finance-report profile

Use this profile for the presentation layer of a `finance-report`. The output
must be portable across Codex, Claude, GitHub Pages, Cloudflare Pages, Vercel,
Netlify, S3-compatible hosting, and an eventual FinRunbook application.

## Output package

The default final package is:

```text
report/
├── index.html
└── report-data.json
```

`index.html` is a responsive static application. It must not require a chat-only
runtime, proprietary widget API, server-side rendering, database, or secrets.
It may use local CSS and JavaScript assets when the implementation needs them.
`report-data.json` is the complete presentation model, derived from
`research-record.json`; the page must not contain material facts that are absent
from that JSON or the evidence ledger.

The primary report must remain useful without PDF or XLSX. Add optional exports
only when useful:

- `report/report.pdf` for a fixed, printable snapshot;
- `report/model.xlsx` when users need formulas, assumptions, or reusable company
  comparisons; and
- `report/report.pptx` for an explicitly requested presentation.

Do not make Markdown a final finance-report artifact.

## Presentation-data contract

`report-data.json` should contain:

- `schema_version` and `meta`: run ID, title, decision use, as-of date, language,
  coverage universe, status, and available periods;
- `executive_view`: analyst conclusion, decisive metrics, implications, and the
  conditions that would change the view;
- `sections`: ordered blocks such as `metric-grid`, `table`, `chart`, `bridge`,
  `ranking`, `scenario`, `timeline`, or concise `analysis`;
- `methodology`: metric definitions, normalization, material proxy limitations,
  and conflicts;
- `sources`: source IDs, titles, publishers, dates, URLs or permitted local
  references; and
- `validation`: status, timestamp, and disclosed warnings.

Every section block carries the `fact_ids`, `calculation_ids`, and `source_ids`
needed to reproduce it. Store display values separately from raw values and
record the formatting rule. Do not paste full source documents into the
presentation data.

## Interaction contract

Use interaction to help analysis, not to decorate it:

- period and company/subsector filters update every dependent metric and chart;
- consistent actual, estimate, guidance, and scenario styling is visible
  without hovering;
- chart tooltips show value, units, period, basis, and source ID;
- clicking a metric opens its evidence and calculation trail;
- the source drawer is searchable and links to the exact source;
- comparison tables support sorting while preserving units and definitions;
- navigation keeps analyst view, dashboard, changes, rankings, value flow,
  outlook, and methodology easy to reach; and
- the page has a readable print layout and remains usable on mobile.

Avoid marketing-page hero sections, decorative animation, generic KPI cards,
hidden caveats, or interactions that obscure the denominator. Use accessible
type sizes, sufficient contrast, keyboard operation, and reduced-motion
preferences.

## Portability rule

Conversation-specific rendering skills may inform visual design but cannot be
the primary implementation if they require `show_widget`, `sendPrompt`, host CSS
variables, or another unavailable runtime. Build ordinary web files instead.
All material data must ship with the report; a static viewer must not fetch live
third-party financial data at display time.
