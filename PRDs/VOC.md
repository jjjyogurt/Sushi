Time: March 30, 11 AM
PRD: AI-Powered VOC Insight Engine (v1.5)
1) Executive Summary
Objective
Transform raw, high-volume customer feedback into trusted, editable, and actionable insights through a simple end-to-end VOC workflow.

Target Users
Product Managers
Customer Service Representatives
Initial group size: ~10 users.

Product Intent
The product should answer:

What users love/hate
What product insights should go back to R&D
Which pain points should be prioritized
Which critical risks require immediate action
2) Core User Journey (Source of Truth)
Enter VOC panel
Start and name a project
Upload raw data (relevant formats)
Start data cleaning
Review cleaned data sheet (scroll and/or download)
Hit start analysis
AI processes in background (async)
Generate insights report (based on active system prompt/skills/template, fully editable)
Output final report
All feature decisions must support this journey.

3) Scope
In Scope (Phase 1)
VOC project creation and management
Raw data upload + validation
Two-agent pipeline (Data Cleaner + Analyzer)
Cleaned data sheet preview + download
Async processing status tracking
Editable AI-generated report
Evidence-backed insights (representative quotes + counterexamples)
Decision fields:
Owner, Team, Severity, Confidence, Recommended Action, Due Date
VOC settings under VOC (not Knowledge Base):
VOC Data Cleaner Skills
VOC Analyzer Skills
VOC Report Templates
Out of Scope (Phase 1)
Fully autonomous action execution
Unrestricted freeform prompt changes without guardrails
Broad social connector expansion beyond initial priorities
4) Functional Requirements
4.1 VOC Navigation and Project Setup
Left sidebar includes VOC (below Knowledge Base in nav).
VOC landing shows projects and New Project CTA.
Project requires name; optional description.
Project initial state: Draft.
4.2 Data Upload and Ingestion
Phase 1 supported inputs: CSV + support-ticket export format.
Upload validates schema and stores raw source in Bronze.
Every row receives processing ID.
Processing rule: every row must end as processed or failed; no silent drops.

4.3 Agent 1: VOC Data Cleaner
Role:

PII redaction, noise filtering, language detection, source tagging, schema normalization.
Output:

Silver dataset (cleaned/anonymized/normalized).
4.4 Cleaned Data Sheet Review
User can scroll cleaned rows and download cleaned file.
UI shows totals: total / processed / failed.
UI shows failure reasons by category.
4.5 Agent 2: VOC Analyzer
Role:

Categorize all records into Pains/Gains/Requests.
Generate thematic insights, confidence labels, and evidence mapping.
Suggest default decision fields.
Output:

Gold insights dataset + evidence links + report-ready structures.
4.6 Async Processing
Queue + workers for cleaning and analysis.
Run states: queued, running, completed, failed, partial.
Retries with backoff for transient errors; DLQ for exhausted retries.
Users can leave and return; progress persists.
4.7 Report Generation and Editing
Report auto-generated after analysis.
Report is fully editable before publish.
Top insights require all decision fields.
Required top-insight fields:

Owner
Team
Severity (Low | Medium | High | Critical)
Confidence (numeric + label)
Recommended Action
Due Date
4.8 Final Report Output
Output in-app published report + downloadable export.
Include metadata:
run timestamp
cleaner skill version
analyzer skill version
report template version
Every key claim traceable to source evidence.
5) VOC Settings (Under VOC, Below Knowledge Base)
All VOC controls are placed under VOC section in settings/navigation, not under Knowledge Base.

5.1 VOC Data Cleaner Skills
Base skill (immutable platform baseline)
Workspace overlay (editable)
Lifecycle: Draft -> Validate -> Active
Version history + rollback
Guardrails:
cannot weaken PII policy
must pass schema validation
5.2 VOC Analyzer Skills
Same lifecycle/version model as Data Cleaner Skills
Defines taxonomy guidance, severity heuristics, synthesis style
Guardrails:
citation/evidence requirements cannot be disabled
must pass validation before activation
5.3 VOC Report Templates
Default template provided: Consumer Hardware Best-Practice Report
Workspace-editable template version (clone/edit/activate)
Lifecycle: Draft -> Preview -> Active
Version history + rollback
Required sections cannot be removed:
Executive Summary
Key Pains/Gains/Requests
Critical Risks
Evidence and Counterexamples
Recommended Actions + Owners + Due Dates
6) Quality Gates
6.1 Publish Policy with Failed Rows
0%–1% failed rows: publish allowed with warning
>1%–5%: publish allowed only with explicit reviewer acknowledgment
>5%: publish blocked until retry/reprocess
Any failure in critical source connector: publish blocked regardless of ratio
6.2 Confidence Thresholds
High: >= 0.80 (fixed)
Medium: 0.60–0.79
Low: < 0.60
6.3 Confidence Gating
High: normal flow
Medium: publish allowed with visible confidence badge
Low:
excluded from automatic Top insights
requires explicit human approval to include in final report
reviewer must inspect evidence panel before approval
7) Evidence and Trust Requirements
For each key insight/claim:

