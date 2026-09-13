# Source access and topic selection

## Coverage is part of the result

Use the user's source choices when supplied. Otherwise use Hacker News, GDELT
and Google Trends Trending Now RSS for discovery, with SEC/issuer IR for event
preflight and evidence. Keep X disabled unless the user explicitly adds it.
Reddit and YouTube are optional, not mandatory fallback probes. Where access
allows, include broad finance and non-technology sectors rather than drawing
the entire candidate pool from HN. Disclose remaining concentration. Do not
hard-code a permanent influencer list or treat followers as expertise.

For each source record platform, community/query, access mode (`api`, `browser`,
`search` or `feed`), scan time, date window, status and limits. Capture individual
post/article/filing permalinks rather than citing a search results page as an
original source. A trend observation may instead link to the exact official
feed/query with its parameters and timestamp. Preserve observation time even
when a live URL later changes.

| Source | Preferred route when available | Important boundary |
| --- | --- | --- |
| Hacker News — default | Official read-only API; bounded top/new story samples and relevant items | Capture score, total comments, publication time, observed rank and sample size. Cumulative counts are not daily increments. Tech-community coverage is not the whole market. |
| GDELT — default | DOC API article discovery and coverage timelines; open relevant original articles | Measures coverage in GDELT's monitored corpus, not readers or social discussion. Deduplicate syndication; a domain count is not necessarily independent reporting. Preserve timeline denominator, time resolution and query. |
| Google Trends — default | Trending Now's official RSS export for the chosen region; permitted UI/CSV for missing details | Search interest is not investor sentiment or buying intent. Preserve geography, time window and bucketed volume. The RSS may omit UI fields: missing growth/rank stays unknown. Do not require the separate, access-gated Trends API. |
| SEC / issuer IR — evidence and event checks | SEC submissions API or filing RSS; issuer releases and feeds where offered | No popularity metric. Confirm the original filing/release time and identity. Select an event only when its financial consequence and research question justify it. Respect SEC fair-access rules and issuer-specific access terms. |
| YouTube — optional | Already authorized Data API; bounded finance/industry channel or keyword sample | Capture video IDs, dates and available views/likes/comments. Use API quota conservatively; no assumption that arbitrary captions are downloadable. No need to ingest whole videos to discover topics. |
| Reddit — optional | Authorized API/connector; permitted browser inspection can enrich selected original threads | Compare Top with New within the recorded community and time window. Verify approved use; commercial API use needs a separate agreement. Search excerpts are partial, not a current platform ranking. |
| X / Twitter — disabled by default | Only after explicit user inclusion, through an authorized API/connector or permitted browser route | Top and Latest answer different questions; neither is a platform-wide census. Do not probe, buy access or treat disabled coverage as a failed request. Enabling the source does not authorize paid calls or scraping. |

Check current access documentation rather than assuming a free API or an installed
provider connection. Reference documentation:

- [Official Hacker News API](https://github.com/HackerNews/API)
- [GDELT DOC API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
- [Google Trending Now exports](https://support.google.com/trends/answer/3076011?hl=en-GB)
- [Google Trends API access status](https://developers.google.com/search/apis/trends)
- [SEC developer resources and fair access](https://www.sec.gov/about/developer-resources)
- [YouTube API access and quotas](https://developers.google.com/youtube/v3/getting-started)
- [Reddit Data API terms](https://redditinc.com/policies/data-api-terms)
- [X recent post search](https://docs.x.com/x-api/posts/search-recent-posts)

Probe each configured source with a small request first; verify response format,
timestamps and relevant coverage before expanding the sample. Do not assume a
documented endpoint is working or that a key is installed. Fix a valid empty
result's query only within scope; do not label it an access failure. After an
access failure, try at most one permitted alternative route, then disclose the
gap and continue. Check current documentation only for sources actually used.

Public visibility is not a blanket redistribution license. Do not export comment
archives or unnecessary handles/profiles. Respect source terms and deletion or
access restrictions. Never provision paid access just to meet the topic count.

When using browser-assisted discovery, follow [the browser procedure](browser-discovery.md)
for access checks, bounded sampling, disagreement summaries and incremental-value
evaluation. A logged-in session is not itself authorization for automated collection.

## Separate attention from research merit

Keep three attention families separate: `community` (scores, replies, views),
`news` (coverage volume/breadth) and `search` (search interest). A `primary_event`
is a fourth, non-attention signal. Keep every metric's unit, source sample,
window and retrieval time; identify a rank's listing and sort mode. A claim of
"trending" in a search snippet is not a measurement.

Compare within sources before synthesizing an assessment across them. Prefer
changes against a stated baseline or same-source percentiles when available;
neither requires an arbitrary universal score. Derive engagement growth only
from comparable timestamped observations of the same item. A provider-reported
growth value must retain the provider's baseline definition and approximation.
On a first run without history, use observed levels/ranks and disclose that our
own growth is unavailable. Never fabricate a baseline to make a topic qualify.

Use high/medium/low attention tiers only with a written comparison to the
observed pool, identifying whether the tier concerns community, news or search
attention. Independent recent discussion/coverage breadth can be a labeled
proxy when counts are unavailable; lower confidence. Without credible attention
evidence leave heat `unverified`. An event-led selection can retain that status;
it must not be presented as a verified hot topic.

Cluster a filing, news rewrites, discussion links and search variants about the
same catalyst before ranking. Keep separate signal observations, but do not
count dependent copies as independent confirmation. Popularity may be driven
by outrage, promotion or memes; identify those
limitations without diagnosing intent. A high-engagement assertion can still be
false. Recast it into a neutral, falsifiable question.

The research gate requires all of the following:

1. A verifiable recent discussion, news/search signal or material primary event.
   For attention-led selection, substantiate attention; for event-led selection,
   substantiate event timing and financial importance without inventing heat.
2. A financial mechanism and a concrete metric/bridge capable of testing it.
3. At least one opened, relevant primary source and a feasible plan for the
   other material inputs; disclose unavailable consensus/private-company data.
4. A meaningful unanswered question, not just a request to repeat a headline.
5. A novelty check against prior batches and related existing reports.

Questions can survive a false popular premise: investigate why the premise is
wrong when that is financially useful. Never inherit an allegation as a fact.

Selection must balance attention, financial consequence, evidence readiness and
novelty. Write why a chosen question beats the next eligible candidate. Do not
automatically prefer a viral but shallow debate to a researchable material event.
When replacing an attention-led candidate with an event-led one, disclose the
tradeoff. A hot-discussions-only request excludes event-only selections.

Illustrative transformations, not current recommendations:

- "AI will kill SaaS" → Which disclosed retention, pricing and margin metrics
  indicate actual pressure, and which suppliers capture or eliminate spending?
- "A stock fell despite an earnings beat" → Which reported versus expected
  metrics diverged, and what price-reaction explanations remain unverified?
- "Cloud capex is excessive" → How do cash investment, depreciation, disclosed
  demand and utilization proxies differ across comparable companies and periods?

## Deduplication and freshness

Build an `event_key` from the question, entities and catalyst/period. The same
headline in a news feed and HN belongs to one topic. Two genuinely different financial
questions about one company can remain separate, but explain the distinction.

Inspect the last seven days of radar manifests and relevant research records.
For a previously researched topic, store prior run IDs and either a material new
filing/event/data point (`material_update`) or a `reuse` decision. Do not treat
new wording, more likes or another repost as new financial evidence.

Keep the scan cutoff fixed. Reports may use later evidence only when their
own as-of date is explicitly advanced and that change is disclosed; do not
retroactively count later signals in the original attention assessment.
