# Alpha Release Test Cases

This document is the release-quality runbook for the next alpha deployment.

## Scope

This checklist validates:

- Influencer video ingestion
- AI analysis quality and stability
- Report and chatbot reliability
- Auth and data isolation safety
- Deployment/migration health

## Release Gates

- `P0` (blocking): must pass before deployment.
- `P1` (required): must pass within 24 hours after deployment.
- `P2` (quality): must pass before widening alpha traffic.

## Ownership

- `ENG`: backend and frontend correctness, API and migrations
- `QA`: execution, evidence capture, pass/fail log
- `PMM`: analysis/report quality acceptance

## Environment Matrix

- `Staging` (mandatory): full P0 + smoke P1
- `Production` (mandatory): deploy smoke + PIPE-REAL-001

## Exit Criteria (Go/No-Go)

Go only if all are true:

- All `P0` tests pass in staging
- DB migrations complete with zero manual intervention
- Production smoke tests pass within 30 minutes after deploy
- No Sev1 or unresolved security/data-isolation issue

No-Go if any are true:

- Any `P0` fail
- Any auth boundary or cross-account leakage issue
- Any critical analysis/report/chat hallucination in core claims

## Evidence Requirement

Every executed case must record:

- `Case ID`
- `Executor`
- `Timestamp`
- `Result` (`Pass`/`Fail`/`Blocked`)
- `Evidence` (screenshot, API response, logs, query snippet)
- `Defect Link` (if failed)

## P0 Blocking Cases (Must Pass Before Deploy)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| DEP-001 | App Startup Health | New build artifact ready | Start app in clean environment | Service boots successfully and health endpoint is healthy | Integration |
| DEP-002 | Migration Safety | DB backup exists, target DB reachable | Run startup/migrations once | Migrations complete without runtime errors or destructive drift | Integration |
| DEP-003 | Rollback Readiness | Previous version artifact exists | Verify rollback command and config | Rollback procedure is executable and documented for this release | Manual |
| AUTH-001 | Auth Session Flow | Valid test user | Login -> `/auth/me` -> logout -> `/auth/me` | `200 -> 200 -> 200 -> 401` | Unit/API |
| AUTH-002 | Auth Guard | No authenticated session | Request `/watchlist` | `401 Unauthorized` | Unit/API |
| DB-ACC-001 | Pipeline Ownership Binding | Two users (`A`, `B`) and one project owned by `A` | User A runs import -> analysis -> report -> chat and inspect records by `video_id` | Persisted rows remain within correct account/project scope; no ownership leakage | Integration + Manual SQL |
| VIDEO-001 | Video List Contract | Seeded videos | `GET /videos` | Correct payload shape, monitor profile name, analysis status, bookmark flag | Unit/API |
| ANL-001 | Analyze Happy Path | Video exists and providers healthy | `POST /videos/{id}/analyze` | Structured analysis payload returned with required fields | Unit/API |
| ANL-002 | Gemini Not Ready Mapping | Gemini unavailable | POST analyze | `503` with `GEMINI_NOT_READY` prefix | Unit/API |
| ANL-003 | Transcript Blocked Mapping | Transcript provider blocked | POST analyze | `503` with `TRANSCRIPT_BLOCKED` prefix | Unit/API |
| ANL-ASYNC-001 | Async Batch Create + Persist | Approved videos exist | `POST /analysis/batches` then refresh UI and poll batch status | Batch is created immediately, progress persists across refresh, final status is terminal (`completed`/`failed`) | API + E2E |
| RPT-001 | Report Completeness | Video has completed analysis | Generate report | Report includes sentiment/risk, praise, criticism, action plan, summary | E2E + Manual |
| RPT-ISO-001 | Insights Project Isolation | At least two projects exist; project A has an insights report and project B has no current report or a different report | Open project A Insights, start/finish Refresh Report, immediately switch to project B Insights, and inspect `/monitor-profiles/{id}/insights/current` for both projects | Project B never shows project A metrics, history, summary, or refresh loading state; hidden Insights content is not visible; API `monitor_profile_id` always matches the requested project | E2E + API |
| RPT-JOB-001 | Concurrent Insights Jobs | At least two projects exist; current user can access both; worker queue is enabled | Click Refresh Report twice on project A, then click Refresh Report on project B while A is still queued/running; inspect `/insights/jobs/active` for both projects | Project A creates one active job and keeps only A's button disabled; the duplicate click returns the same job; project B creates a separate active job and remains independent; completed reports write only to their own `monitor_profile_id` | Unit/API + E2E |
| CHAT-001 | Agent Grounding | Analysis exists | Ask chatbot for summary and top risks | Response is grounded in analysis context and evidence moments; no fabricated claims | E2E + Manual |
| PIPE-REAL-001 | End-to-End Real User Flow | One new YouTube URL not analyzed in current env | Create/select project -> import URL -> analyze -> open report -> ask chatbot -> cross-check evidence | Pipeline completes without manual DB fixes; output quality is decision-usable | E2E + Manual |

