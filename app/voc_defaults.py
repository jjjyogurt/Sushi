"""Default VOC skill prompt text — single source for API defaults and seeding."""

DEFAULT_CLEANER_SKILL_CONTENT = """VOC Data Cleaner Skills (Strict v3 - Report-Safe)
Goal
Convert each raw VOC row into clean, meaningful customer feedback text that is safe for VOC reporting.
Never output metadata noise as meaningful feedback.

Output (per row)
cleaned_text
language (ISO code or unknown)
source (support_ticket/app_store/reddit/youtube/unknown)
status (always cleaned)
error_reason (always empty string "")

Core rule
If a row is nonsensical, metadata-only, header-like, spam, or not customer feedback:
- keep status as cleaned
- set cleaned_text to ""
- set error_reason to ""

Meaningful text requirement
Only keep text that reads like a real customer statement with a clear opinion, issue, request, or experience.

Must remove if present
- IDs, ticket/order numbers, URLs, usernames, customer names, emails, phone numbers
- labels like zendesk id, customer name, channel, order id, e-mail, product name
- internal taxonomy columns such as 一级分类, 二级分类, 三级分类, recommend
- CSV/header rows, schema labels, and duplicated export headers
- timestamp/token noise like repeated 00:00 or delimiter-heavy fragments
- mixed metadata + fragment strings such as "ID 录入日期 ... [redacted]:00:00"

Forbidden
No summarization
No categorization (Analyzer handles it)
No invented wording to repair unclear text

Success criteria
Row coverage: 100%
Each non-empty cleaned_text should read like a quote safe to include in reports.
If uncertain, output cleaned_text="" instead of noisy text.
"""

DEFAULT_ANALYZER_SKILL_CONTENT = """---
name: voc-analyzer
description: Executive-grade VOC intelligence for Product Marketing, Product, and Leadership.
---

# VOC Analyzer Skill (Insight-Dense v6)

## Mission
Turn raw VOC into a decision-ready intelligence report.
Optimize for: clarity, depth, actionability, and trust.
Do not produce generic summaries. Extract maximum signal from the dataset.

## Output Scaling Rule
Scale report depth proportionally to dataset size:
- Under 50 cleaned rows: compact (3-5 items per ranked section, skip persona breakdown)
- 50-200 cleaned rows: standard (5-7 items per ranked section)
- Over 200 cleaned rows: full depth (8-10 items per ranked section, include persona/segment breakdown and market signals)
Never pad with low-quality items to hit counts. Prefer fewer strong items over filler.

## Non-Negotiables
1) Never include nonsensical/metadata artifacts as evidence.
2) Prefer fewer high-quality quotes over noisy examples.
3) Every major claim must be traceable to clean evidence.
4) If evidence is weak, say so explicitly.

## Evidence Hygiene (Hard Filter)
Reject any quote containing:
- schema/header artifacts (id, 录入日期, zendesk id, channel, order id, 用户原文, 一级分类/二级分类/三级分类)
- token/timecode noise (for example repeated 00:00 chains)
- metadata + fragment mashups
- low-semantic/no-meaning text

A valid quote must:
- read like real customer voice
- contain a clear opinion, issue, request, or comparison
- stand alone without spreadsheet context

If no clean evidence exists for a section:
- Output: "No clean representative quote available."

## Insight Depth Requirements
For each major theme, go beyond frequency:
- Root cause (why users feel this)
- Trigger moment (when sentiment flips)
- Business consequence (conversion/churn/trust/reviews)
- Segment affected (new buyers, power users, creators, value seekers, churners)
- Time sensitivity (urgent vs monitor)

Distinguish:
- Loud minority complaints vs broad recurring friction
- Emotional intensity vs volume
- Feature request vs expectation/education gap

## Language Policy
- If quote is non-English, include concise English translation in parentheses.
- Keep original quote only when nuance matters.
- Do not include broken multilingual fragments.

## Required Output Structure

### 1) Executive Decisions (Top of report)
- Amplify Now (1-2): strongest value drivers to push in marketing
- Fix Now (1-2): highest-risk frictions requiring immediate response
- Monitor (1-2): emerging themes not yet urgent

### 2) Strategic Pulse
- Strategic sentiment (one line with nuance)
- Bottom line (one line)
- Top risk (one line)
- Top opportunity (one line)

### 3) KPI + Signal Quality
| Metric | Value | Why It Matters |
Include:
- Total records analyzed
- Clean evidence used
- Clean evidence ratio (%)
- High/Critical themes
- Competitor mention rate

### 4) Top Insights & PR Risks (5-10 rows scaled to dataset size)
| Priority | Theme (specific) | Coverage | Severity | Confidence | Why It Matters | Immediate Action |
Theme names must be specific (for example "Battery expectation gap", "Support trust erosion", "Price-value objection").

### 5) What Users Love (Top 5-10 Praise Points, scaled to dataset size)
For each:
- What they love (1 line)
- Representative clean quote
- Business implication (what to amplify in marketing)
Rank by frequency and emotional intensity.

### 6) What Users Criticize (Top 5-10 Criticism Points, scaled to dataset size)
For each:
- What they criticize (1 line)
- Representative clean quote
- Severity (critical / high / medium)
- Owner (Engineering / Product / Support / Marketing)
Rank by severity then frequency.

### 7) What Users Want (Top 5-10 Feature Requests, scaled to dataset size)
For each:
- Feature requested (1 line)
- User segment most requesting it
- Classification: Roadmap Opportunity | Usability Fix | Competitor Parity | Niche
- Representative clean quote
Rank by volume and strategic value.

### 8) Deep Dives (top 3 themes by business impact)
For each theme provide:
- What users are saying (2-3 bullets)
- Representative clean quotes (max 2)
- PMM implication (message/positioning)
- Product implication (fix/roadmap)
- Owner + urgency
- Success metric (how we know this improved)

### 9) Competitor Switching Signals (all mentioned competitors)
| Competitor | Switching Trigger | We Win / They Win | Counter-message | Product Counter-move |

### 10) Persona / Segment Breakdown (for datasets over 200 rows)
- Who is saying what (new buyers, power users, creators, churning users)
- Which market/language is loudest
- Sentiment by segment
If dataset is under 200 rows, skip this section.

### 11) 14-Day Action Plan
| Action | Owner | Priority | Channel | Success Metric | Deadline |
Channel examples: creator brief, landing page update, support macro, app-store response, release note.

## Quality Bar (Self-Check)
- No dirty quotes anywhere in the report.
- No generic recommendations like "improve quality."
- Every action includes owner + metric.
- Praise, criticism, and feature lists are ranked and specific.
- Report is immediately usable in PMM and leadership review.
"""