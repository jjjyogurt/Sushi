# 0529 Discovery Build Plan

Date: 2026-05-29

## Build Goal

Improve YouTube video discovery recall for hardware consumer brand monitoring without building a parallel discovery system.

Manual discovery may use SerpAPI as a market-localized candidate source when configured, but each SerpAPI video ID must be validated through YouTube Data API `videos.list` before publish-window filtering or persistence. Pulse V1 remains YouTube Data API only for scheduled latest monitoring; SerpAPI is not in the scheduled path until manual discovery quality is proven.

The Phase 1 build focuses on discovery correctness:

- Use user-defined project keywords as the source of truth.
- Treat time trigger and publish window as primary discovery inputs.
- Search YouTube newest-first.
- Keep relevant candidates when the keyword signal appears in title or description.
- Avoid hard-blocking brand-level videos that do not mention an exact key product.
- Improve auditability so missed or filtered videos can be debugged.
- Add tests that lock the discovery behavior before proactive monitoring is built.

Phase 1 does not generate daily or weekly proactive monitoring reports. That is Phase 2 and must reuse the same discovery pipeline.

## Current State vs Required Rework

| Area | Already in place | Required Phase 1 rework |
| --- | --- | --- |
| Project keyword source | Project profiles already store `brand_keywords` and `key_products`; discovery loads both. | Preserve exact user-defined keywords as primary search seeds. Do not replace them with AI-generated variants. |
| Time window | Manual discovery already accepts `published_after` and `published_before`; UI already has publish window controls. | Add `time_trigger` as optional request/audit metadata so every discovery run explains why that window was used. |
| Query planning | `DiscoveryKeywordService` already builds YouTube query specs from project keywords, languages, and markets. | Use exact project keywords only; remove localized/Gemini query variants so quota is spent on user-declared terms. |
| YouTube search | `YouTubeDiscoveryService` already calls YouTube Data API with `type=video`, language, region, and publish window. | Add `order=date` to prioritize newly published videos. Keep `publishedAfter` and `publishedBefore`. |
| Raw candidate collection | Search results already become `DiscoveredVideo` objects with video ID, URL, title, channel, language, publish time, and description. | No schema change required for Phase 1. Discovery query/source can remain audit-level metadata for now. |
| Deduplication | Results are deduped by YouTube video ID in memory and persisted under scoped uniqueness by `(monitor_profile_id, youtube_video_id)`. | Keep this behavior. Same video may exist in different projects; duplicate video must not be saved twice in one project. |
| Relevance filter | Discovery currently filters by title keyword match. | Change to title OR description keyword match. |
| Key products | Key products are currently used as required keywords during discovery filtering. | Key products should boost relevance but must not hard-block brand-level videos. |
| Relevance scoring | `RelevanceService` already scores title and description keyword matches. | Keep the service; update inputs/expectations so product hits improve score while brand-only videos can still pass. |
| Persistence | Passing candidates are saved with `queue_state = discovered`. | Keep this behavior. Discovery must not approve, analyze, risk-score, or alert by itself. |
| Audit | Discovery records a simple discovered count. | Record trigger, window, query count, raw count, filtered count, saved count, duplicate/upsert count, and error count where available. |
| Worker infrastructure | Cloud Tasks and the shared analysis worker already process analysis batches and project insight jobs. | Do not change for Phase 1. Reuse this pattern later for proactive monitoring jobs. |

## Implementation Chunks

### 1. Query Plan Rework

Change discovery query planning so exact user keywords are always included as search seeds.

Required behavior:

- Normalize and dedupe `brand_keywords + key_products`.
- Generate query specs from individual keyword seeds across configured languages and markets.
- Preserve exact user keyword text without adding AI/Gemini or localized intent variants.
- If more than three languages are configured, use English first when configured, plus the next two configured languages.
- Keep `_MAX_SPECS` behavior so a large project does not explode quota usage.
- Keep deterministic behavior regardless of Gemini availability.

Recommended fallback seed pattern:

```text
brand keyword alone
key product alone
```

Do not use a single fallback query that joins every keyword together.

### 2. YouTube Newest-First Search

Update the YouTube Data API request to include:

```text
order=date
```

Keep the existing request behavior:

```text
type=video
publishedAfter=<window start>
publishedBefore=<window end>
relevanceLanguage=<project language>
regionCode=<project market>
maxResults=min(requested max_results, 50)
```

Do not divide `max_results` across query specs. Each YouTube Data API request should fetch the full allowed page for that query, then discovery dedupes, filters, and trims the final saved candidates.

If the Data API fails, existing timeout/error handling should continue to skip that query and continue with remaining queries.

### 3. Light Relevance Filter

Change discovery filtering from title-only to title-or-description.

Keep a video when:

- Any configured brand keyword, key product, or safe variant matches the title.
- Any configured brand keyword, key product, or safe variant matches the description.

Filter out a video when:

- It has no keyword signal in title or description.
- It is outside the requested publish window.
- It is missing required video identity fields.
- It is already saved in the same project.

Important behavior change:

- `key_products` must not be passed as a hard required keyword list during discovery filtering.
- Product matches should still improve relevance score and reason.