## P1 Required Cases (Within 24h Post-Deploy)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| PROJ-UI-005 | Edit Project Cancel | Edit panel open | Click `Cancel` | Panel closes and no change persists | E2E |
| PROJ-API-001 | Monitor Profile Validation | Existing profile | PUT invalid payload | `422` validation error | Unit/API |
| PROJ-API-002 | Monitor Profile Not Found | Missing profile id | PUT missing profile | `404` response | Unit/API |
| VIDEO-002 | Queue Filters | Seeded mixed risk/sentiment/title | Query filters | Correct subset returned | Unit/API |
| VIDEO-003 | Assignee Validation | Existing video | Patch unknown assignee | `400` with clear message | Unit/API |
| ANL-004 | Transcript Unavailable Mapping | Transcript unavailable | POST analyze | `422` with `TRANSCRIPT_UNAVAILABLE` prefix | Unit/API |
| ANL-005 | Missing Analysis Fetch | No analysis for video | `GET /videos/{id}/analysis` | `404 Analysis not found.` | Unit/API |
| ANL-006 | Analysis Determinism Smoke | Same video and same build/config | Run analysis twice | Required structure stable and no missing critical fields | E2E + Manual |
| ANL-ASYNC-002 | Async Batch Resume After Refresh | Running batch exists | Start run-all analysis -> hard refresh page -> revisit queue | UI resumes tracking same batch and does not restart from zero or lose server-side progress | E2E |
| ANL-ASYNC-003 | Async Batch Cancel | Running batch exists | `POST /analysis/batches/{id}/cancel` during execution | Remaining queued/running items are marked cancelled and batch status becomes `cancelled` | API + Integration |
| CHAT-002 | Agent Failure Handling | Simulate upstream failure | Ask chatbot follow-up | Graceful fallback with clear limitation and next step | E2E |
| DB-ACC-002 | Cross-Account Access Control | Two users and one analyzed video of `A` | User `B` attempts analysis/report/chat read on `A` video | Foreign account data access blocked (`401/403/404` by design) | E2E + API |
| DB-DATA-001 | Re-Import Idempotency | Same YouTube URL already analyzed | Re-import and re-analyze under same project | No ownership conflict, no orphan report/chat references | Integration + Manual SQL |
| OPS-001 | Startup Migration Health | Fresh DB | App startup | Migrations run cleanly | Integration |

## P2 Quality Cases (Before Wider Alpha Traffic)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| UX-001 | Empty States | No projects/videos/watchlist | Visit dashboard/queue/watchlist | Useful empty-state guidance appears | E2E |
| UX-002 | Responsive Layout | Narrow viewport | Open dashboard forms | Controls remain visible and usable | E2E |
| I18N-001 | Copy Coverage | EN and ZH locales | Scan key pages | No missing/fallback keys on critical paths | Manual/E2E |
| PERF-001 | Queue API Latency Smoke | Seeded data | Measure `GET /videos` latency | Meets agreed alpha baseline | Integration |
| AUDIT-001 | AI Traceability | Completed analysis and report | Inspect stored metadata | Prompt/model/version/time/source video ID are traceable | Integration |

## Deployment Test Timeline

1. `T-1 day`: run full staging P0 suite and fix blockers.
2. `T-2 hours`: re-run staging smoke (`DEP-001`, `DEP-002`, `AUTH-001`, `ANL-001`, `PIPE-REAL-001`).
3. `T+0 deploy`: deploy production build.
4. `T+30 min`: run production smoke (`DEP-001`, `AUTH-001`, `VIDEO-001`, `ANL-001`, `RPT-001`, `CHAT-001`).
5. `T+24h`: complete P1 verification and close release checklist.

## Run Commands

### Fast gate (P0 core)

```bash
python3 -m pytest \
  tests/unit/test_monitor_router.py \
  tests/unit/test_auth_watchlist_router.py \
  tests/unit/test_video_router.py \
  tests/unit/test_analysis_service.py \
  tests/unit/test_gemini_client.py
```

### Full regression

```bash
python3 -m pytest -q tests/unit
```

### Full regression (latest run evidence)

```bash
python3 -m pytest -q tests/unit
# Result on 2026-04-30: 117 passed, 1 warning
```

## Release Sign-Off Block

- Engineering Sign-Off: `Name / Date / Pass|Fail`
- QA Sign-Off: `Name / Date / Pass|Fail`
- PMM Sign-Off: `Name / Date / Pass|Fail`
- Final Decision: `GO` or `NO-GO`
- Notes: incident IDs, known non-blocking issues, follow-up owner
