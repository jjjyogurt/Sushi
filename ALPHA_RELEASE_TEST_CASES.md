# Alpha Release Test Cases

This document defines the minimum release-quality checks for alpha rollout.

## Release Gates

- `P0` (blocking): must pass before any alpha deploy.
- `P1` (required): must pass before cohort expansion.
- `P2` (quality): must pass before public beta.

## Test Case Template

Each case should track:

- `Case ID`
- `Priority` (`P0`, `P1`, `P2`)
- `Area`
- `Preconditions`
- `Steps`
- `Expected Result`
- `Automation` (`Unit`, `Integration`, `E2E`, `Manual`)
- `Owner`
- `Status`

## P0 Blocking Cases (Must Pass)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| PROJ-UI-001 | New Project Form Visibility | Dashboard loaded | Click `+ New Project` | Form shows all controls: name, brand keywords, markets, languages, key products, sensitivity | E2E |
| PROJ-UI-002 | New Project Creation | Form visible | Fill valid values and submit | Project created; success feedback shown; card appears in project grid | E2E |
| PROJ-UI-003 | Edit Project Entry | Existing project card | Click 3-dot menu -> `Edit Project` | Edit panel opens with prefilled project values | E2E |
| PROJ-UI-004 | Edit Project Save | Edit panel open | Change fields and submit | Project card and backend data update successfully | E2E + API |
| PROJ-I18N-001 | Translation Safety | EN locale | Apply static translations | Form controls remain intact (labels update, inputs/selects remain in DOM) | UI integration |
| PROJ-I18N-002 | Locale Switch Safety | Dashboard loaded | Switch `EN -> ZH -> EN` | Create/Edit forms remain fully editable across locale changes | E2E |
| AUTH-001 | Auth Session Flow | Valid test user | Login -> `/auth/me` -> logout -> `/auth/me` | 200 -> 200 -> 200 -> 401 | Unit/API |
| AUTH-002 | Auth Guard | No authenticated session | Request `/watchlist` | 401 unauthorized | Unit/API |
| WATCH-001 | Watchlist Basic Flow | Authenticated session + existing video | Add then remove watchlist video | Bookmark state toggles correctly | Unit/API |
| WATCH-002 | Watchlist Isolation | Two users + same video | Add as user A, view as user B | User B cannot see A bookmarks | Unit/API |
| VIDEO-001 | Video List + Context | Seeded videos | GET `/videos` | Correct payload shape, monitor profile name, analysis status, bookmark flag | Unit/API |
| ANL-001 | Analyze Happy Path | Video exists and providers healthy | POST `/videos/{id}/analyze` | Structured analysis payload returned | Unit/API |
| ANL-002 | Gemini Not Ready Mapping | Gemini unavailable | POST analyze | 503 with `GEMINI_NOT_READY` prefix | Unit/API |
| ANL-003 | Transcript Blocked Mapping | Transcript provider blocked | POST analyze | 503 with `TRANSCRIPT_BLOCKED` prefix | Unit/API |
| GEM-001 | Gemini Analyze Contract | Test client initialized | Call `analyze_video` with canonical args | Accepts `source_language` and `target_output_language`; no legacy contract drift | Unit |
| DB-ACC-001 | Pipeline Ownership Binding | Two users (`User A`, `User B`), one project owned by `User A`, one new YouTube video | `User A` runs full pipeline (import -> analysis -> report -> chat), then query DB records by `video_id` | Persisted rows are linked to correct project/account scope; no ownership leakage to `User B`; `created_by/assigned_user_id` fields (when present) match expected actor | Integration + Manual SQL |

