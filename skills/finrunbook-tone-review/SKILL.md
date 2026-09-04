---
name: finrunbook-tone-review
description: Perform FinRunbook's final editorial pass on report copy, captions, UI labels, and exports. Make the language professional, restrained, precise, and decision-useful without changing facts, financial definitions, uncertainty, citations, or the report structure. Run after drafting and translation and before final rendering and finrunbook-validator.
---

# FinRunbook Tone Review

Edit presentation language, not the underlying research. Retain the analyst's
view and the financial-report structure. Professional tone does not mean more
jargon, more certainty, or an academic literature-review style.

## Select the editor by report language

Use the report language already resolved by the router and recorded in
`request.language`: explicit output-language request first, otherwise the main
language of the current request, with English only as the undetermined-language
fallback. Do not reset it to English during editing. If the rendered prose or
artifact metadata conflicts with that choice, return the mismatch to generation
before reviewing it. For multilingual reports, review each version in its own
language.

- **English:** read the complete
  `vendor/agent-toolkit/skills/writing-clearly-and-concisely/SKILL.md` and its
  `elements-of-style/03-elementary-principles-of-composition.md`. Use its
  clarity, concision, and anti-puffery guidance subject to the financial rules
  below. Preserve necessary negation, attribution, uncertainty, and the tense
  distinctions between historical results, current conditions, and guidance.
  Do not remove a valid financial term such as “leverage” as an AI-style word.
- **Chinese, whether explicitly requested or inferred:** read the complete
  `vendor/readable-human-writing/SKILL.md` and its required references. Use
  `polish-only` mode; do not run the Chinese editor on English copy.
- **Other resolved languages:** apply the financial rules below in that
  language. Record the local-only review; do not claim an upstream editor ran.

Apply these constraints to either editor:

- Audience: the run's audience; default finance professional.
- Voice: neutral, concise, explicit about evidence and judgment.
- Structure: preserve FinRunbook's financial panels, rankings, and navigation.
- Input: extracted human-facing text and its evidence context, not executable
  code or the entire JSON object as a prose document.
- Output: edits to those same text fields, not a Markdown report or a new
  research outline.

Record each editor actually used and its submodule commit in
`plan.selected_skills`. This pass does not translate reports or change their
language. If a required dependency is missing, surface the issue; do not claim
it ran. FinRunbook's financial constraints take precedence over stylistic
advice to make claims stronger, remove hedging, or standardize every tense.

## Financial editorial rules

1. Replace promotional or emotionally loaded wording with the measured
   development: avoid unsupported “revolutionary,” “inevitable,” “crushed,”
   “explosive,” “碾压,” “颠覆,” “史诗级,” or “必然.” These are contextual review
   signals, not a blind replacement list. Preserve exact attributed quotations.
2. Match claim strength to evidence. Preserve “may,” “estimated,” “management
   expects,” sample boundaries, and confidence qualifications. Do not turn an
   association into causality, slower growth into contraction, penetration into
   revenue share, or a scenario into guidance. Remove only redundant hedging.
3. Preserve the point of view: a labeled analyst judgment with a mechanism and
   falsification condition is useful. Do not neutralize every conclusion into
   “both sides have merits,” and do not add unsupported conviction.
4. Prefer a named business driver and comparable metric over vague adjectives.
   Do not invent a number to make a sentence more specific. Keep terminology
   stable: revenue, bookings, ARR, ACV, RPO, NRR, FCF, and market share are not
   interchangeable stylistic variants.
5. Remove empty transitions, repetitive conclusions, rhetorical questions,
   reader manipulation, cheerleading, urgency, and generic AI-generated prose.
   Do not add stories, slang, jokes, or detector-evasion tricks.
6. Preserve numbers, signs, units, periods, fiscal labels, currencies, source
   and calculation IDs, URLs, direct quotes, rankings, scenario assumptions,
   JSON keys, code, and financial definitions. If an edit would alter any of
   these, return it to analysis/validation rather than fixing it as tone.

For example, “Management expects FY2027 revenue of $10–11bn [SRC-003]”
must not become “FY2027 revenue will reach $11bn.” Concision must preserve
the attribution, forecast status, range, period, units, and citation.

## Execute near the end

1. Read the final draft, its supporting facts, and any completed translations.
2. Mark artifacts draft and validation stale before editing a previously
   validated report. Limit the pass to copyediting; propose material structural changes
   separately instead of applying them here.
3. Edit only human-facing text fields in `report/report-data.json`, or the
   source copy for an explicitly requested PDF/PPTX/research memo. Update the
   presentation model first; never leave a polished HTML page with stale JSON.
4. Compare before/after values against the protected items in rule 6. Log
   nontrivial wording changes with field/section, before, after, and reason in
   `editorial-review.json`. If nothing needs changing, record `no-change`; a
   real review can be complete without a rewrite.
5. Regenerate affected pages, translations only if separately authorized, and
   existing exports from the reviewed copy. Check headings, chart annotations,
   source drawers, and visible qualifications for consistency.
6. Update `research-record.json.editorial_review`: `required`, `status`,
   `completed_at`, `reviewer`, `languages`, `upstream_skills`,
   `reviewed_artifacts`, `change_log_path`,
   `protected_items_preserved`, and `unresolved_issues`. Use `status: completed`
   only after comparing the edits; otherwise use `blocked`.
   Each `upstream_skills` entry records `name`, repository-relative `path`,
   `commit`, and `languages` actually reviewed. The change log contains a
   `result` of `edited` or `no-change` and a `changes` array (empty for
   `no-change`). Include every reviewed artifact path, including regenerated
   outputs, in `reviewed_artifacts`.
7. Run `finrunbook-validator` on the edited and regenerated artifacts. Do not
   polish again after validation without repeating the editorial and validation
   checks. State whether the review used the same agent or an independent one;
   do not imply independent review when none occurred.

Tone is the final language pass, not the final unchecked mutation. The finish
sequence is: draft/translation → tone review → regenerate → validation → deliver.
