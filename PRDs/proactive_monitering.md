Feature Goal

The system should proactively monitor YouTube for new videos relevant to a specific project, product, and market, then automatically run the existing video analysis pipeline and surface a concise risk report.

The user mainly cares about:

Is monitoring working for this product in this market?
Did the system find anything new?
Did any new video create product, PR, or marketing risk?
Core User Requirements

Requirement	User-Facing Meaning
Per-project monitoring	User can enable proactive monitoring inside a project.
Product-level monitoring	User can see whether each configured product is being monitored.
Market-level monitoring	User can see whether monitoring is working for each target market.
Daily / weekly cadence	User can choose how often monitoring runs.
Layered discovery	System searches multiple ways, not only one YouTube keyword query.
Wrong-video filtering	DJI-only or unrelated videos should not be added to a HOVERAir project.
Automatic analysis	New relevant videos should automatically enter the video analysis pipeline.
Risk digest	User sees summaries like “2 new videos, 1 critical risk detected.”
Quiet failure handling	User is not spammed by transient failures unless action is required.
Monitoring confidence	User can understand if coverage is high, low, or needs attention.
Key Data Concepts

Project
  -> Products
      -> Markets
          -> Monitoring Target
              -> Monitoring Runs
                  -> Discovered Videos
                      -> Analysis Results
Recommended new durable concepts:

Concept	Purpose
monitoring_target	Represents one product × market monitoring setup.
monitor_run	Represents one proactive monitoring execution.
monitor_run_item	Records each candidate video found, accepted, skipped, duplicated, or analyzed.
monitoring_digest	User-facing summary of meaningful outcomes from a run.
Example monitoring target:

Project: HOVERAir
Product: HOVERAir X1 ProMax
Market: Japan
Languages: Japanese, English
Cadence: Daily
Status: Working
Pipeline Logic

1. Scheduler starts
2. Find due monitoring targets
3. Create monitor run
4. Build layered discovery plan
5. Search YouTube
6. Normalize and filter results
7. Reject unrelated videos
8. Persist relevant new videos
9. Create analysis batch
10. Run video analysis pipeline
11. Finalize monitor run
12. Generate user digest
13. Update product × market monitoring status
Detailed Pipeline

Step	Logic	Output
1. Scheduler starts	Cloud Scheduler or equivalent triggers proactive monitoring.	Monitoring job begins.
2. Find due targets	Query enabled targets where next_run_at <= now.	List of product × market targets.
3. Create run	Create monitor_run with status running.	Durable audit record.
4. Build discovery plan	Generate query matrix from project keywords, product aliases, market, language, competitors, and pain keywords.	Search query specs.
5. Search YouTube	Run YouTube Data API searches with publishedAfter, publishedBefore, regionCode, and relevanceLanguage. Also scan watched channels if configured.	Raw video candidates.
6. Normalize candidate text	Normalize title, description, channel name, spacing, punctuation, casing, and aliases.	Searchable text.
7. Apply relevance gate	Require project brand/product/alias match. Competitor-only videos are rejected.	Accepted/rejected candidate decision.
8. Dedupe	Skip videos already saved for this project/product/market.	New relevant videos only.
9. Persist videos	Save accepted videos into video_candidates.	New candidate rows.
10. Create analysis batch	Automatically enqueue only new relevant videos.	analysis_batch created.
11. Worker analyzes videos	Existing transcript/comment/Gemini analysis pipeline runs.	analysis_results.
12. Finalize run	Count found/new/analyzed/failed/high/critical videos.	Completed monitor_run.
13. Generate digest	Produce user-facing summary only if useful.	“2 new videos, 1 critical risk detected.”
14. Update health	Update monitoring target status and confidence.	Working, Low confidence, or Needs attention.
Layered Discovery Logic

Layer 1: Product Alias Search
- hoverair x1
- hover air x1
- hover x1
- hoverair promax
- hover air aqua

Layer 2: Competitor Comparison Search
- hoverair vs dji
- hoverair x1 vs dji neo
- hoverair aqua vs potensic

Layer 3: Pain Keyword Search
- hoverair overheating
- hoverair battery drain
- hoverair connection issue
- hoverair crash
- hoverair not worth it

Layer 4: Market + Language Search
- Japanese / Japan
- German / Germany
- English / US

Layer 5: Watched Channel Scan
- For known creators, scan uploads directly instead of relying on search ranking.
Wrong-Video Filtering Rule

A video should be added only if it matches the project.

Add if:
- title or description contains a strong project alias
- title or description contains product keyword
- competitor comparison includes project keyword
- watched channel upload contains project alias

Reject if:
- only competitor keyword matched
- only generic drone/category keyword matched
- only market/language matched
- title is about DJI/Potensic/etc. with no project mention
Example:

Video Title	Decision	Reason
HOVERAir X1 ProMax Review	Add	Direct product match.
Hover Air X1 vs DJI Neo	Add	Project + competitor comparison.
DJI Neo Full Review	Reject	Competitor-only, no project match.
Best Pocket Drone 2026	Reject by default	Too generic unless description/transcript mentions project.
Hover X1 Flight Test	Add	Strong alias match.
X1 Camera Review	Reject or borderline	X1 alone is too weak.
Alias Matching Requirement

The system should generate and use aliases from project keywords and key products.

Example product:

HOVERAir X1 ProMax
Generated aliases:

hoverair x1 promax
hover air x1 promax
hover x1 promax
hoverair promax
hover air promax
x1 promax hoverair
Alias strength:

Alias Type	Example	Strength
Exact brand/product	hoverair x1 promax	Strong
Spacing variant	hover air x1	Strong
Common shorthand	hover x1	Strong enough
Product-only	x1 promax	Medium
Single generic token	hover, x1	Weak
Persistence rule:

Persist if:
1 strong alias
OR 2 medium aliases from same product group
OR competitor comparison + 1 project alias
User-Facing Monitoring Status

Status	Meaning
Working	Recent run completed with enough coverage.
Low confidence	Monitoring ran, but coverage is thin or partial.
Needs attention	User/admin must fix setup, quota, credentials, or keywords.
Paused	Monitoring is intentionally disabled.
Not configured	Product × market target does not exist yet.
When To Notify User

Notify only for meaningful outcomes or action-required failures.

Situation	Notify User?
New videos found	Yes
High or critical risk detected	Yes, prominently
No new videos, run succeeded	No, quiet status only
One query timed out but run mostly succeeded	No
YouTube quota exhausted	Yes
Missing API key or credentials	Yes
No usable project keywords	Yes
Repeated run failures	Yes
One transcript unavailable	Usually no
Digest Format

Monitoring Digest

Project: HOVERAir
Product: HOVERAir X1 ProMax
Market: Japan
Run: Daily monitoring

2 new videos found
2 videos analyzed
1 critical risk detected
0 videos failed analysis

Top risk:
Creator demonstrates repeatable connection drop during outdoor flight.
Functional Requirements

User can enable or disable proactive monitoring per project.
User can configure daily or weekly cadence.
System creates monitoring targets per product × market.
System uses project keywords and key products to generate aliases.
System runs layered YouTube discovery for each due monitoring target.
System applies strict relevance filtering before saving videos.
System rejects competitor-only videos unless the project is also mentioned.
System dedupes videos within the same project.
System automatically analyzes new accepted videos.
System records each monitoring run durably.
System records skipped/rejected candidate reasons internally.
System finalizes each run with counts for new videos, analyzed videos, failed videos, high risk, and critical risk.
System shows user-facing status by project, product, and market.
System only notifies users when there is a meaningful result or action required.
System keeps operational failures visible internally even when not shown to the user.