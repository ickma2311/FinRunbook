# Validation rules

## Blocking errors

- missing or invalid required top-level fields;
- duplicate or malformed stable IDs;
- a source without a title, publisher, retrieval time, or retrievable location;
- evidence pointing to a nonexistent source or lacking a precise locator;
- a material fact with no source/evidence support;
- `verified`, `company-reported`, or `calculated` facts without the support
  appropriate to that status;
- a calculation with missing input facts, expression, result, or units;
- an artifact referencing an unknown fact;
- a Markdown citation referring to an unknown source;
- unresolved placeholders or `[SOURCE NEEDED]` in a final artifact;
- guidance, estimate, and actual periods conflated in a material comparison.

## Warnings

- source is secondary where primary evidence should exist;
- missing publication or as-of date;
- a material source is not cited anywhere in the Markdown report;
- an inference lacks a clear explanation of its reasoning;
- a numeric fact lacks period, units, or currency where applicable;
- the report does not cite all source IDs attached to its material facts;
- a source's data-use terms are unknown;
- a selected skill's repository revision is not recorded.

Warnings do not block delivery, but the user must be told about them.

## Semantic review checklist

For material numbers, confirm:

1. entity and security;
2. fiscal/calendar basis and exact start/end date;
3. instant versus duration context;
4. quarterly, year-to-date, annual, or trailing period;
5. reported, non-GAAP, constant-currency, or modeled basis;
6. units, scale, currency, and sign;
7. continuing operations versus total company;
8. amended versus original filing;
9. guidance/estimate versus actual result; and
10. formula inputs and rounding.

For narrative conclusions, confirm that the cited text supports the strength
of the wording. “May,” “expects,” and “will” are not interchangeable.

## Source rendering

The validator manages two idempotent blocks in `report.md`:

```text
<!-- finrunbook:validation:start -->
...
<!-- finrunbook:validation:end -->

<!-- finrunbook:sources:start -->
...
<!-- finrunbook:sources:end -->
```

It formats one footnote definition per source. The analytical author must place
the corresponding `[^SRC-001]` marker next to the claim; the validator must not
guess that association.

