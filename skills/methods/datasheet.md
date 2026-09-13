# Historical financial datasheet

Define entities, periods and metrics. Use entity/metric/period/basis rows or a
documented wide equivalent. Keep issuer, metric definition, start/end, fiscal
label, duration/instant basis, currency, units, actual/adjusted status and source
locator with each observation.

Preserve raw data separately from normalized figures. Record scaling and sign
transformations, including cash outflows. Distinguish zero, missing, not applicable
and suppressed. Do not interpolate an undisclosed period without an authorized,
clearly labeled estimate.

Derive quarters from YTD only with matching scope and restatement basis. Check
boundaries and period counts. Balance-sheet values are instants, so do not
subtract them to invent quarterly balances. Prefer later restatements where
appropriate, retaining superseded observations and exceptions.

Reconcile totals, segments, balance-sheet equation and cash changes when inputs
exist. Disclose rounding residuals and exclusions. Definitions and comparability
flags belong in the dataset, not just a prose footnote.

CSV should include period, units, basis, missing reasons and source IDs. Escape
formula-like text for spreadsheet safety. Include definitions and exceptions
in structured JSON or the requested workbook. XLSX uses an available local
library with formulas and source links preserved; disclose missing dependencies.
Cleaning a table does not independently verify the issuer's accounting.
