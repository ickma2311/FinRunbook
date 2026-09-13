# Browser-assisted discussion discovery

Use this optional procedure to understand original discussions, competing claims
and linked evidence. It supplements Radar's discovery sources; it does not measure
the whole platform or make social claims financial facts.

## Access and scope first

- Preserve the batch's source choices. X remains disabled until the user includes
  it or approves a scoped search request. An earlier approval in the same task
  counts; do not ask again solely because execution resumed. Editing this skill
  does not grant account access or enable X in all future batches.
- Prefer existing authorized APIs/connectors when sufficient. Use the host's
  browser tools for permitted UI inspection, not a mandatory new automation
  framework, crawler or nested model process.
- Check current platform terms and the permitted collection route before use.
  Public visibility or an existing login is not permission to scrape. If access
  requires login, let the user handle it; do not extract cookies or credentials.
  Stop an unresolved permission/access issue for that source, not the whole batch.
- Do not bypass CAPTCHAs, rate limits, robots restrictions or denials with proxies,
  hidden endpoints or alternate identities. After failure, try at most one
  permitted alternative; otherwise record the gap and continue other sources.

## Choose a browser and obtain search permission

1. Honor an explicit browser or tab selection first, including `@Browser`. Do not
   silently switch away from the selected browser. Otherwise, inspect the host's
   connected-browser/tab inventory, preferring the user's default browser when
   the host identifies it. Never assume Chrome is the default. If the default is
   unknown, use a connected browser with a relevant open tab; ask which profile
   to use only when multiple plausible accounts make the choice ambiguous.
2. Look only for Reddit/X tabs relevant to this task. Inventory presence and a
   domain URL do not prove login. Before inspecting account-backed content or
   searching X, check the user's current authorization. If absent, ask once:
   "May I use your signed-in X session for read-only searches and public post/
   reply inspection for this Radar run? No posting, messages or account changes."
   Obtain equivalent consent for Reddit if outside the authorized source scope.
   Respect an explicit exclusion or refusal; continue other sources while an
   answer is pending, and record the source as not attempted.
3. With authorization, check the relevant tab's visible UI for signed-in state.
   Reuse that browser/profile and the existing search tab where suitable; do not
   overwrite a user's draft or unrelated work. If no relevant tab is open, one
   direct site navigation in the connected default browser can check the session.
   Do not inspect history, cookies, credential stores, private messages or other
   profiles to discover an account. Readable search results, not merely login,
   are the subsequent access test.
4. If no connected regular browser is available, or it has no usable signed-in
   session, use the in-app `@Browser` (or the host's equivalent). Reuse a matching
   in-app tab if present. Regular-browser login does not imply in-app login; if
   login is required, show that tab and ask the user to sign in there, then
   recheck search access. Never request a password in chat. If the user explicitly
   selected the original browser, ask before switching. A CAPTCHA, site denial
   or rate limit is not a reason to switch browsers to evade it.
5. Respect host website-permission prompts separately from conversational consent.
   Grant no permissions on the user's behalf and do not request blanket access
   to all sites. Record browser type, observed login state, selection/fallback
   reason and the scope of consent in coverage limitations; omit account identity
   and session secrets. Add an approved source to this batch's requested sources
   and remove it from this batch's disabled list with an authorization note.

This preference selects a browser only when browser inspection is useful; an
existing sufficient authorized API/connector remains usable. Neither login nor
user consent overrides platform terms or proves permission for bulk collection.

Useful official references, checked only for sources used:

- [Reddit search sorts and filters](https://support.reddithelp.com/hc/en-us/articles/19695706914196-What-filters-and-sorts-are-available)
- [Reddit user agreement](https://redditinc.com/policies/user-agreement)
- [X advanced search](https://help.x.com/en/using-x/x-advanced-search)
- [X Top search results](https://help.x.com/en/using-x/top-search-results-faqs)
- [X terms](https://x.com/en/tos)

## Bounded scan

Record limits before collection. For an initial discovery pilot, a useful budget
is 20 unique original posts total across sources, five queries total, two result
pages/screens per query, up to three relevant replies per opened thread, and ten
minutes of discovery. Stop at the first applicable limit. These are adjustable
pilot bounds, not topic quotas or limits on subsequent financial research.
No endless scrolling. A requested pilot can use `scan-only`; do not silently
convert an ordinary research request into a pilot.

1. Use configured feeds, search and primary events to identify seed questions.
   If the user requests only Reddit/X, stay within that source scope.
2. Open selected original discussions through permitted routes. On Reddit, sample
   Top plus New with the community and period recorded. On X, sample Top plus
   Latest with observed query/date filters. Use controls actually available;
   do not assume a filter was applied merely because it appeared in a URL.
3. Prefer explicit queries/listings over personalized home feeds. Record sort,
   filters, region/language and whether the session/results are personalized or
   unknown. Top is algorithmic selection, not objective popularity; Latest can
   surface low-engagement new ideas. Neither proves global heat.
4. Inspect a small reply sample for opposing explanations and original document
   links. Summarize the central claim, counterclaim and testable financial
   question with attribution. Do not infer consensus from sampled replies.
5. Record compact structured observations immediately in `radar.json`, following
   [the batch contract](batch-contract.md). Prefer accessible text/DOM; screenshots
   are optional evidence where permitted, excluding unrelated account information.
   Do not dump full pages, profiles or comment archives into agent context.
6. Deduplicate post IDs/permalinks and event clusters. Use Python for deterministic
   normalization and comparisons when needed; use the agent for question framing.
   Preserve distinct observations rather than adding duplicated engagement.

Capture original permalink, publication/activity time, observation time and
visible metrics. Missing values are `null`; rounded displays retain their
precision. Search snippets are `search_excerpt`, not a verified original thread.
No growth claim from one snapshot: computed growth requires comparable times
for the same post and metric. A later recheck requires a separate invocation;
this procedure does not create a schedule.

## Selection and evaluation

Apply the existing financial-mechanism, primary-preflight and novelty gates.
Open relevant SEC/IR or other primary documents before selection. A viral claim
can become a question to disprove; it cannot become report evidence by repetition.
Produce 3–5 questions only if enough qualify, with direct discussion links,
opposing views, attention limitations and the remaining evidence plan.

For a pilot, preserve the pre-browser shortlist and compare it with the enriched
pool at the same cutoff. Record incremental qualified topics, newly discovered
counterarguments/evidence links, verified original posts, access failures,
elapsed time and actual browser action count. Record token usage only when the
host exposes it; otherwise `null`. Without a baseline, report the observed yield,
not an invented improvement percentage. Use the result to decide whether the
extra coverage merits routine use; do not assume browsers are more efficient.

If browser access is unavailable, retain permitted API/search/feed observations
with their actual quality and coverage labels. Do not label a search-only result
as equivalent to a directly inspected thread. Proceed with the existing child
FinRunbook workflow in research mode; a pilot alone does not generate reports.
