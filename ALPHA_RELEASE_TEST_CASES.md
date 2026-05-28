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

### Browser Evidence Requirement

**Added 2026-05-25:** Any UI, E2E, or Manual case that depends on visible browser behavior must be verified with Codex `@Browser` in addition to API/unit evidence. Record the target URL, viewport size, screenshot path, and observed browser state. For responsive checks, capture at least one desktop viewport and one phone-width viewport.

## P0 Blocking Cases (Must Pass Before Deploy)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| DEP-001 | App Startup Health | New build artifact ready | Start app in clean environment | Service boots successfully and health endpoint is healthy | Integration |
| DEP-002 | Migration Safety | DB backup exists, target DB reachable | Run startup/migrations once | Migrations complete without runtime errors or destructive drift | Integration |
| DEP-003 | Rollback Readiness | Previous version artifact exists | Verify rollback command and config | Rollback procedure is executable and documented for this release | Manual |
| AUTH-001 | Auth Session Flow | Valid test user | Login -> `/auth/me` -> logout -> `/auth/me` | `200 -> 200 -> 200 -> 401` | Unit/API |
| AUTH-002 | Auth Guard | No authenticated session | Request `/watchlist` | `401 Unauthorized` | Unit/API |
| AUTH-003 | Local Alpha Account Seeds | Fresh or migrated local auth DB | Start app/migrations, then login with `Sushi_1` and one fruit account using password `1234`; inspect sign-in form before typing | All 35 alpha accounts exist with hashed passwords; legacy and fruit accounts can authenticate; sign-in fields are empty by default and no account/password is prefilled | Unit/API + Browser Manual |
| DB-ACC-001 | Pipeline Ownership Binding | Two users (`A`, `B`) and one project owned by `A` | User A runs import -> analysis -> report -> chat and inspect records by `video_id` | Persisted rows remain within correct account/project scope; no ownership leakage | Integration + Manual SQL |
| VIDEO-001 | Video List Contract | Seeded videos | `GET /videos` | Correct payload shape, monitor profile name, analysis status, bookmark flag | Unit/API |
| VIDEO-DISC-001 | User Keyword Discovery With Publish Window | User is signed in; project has user-defined brand keywords and key products; YouTube discovery can be mocked or run against a controlled fixture | Open the project video queue -> choose a publish window such as last 24 hours or last 7 days -> click Discover Videos -> inspect `/videos/discover` payload and resulting queue | Discovery sends `max_results=50`, the selected time trigger, and publish window; searches with user-defined keywords; saves relevant candidates when the keyword appears in title or description; keeps brand-level videos even without exact key-product text; and does not create alerts or analysis results by itself | Unit/API + Browser Manual |
| VIDEO-LIST-STRIP-001 | Video List Strip Essentials | User is signed in and a project has videos with completed and not-started analysis states | Open the project video list at desktop and phone-width viewports, then inspect completed and not-started rows | Rows show title, channel, a small completed check when applicable, and tiny muted published-date/views metadata; sentiment labels, explicit `Analysis status: completed` text, and language labels are not shown in the strip; bookmark/delete/select controls remain usable without overlap | Unit + Browser Manual |
| VIDEO-BULK-001 | Video List Bulk Delete + View Sort | Project has at least three videos with known or mockable YouTube view counts; one separate project exists for isolation | Open Project video list -> use the sort icon beside All Sentiments to choose Views High to Low and Low to High -> select two visible videos -> delete selected -> refresh list and inspect `/videos?monitor_profile_id=&sort_by=views&sort_order=` plus `/videos/bulk-delete` behavior | View sorting is deterministic with unknown counts last; the sort icon opens a single-select menu and preserves the selected sort; row numbers are visible on the left; selected count/select-all state is accurate; bulk delete removes only selected owned videos and dependent rows; invalid/foreign/active-batch selections fail without partial deletion | Unit/API + E2E |
| VIDEO-DETAIL-001 | Video Detail Metadata Labels | User is signed in and a project video is selected on `/projects/{id}` | Open the selected video detail header at desktop and phone-width viewports | Views, influencer subscribers, analysis status, and analysis language render as consistent label/value pills; published date remains secondary metadata; pills wrap without overlapping actions or title text | Unit + Browser Manual |
| ANL-001 | Analyze Happy Path | Video exists and providers healthy | `POST /videos/{id}/analyze` | Structured analysis payload returned with required fields | Unit/API |
| ANL-002 | Gemini Not Ready Mapping | Gemini unavailable | POST analyze | `503` with `GEMINI_NOT_READY` prefix | Unit/API |
| ANL-003 | Transcript Blocked Mapping | Transcript provider blocked | POST analyze | `503` with `TRANSCRIPT_BLOCKED` prefix | Unit/API |
| ANL-ASYNC-001 | Async Batch Create + Persist | Approved videos exist | Click Run All Analysis in the video list, inspect the notification, `POST /analysis/batches`, then refresh UI and poll batch status | User sees a clear “may take a few minutes, check back later” notification immediately; batch is created immediately, progress persists across refresh, final status is terminal (`completed`/`failed`) | API + E2E |
| RPT-001 | Report Completeness | Video has completed analysis | Generate report | Report includes sentiment/risk, praise, criticism, action plan, summary | E2E + Manual |
| RPT-ISO-001 | Insights Project Isolation | At least two projects exist; project A has an insights report and project B has no current report or a different report | Open project A Insights, start/finish Refresh Report, immediately switch to project B Insights, and inspect `/monitor-profiles/{id}/insights/current` for both projects | Project B never shows project A metrics, history, summary, or refresh loading state; hidden Insights content is not visible; API `monitor_profile_id` always matches the requested project | E2E + API |
| RPT-JOB-001 | Concurrent Insights Jobs | At least two projects exist; current user can access both; worker queue is enabled | Click Refresh Report twice on project A, then click Refresh Report on project B while A is still queued/running; inspect `/insights/jobs/active` for both projects | Project A creates one active job and keeps only A's button disabled; the duplicate click returns the same job; project B creates a separate active job and remains independent; completed reports write only to their own `monitor_profile_id` | Unit/API + E2E |
| RPT-LANG-001 | Insights Language Switch | Project has completed English and Chinese video analyses, or Chinese analysis can be generated during the test | Open project Insights -> verify English is selected -> switch to `中文` -> refresh report if no Chinese report exists -> switch back to English; inspect `/monitor-profiles/{id}/insights/current?language=en` and `?language=zh-Hans` | UI toggles active state correctly; Chinese report uses `zh-Hans` rows and Chinese user-facing text; English report remains unchanged; history/current/refresh/job APIs stay separated by `language`; no cross-language stale content or loading state appears | Unit/API + E2E |
| NAV-001 | VOC Navigation Hidden | User is signed in on desktop and mobile-width viewports | Open the app shell with `@Browser`, inspect the left sidebar and mobile bottom navigation, then navigate between Dashboard, Project, Watch list, Alerts, and Settings | VOC is not visible or keyboard-focusable in sidebar/mobile navigation; remaining navigation entries continue to switch panels correctly; VOC implementation remains untouched for later re-enabling | Browser E2E + Manual |
| BRAND-001 | Sushi Browser Tab Icon | New frontend build is loaded in a browser with cache disabled or cache-busted assets | Open the app with `@Browser` and inspect the browser tab/favicon asset | Browser tab uses the sushi emoji favicon; in-page header layout is unchanged; icon remains visible at normal tab size | Unit + Browser Manual |
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
| UX-002 | Responsive Layout | Narrow viewport | Open dashboard forms with `@Browser` | Controls remain visible and usable | Browser E2E |
| UX-003 | Dashboard Create Button Hover State | Dashboard is loaded on desktop and keyboard navigation is available | Use `@Browser` to hover and keyboard-focus `+ New Project` | Button keeps text legible, shows one thin monochrome beam moving around the frame, adds no off-brand glow, does not shift layout, and respects reduced-motion settings | Browser Manual/E2E |
| UX-004 | Phone Project Workspace Layout | 390px-wide phone viewport with at least one project | Use `@Browser` at 390px width to open Dashboard, expand `New Project`, open Project Workspace, and switch bottom navigation tabs | Mobile layout matches the web information hierarchy, form fields stack cleanly, bottom nav uses the same icon/label structure as the sidebar, Add Video URLs controls remain inside their card, and no page-level horizontal scroll appears | Browser Manual/E2E |
| UX-005 | UI Motion, Hover States, and Dashboard Scanability | User is signed in; at least one project has long keyword metadata and at least one video/watchlist row exists | Use `@Browser` on desktop and phone-width viewports to switch Dashboard, Project, Watch list, Alerts, and Settings; hover/focus project cards, video rows, watchlist rows, nav buttons, icon buttons, and primary/secondary buttons; expand a long project card; emulate `prefers-reduced-motion: reduce` | Panels enter with a subtle opacity/4px settle only when motion is allowed; hover and active states use consistent restrained background, border, shadow, and focus treatment; long dashboard keyword metadata is clamped by default and visible when the project card is expanded; no text overlap, layout shift, or console error appears | Browser Manual/E2E |
| UX-006 | Alerts Triage and Unanalyzed Video Detail | User is signed in; project has at least one unanalyzed video and at least one alert | Use `@Browser` to open Project Workspace, select an unanalyzed video, then open Alerts on desktop and phone-width viewports | Unanalyzed video detail does not show the analysis-start panel; Run Analysis remains the primary action; analysis errors render as a compact inline message; Alerts use clear severity/date/title/message/meta hierarchy with restrained critical styling and no wall-of-red layout; no horizontal overflow or console error appears | Browser Manual/E2E |
| UX-007 | Settings Collapse and Heading Hierarchy | User is signed in and Settings is open on desktop and phone-width viewports | Use `@Browser` to inspect Language, Account, All videos, Advanced Agent Prompt, Project Brain, and Advanced VOC Prompts; expand/collapse Project Brain and at least one other collapsible settings block | Settings section titles share one heading size, weight, casing, and meta alignment; Project Brain collapses to a compact header and expands without layout overlap; knowledge setup steps remain readable and controls stay usable on desktop and mobile | Browser Manual/E2E |
| UX-008 | App Typography Font Stack | New frontend build is loaded with cache disabled or cache-busted assets | Use `@Browser` on desktop and phone-width viewports to open Dashboard, Project Workspace, and Settings; inspect computed font families for normal text, native controls, transcripts, and monospace prompt/advanced settings fields | Main UI text and native controls use Geist, transcript and settings monospace fields use Geist Mono, and the font swap causes no text clipping, overlap, horizontal overflow, or layout shift in primary workflows | Browser Manual/E2E |
| UX-009 | Video Analysis Detail Spacing | Project has at least one completed analysis with summary, comments sentiment, transcript, evidence, and chat visible | Use `@Browser` on desktop and phone-width viewports to open the analyzed video detail view and inspect the top metadata, video embed, action row, analysis cards, transcript, evidence, and chat composer | The detail pane has clear spacing between major sections, analysis cards use readable padding, summary/comment lists do not feel compressed, long video links wrap safely, chat controls remain aligned, and no horizontal overflow or text overlap appears | Browser Manual/E2E |
| I18N-001 | Copy Coverage | EN and ZH locales | Scan key pages with `@Browser` | No missing/fallback keys on critical paths, the sidebar slogan renders `Get the market’s view, early.` on one line, and `early.` stays visually attached after the comma | Browser Manual/E2E |
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
