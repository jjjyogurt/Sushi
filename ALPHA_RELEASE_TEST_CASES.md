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

- Go if all `P0` cases pass, no Sev1 issues remain, and deploy-blocking tests are green.
- Hold release if any `P0` case fails, especially project create/edit, auth boundaries, or analysis error mapping.