## P1 Required Cases (Before Expanding Alpha Cohort)

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| PROJ-UI-005 | Edit Project Cancel | Edit panel open | Click `Cancel` | Panel closes with no persisted changes | E2E |
| PROJ-API-001 | Monitor Profile Update Validation | Existing profile | PUT invalid payload | 422 validation error | Unit/API |
| PROJ-API-002 | Monitor Profile Not Found | Missing profile id | PUT `/monitor-profiles/{missing}` | 404 response | Unit/API |
| VIDEO-002 | Queue Filters | Seeded mixed risk/sentiment/title | Query filters | Correct subset returned | Unit/API |
| VIDEO-003 | Assignee Validation | Existing video | Patch with unknown assignee | 400 with clear message | Unit/API |
| ANL-004 | Transcript Unavailable Mapping | Transcript unavailable | POST analyze | 422 with `TRANSCRIPT_UNAVAILABLE` prefix | Unit/API |
| ANL-005 | Missing Analysis Fetch | No analysis for video | GET `/videos/{id}/analysis` | 404 `Analysis not found.` | Unit/API |
| ANL-006 | Analysis Persist + Determinism Smoke | One new YouTube video selected for alpha validation | Run analysis twice on same video within same build/config | Both runs return valid structured fields; no missing required sections; risk/sentiment class remains logically consistent | E2E + Manual |
| RPT-001 | Report Generation Completeness | Video has completed analysis | Generate report from analysis output | Report includes all required sections (sentiment/risk, praise, criticism, action plan, summary) and no empty critical blocks | E2E + Manual |
| CHAT-001 | Agent Grounding on Existing Analysis | Video analysis exists | Ask chatbot for summary + top risks + evidence moments | Bot answers from stored analysis context, cites moments/timestamps if available, no hallucinated product claims | E2E + Manual |
| CHAT-002 | Agent Failure Handling | Simulate analysis/report upstream failure | Ask chatbot follow-up on failed video | Bot returns graceful fallback (clear limitation + next step), no crash or blank response | E2E |
| DB-ACC-002 | Cross-Account Access Control for Analysis/Report/Chat | Two authenticated users and one analyzed video created by `User A` | Login as `User B`; attempt read actions on `User A` video (`GET analysis`, report fetch endpoint, chat ask endpoint) | Unauthorized access is blocked (`401/403/404` per design) and no foreign account analysis/report/chat payload is returned | E2E + API |
| DB-DATA-001 | Re-Import + Re-Analyze Idempotency | Same YouTube URL available; existing analysis already completed once | Import same URL again and trigger analyze again under same project; inspect DB state | No duplicate logical `video_candidates` ownership conflict; analysis versioning/history is valid by product design; analysis rows remain tied to same video/project; no orphan chat/report references | Integration + Manual SQL |
| GEM-002 | Oversize Fallback | Transcript near model limit | Analyze call triggers context oversize | Fallback to chunk/reduce succeeds | Unit |
| GEM-003 | Malformed Reducer Handling | Reducer returns invalid JSON | Analyze call | Raises controlled `GeminiResponseError` | Unit |
| OPS-001 | Startup Migration Health | Fresh DB | App startup | Migrations run cleanly without runtime errors | Integration |

## P2 Quality Cases

| Case ID | Area | Preconditions | Steps | Expected Result | Automation |
|---|---|---|---|---|---|
| UX-001 | Empty States | No projects/videos/watchlist | Visit dashboard/queue/watchlist | Helpful empty-state text shown | E2E |
| UX-002 | Responsive Layout | Narrow viewport | Open dashboard forms | Create/Edit controls remain visible and usable | E2E |
| PERF-001 | Queue API Latency Smoke | Seeded data | Measure GET `/videos` | Meets baseline latency target | Integration |
| I18N-001 | Copy Coverage | EN and ZH locales | Scan key pages | No missing/fallback keys in key workflows | Manual/E2E |
| DATA-001 | Duplicate Video Re-Import Safety | Same YouTube URL submitted twice | Import same video two times | System avoids duplicate logical records or clearly links reruns; no corrupted analysis associations | Integration |
| AUDIT-001 | Traceability of AI Outputs | Completed analysis + generated report | Inspect stored artifacts and metadata | Prompt/model/version/time and source video id are traceable for debugging and incident review | Integration |

## Full Pipeline Real-World Scenario (Alpha Launch Critical)

Use **one new YouTube video only** to control transcript-credit cost.

| Case ID | Priority | Area | Preconditions | Steps | Expected Result | Automation | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| PIPE-REAL-001 | P0 | End-to-End Real User Flow | Production-like environment, one fresh YouTube URL never analyzed in current env, authenticated test user | 1) Create/select project with relevant brand keywords. 2) Import video URL. 3) Wait until transcript fetch completes. 4) Trigger analysis. 5) Open generated report. 6) Ask chatbot: “Summarize sentiment, top 3 risks, and recommended action.” 7) Cross-check output against video/transcript evidence. | Pipeline completes without manual DB fixes; analysis and report are generated; chatbot responds correctly from analysis context; output includes risk level/score + clear praise/criticism + actionable recommendation; no critical section missing. | E2E + Manual | QA + PMM | Planned |

### PIPE-REAL-001 Validation Checklist (Pass/Fail)

- `Ingestion`: Video metadata, transcript status, and queue state update correctly.
- `Analysis Correctness`: Output has valid structure and evidence-backed claims; no contradictory sentiment/risk.
- `Report Correctness`: Required business sections render fully and are readable by non-technical stakeholders.
- `Agent Reliability`: Chatbot answers are grounded in generated analysis/report, not generic or fabricated.
- `Failure UX`: If any stage fails, user sees actionable error message and retry path.

### Suggested Pass Rubric for Real-World Scenario

- `Pass`: 0 blocking defects, 0 missing required report sections, chatbot accuracy acceptable on all asked prompts.
- `Conditional Pass`: Minor wording/formatting issues only; no correctness or trust issues.
- `Fail`: Any incorrect risk classification with clear evidence conflict, missing report core section, or chatbot hallucination on core claims.

## Execution Commands

### P0 gate command baseline

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
python3 -m pytest tests/unit
```

## Go/No-Go Criteria

- Go if all `P0` cases (including `PIPE-REAL-001`) pass, no Sev1 issues remain, and deploy-blocking tests are green.
- Hold release if any `P0` case fails, especially full pipeline correctness, auth boundaries, or analysis/report/chatbot trust issues.