Representative Quotes: 1–5
Counterexamples: 1–5 (or explicit none-found reason)
Source metadata: channel, timestamp, language, anonymized ID
Traceability links to source records
Coverage stats (count and percentage)
All substantive chat/report claims must be evidence-backed.

8) UI and Design Requirements
Follow designer.md:

Calm, minimal, low-noise interface
No purple hues
Sparse primary blue usage for primary actions only
One dominant CTA per view
Dense details in side drawer/panel (avoid card clutter)
Accessibility:
text contrast >= 4.5:1
visible keyboard focus
target size >= 36px
no color-only status signaling
9) Reliability, Security, Operations
Medallion architecture:
Bronze (raw immutable)
Silver (cleaned)
Gold (insights/evidence/index metadata)
Idempotency key per row/stage
Retry + DLQ handling
PII redaction checks and post-check scans
Operational metrics:
queue lag
retry/DLQ rate
processing completion
citation coverage
confidence distribution drift
10) Success Metrics (Current Scale: 10k–30k messages/month)
Core
Coverage: 100% rows end in processed or failed
Accuracy: >90% AI-human agreement on categorized samples
Time-to-insight: ~10h to <15min
Trust
100% substantive claims include evidence references
100% top published insights include required decision fields
Performance (Phase 1 SLO)
Upload acceptance: <30s
End-to-end run completion (p95): <15min
Report/chat retrieval response (p95): <4s
PII leakage incidents: 0
Implementation Plan (Final, Journey-Aligned)
Phase 1 — VOC Entry + Project Setup (Week 1)
Build

Sidebar VOC entry
VOC project list and create flow
Project state model (Draft)
Exit

Users can create/open projects reliably.
Phase 2 — Upload + Bronze + Validation (Week 2)
Build

Upload API and parser
Bronze raw storage
Row IDs, schema validation, ingest counters
Exit

Every uploaded row is tracked; no silent loss.
Phase 3 — Data Cleaner + Cleaned Sheet (Week 3–4)
Build

Start Cleaning action
Cleaner worker pipeline
Cleaned sheet UI + download + failure reason view
Exit

Cleaned data review step is complete and usable.
Phase 4 — Analyzer + Async Run Status (Week 5–6)
Build

Start Analysis action
Analyzer worker pipeline
Async status UI (queued/running/completed/failed/partial)
Gold insight output with confidence/evidence links
Exit

End-to-end async processing stable and observable.
Phase 5 — Report Generation + Editing + Decision Fields (Week 7–8)
Build

Auto-generated report from analysis output
Full report edit capability
Required decision fields + publish validation
Confidence thresholds and gating enforcement
Exit

Editable report can be finalized with quality gates.
Phase 6 — VOC Settings: Skills + Templates (Week 9)
Build

Under VOC settings:
VOC Data Cleaner Skills
VOC Analyzer Skills
VOC Report Templates
Lifecycles:
Skills: Draft -> Validate -> Active
Templates: Draft -> Preview -> Active
Versioning + rollback + run snapshot IDs
Exit

Safe configurable behavior with auditability and rollback.
Phase 7 — Final Output + Hardening + Pilot (Week 10–12)
Build

Final report output flow
Publish-policy enforcement for failed-row ratios
Observability dashboards + alerting
Accessibility and UX polish
Internal pilot rollout
Exit

Weekly workflow runs end-to-end with stakeholder sign-off.
Test Strategy
Unit
Schema transforms
Confidence banding/gating
Decision-field validators
Skill/template activation validators
Integration
Upload -> Cleaner -> Analyzer stage handoffs
Retry/backoff/DLQ
Idempotency/dedupe
Version snapshot persistence
End-to-End
Full journey:
enter VOC -> create project -> upload -> clean -> review/download -> analyze -> async complete -> edit report -> output report
Publish gating by failed-row ratio
Low-confidence gating behavior
Skill/template version traceability in outputs
Open Decisions (Minimal)
Exact list of “critical source connectors” for hard publish block
RBAC detail for who can activate skills/templates
Final warning/acknowledgment copy for publish gate UX
Readiness Verdict
CLEAR FOR PHASE 1 BUILD once the 3 open decisions above are locked.

 