### 4. Time Trigger Metadata

Add an optional `time_trigger` field to the discovery request model.

Accepted values should be enum-like strings:

```text
manual_last_24h
manual_last_7d
custom_range
scheduled_daily
scheduled_weekly
```

Phase 1 can treat this as metadata rather than a persisted schema field.

Required behavior:

- Preserve existing `published_after` and `published_before` behavior.
- Forward `time_trigger` from API router to discovery service.
- Include `time_trigger` in audit details.
- If the field is omitted, use a safe default such as `manual_unspecified`.

### 5. Discovery Audit Upgrade

Expand the audit details for each discovery run.

Audit details should include:

```text
time_trigger
published_after
published_before
query_count
raw_count
window_filtered_count
relevance_filtered_count
saved_count
duplicate_or_updated_count
error_count
```

This can be stored as a compact string in the existing audit system for Phase 1. Do not add a new discovery run table yet.

### 6. Documentation And Alpha Coverage

Because this changes user-facing discovery behavior, update `ALPHA_RELEASE_TEST_CASES.md` during implementation.

The alpha test case should cover:

- Create or use a project with user-defined brand keywords and key products.
- Run discovery with a publish window.
- Confirm discovered candidates can match title or description.
- Confirm a brand-level video is not dropped only because the exact product name is missing.
- Confirm discovery does not trigger alerting by itself.

## Target Data Flow

```text
Project profile
  brand_keywords + key_products + markets + languages
        |
Discovery request
  max_results + time_trigger + published_after + published_before
        |
Build query plan
  exact user seeds + bounded expansions
        |
YouTube search
  order=date + publish window + language/region
        |
Raw candidates
        |
Deduplicate by youtube_video_id
        |
Light filter
  title OR description keyword signal
        |
Relevance scoring
  brand/product title and description hits
        |
Persist candidate
  queue_state = discovered
        |
Later analysis
  sentiment, risk, action, alert decision
```

## Public Interface And Behavior

Discovery request should support:

```json
{
  "monitor_profile_id": 123,
  "max_results": 20,
  "time_trigger": "manual_last_7d",
  "published_after": "2026-05-22T00:00:00Z",
  "published_before": "2026-05-29T00:00:00Z"
}
```

Existing response behavior remains unchanged:

- Return discovered video candidates.
- Do not return sentiment or risk as part of discovery.
- Do not generate an alert from discovery alone.

No new database table is required for Phase 1.

## Test Plan

### Query Planning Tests

- Exact user-defined keywords are included in query specs.
- Multiple keywords are not collapsed into one strict-only query.
- Language and market expansion still works.
- Gemini is not called for discovery query expansion.
- Exact user-keyword specs are unchanged when a Gemini client is configured.

### YouTube Request Tests

- Data API params include `order=date`.
- Data API params include `publishedAfter` and `publishedBefore`.
- Timeout on one query continues to remaining queries.
- API error response returns no candidates for that query and does not crash the run.

### Filtering Tests

- Title keyword match is kept.
- Description-only keyword match is kept.
- Video with no title or description signal is filtered out.
- Brand-only match is kept when `key_products` are configured.
- Key product match improves relevance score/reason but is not required.

### API And Service Tests

- Router forwards `published_after`, `published_before`, and `time_trigger`.
- Discovery audit details include trigger, window, and counts.
- Duplicate video ID is not saved twice in the same project.
- Same video ID can still be saved independently in another project.

### Manual QA

- Run manual discovery for last 24 hours and last 7 days.
- Verify YouTube newest-first results are saved when relevant.
- Verify the UI still receives the same discovered candidate response shape.
- Verify no alert is created from discovery alone.

## Phase 2 Proactive Monitoring Note

Future proactive monitoring should run through the same discovery pipeline:

```text
Scheduled trigger
-> same discovery request shape
-> same query planning
-> same YouTube search
-> same filtering/scoring/persistence
-> analysis
-> daily or weekly monitoring report
```

Phase 2 should add a monitoring job/report layer instead of creating another discovery path.

Expected report sections:

- Discovery summary
- Sentiment summary
- Risk summary
- Top new risks
- Notable praise
- Competitor signals
- Recommended action

## Explicit Non-Scope For Phase 1

- No proactive daily or weekly monitoring report generation.
- No new discovery run database table.
- No YouTube channel RSS/WebSub monitoring.
- No automatic bad-review alerting from discovery alone.
- No redesign of the queue UI response shape.
- No replacement of the existing analysis worker.

## Acceptance Criteria

- Discovery searches using exact user-defined project keywords.
- Discovery searches newest-first using `order=date`.
- Discovery respects `published_after` and `published_before`.
- Discovery records `time_trigger` and useful run counts in audit details.
- Discovery keeps candidates when keyword signal appears in title or description.
- Discovery keeps brand-level candidates even when key products are configured.
- Discovery saves candidates as `queue_state = discovered`.
- Discovery does not approve, analyze, risk-score, or alert by itself.
- Unit and API tests cover the new behavior.
- Alpha release test cases document the user-facing discovery workflow.
