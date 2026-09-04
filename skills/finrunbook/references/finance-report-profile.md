# Finance-report profile

Use this profile when `request.report_archetype` is `finance-report`. It defines
the analytical contract; adapt the number of companies and sections to the
question rather than filling a template mechanically.

## 1. Define the decision

State in one line what decision the report informs: investment selection,
portfolio monitoring, operating strategy, lending, transaction work, or another
specified use. Separate descriptive research from a recommendation. Do not add
a buy/sell call unless the user asks for investment advice and the available
evidence supports it.

Set a coverage universe before collecting company data. For sectors, identify
the subsectors and public/private boundary, then select companies by disclosed
revenue, market relevance, or another recorded rule. Do not choose examples only
because their disclosures support the initial thesis.

## 2. Build comparable panels

Create a metric dictionary before extraction. For every comparable metric,
record its definition, units, currency, fiscal/calendar basis, actual/estimate
status, period, and source. Normalize only when the transformation is defensible
and recorded.

Use two panels when necessary:

1. **Common financial panel:** revenue, organic growth where disclosed, gross
   margin, operating margin, free-cash-flow margin, and valuation metrics
   relevant to the business model.
2. **Sector KPI panel:** the operating indicators that explain economics. For
   SaaS these may include ARR, NRR/DBNRR, RPO/cRPO, paid seats, customer count,
   large-customer mix, CAC/payback, Rule of 40, and AI-product monetization.

Do not place ARR, ACV, revenue, seats, penetration, and wallet share in one
ranking column. Show unavailable values as `N/A`; do not replace them with an
incomparable metric simply to fill the table.

Use at least two comparable historical periods plus the latest interim period
when available. Use five fiscal years plus latest interim for public-company
initiation or valuation work unless the request supplies a narrower window.

## 3. Quantify the thesis

Translate the question into one or more auditable bridges rather than only a
narrative:

- revenue growth into volume/customers, price or mix, acquisition, and FX when
  disclosures permit;
- margin change into gross-margin, operating-expense, and mix drivers;
- sector value migration into donor, receiver, retained-by-incumbent, internal
  build, and eliminated-spend buckets;
- market-share change into a consistent denominator or an explicitly labeled
  proxy such as customer penetration, wallet share, or revenue growth delta.

Every bridge must reconcile or expose an `unexplained` residual. Never present
directional indicators as an additive 100% share waterfall. Assign confidence
to proxies and state what observation would falsify the attribution.

## 4. Present the report in finance order

The interactive report should normally follow this information hierarchy:

1. **Analyst view:** one clear answer, two or three decisive numbers, and what
   is priced, changing, or operationally important.
2. **Dashboard:** scope, as-of date, coverage, common financial panel, sector
   KPIs, and valuation when relevant.
3. **What changed:** a period-on-period driver bridge, not a chronology of
   documents read.
4. **Company or subsector ranking:** winners, neutral/mixed, and pressured
   exposures, with the financial mechanism for each classification.
5. **Competitive and value flow:** who gains, who loses, why, and which metric
   measures the claimed transfer.
6. **Forward view:** scenarios or estimates, catalysts, risks, and the KPI that
   would confirm or invalidate the view.
7. **Methodology and sources:** definitions, proxy limitations, conflicts, and
   the source ledger.

Put the conclusion before market background. Use tables and charts for repeated
comparisons, and connect filters across dependent views. Keep each caveat next
to the affected number in compact form and consolidate extended source
limitations in the methodology view. Do not make “what the data cannot prove”
the organizing principle of the main narrative.

## 5. Minimum completion gate

Before validation, confirm that:

- the opening view answers the user's question rather than summarizing sources;
- the selected universe and inclusion rule are recorded;
- comparable financial and sector KPIs use aligned periods and definitions;
- at least one auditable bridge or ranking carries the core thesis;
- actuals, guidance, estimates, and scenarios are visually distinct;
- each winner/loser classification identifies its financial mechanism;
- valuation is included when the decision depends on price, and omitted with a
  reason when it does not;
- limitations are disclosed without overwhelming the decision-useful body; and
- tables and charts trace back to fact and calculation IDs.

Also apply `interactive-report-profile.md`; Markdown is not a final artifact for
this archetype.

The validator checks provenance and semantics; it does not decide whether the
artifact reads like a finance report. Apply this profile before invoking it.
