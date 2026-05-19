# Agent Work Log

## 2026-05-19 10:13

- Task: Deploy backend for video detail summary order update.
- Changes: Deployed `sushi-backend` revision `sushi-backend-00004-nbf` and logged the deployment.
- Check: Full unit suite 144 passed; `/health` 200; deployed JS order verified; new-revision ERROR logs empty.
- Next: None.

## 2026-05-19 10:07

- Task: Move sentiment/risk cards above the video summary.
- Changes: Reordered video detail markup so Sentiment and Risk Level render before Summary.
- Check: `node --check app/static/video-detail.js`; `pytest tests/unit/test_video_router.py tests/unit/test_api_mappers.py`; browser verified at `/projects/2`.
- Next: None.

## 2026-05-15 15:34

- Task: Fix missing project-card three-dot menu after icon migration.
- Changes: Added cache-busting query strings for changed frontend assets, versioned the SVG sprite URL, and made the three-dot icon more visible.
- Check: JS syntax checks and Chrome render check on Projects passed.
- Next: None.

## 2026-05-15 15:08

- Task: Remove icon-font flash from the web UI.
- Changes: Replaced Material Symbols ligatures with a local SVG sprite/helper and updated template, dynamic renderers, CSS, and i18n icon handling.
- Check: JS syntax checks, venv Python compile, curl asset checks, and Chrome/Playwright render checks passed.
- Next: None.

## 2026-05-14 18:55

- Task: Restore Cloud Run backend after analysis startup migration outage.
- Changes: Removed obsolete `analysis_results` legacy unique-index creation, added regression coverage, documented database/deploy notes.
- Check: `test_db_migrations.py` 9 passed; full unit suite 144 passed; deployed `sushi-backend-00034-6c2`; `/health` and root returned 200; revision ERROR logs empty.
- Next: Rotate exposed Cloud Run env secrets into Secret Manager.

## 2026-04-28 14:30

- Task: Project workspace — place Insights control beside back (top-right cluster).
- Changes: `index.html` — `queue-header-actions` wraps `open-insights-btn` + `back-to-dashboard-btn`; removed extra `button-row`; `styles.css` — flex cluster with 8px gap.
- Check: Not run.
- Next: None.

## 2026-04-28 14:00

- Task: Align Projects (dashboard) typography/spacing with VOC and other primary panels.
- Changes: `styles.css` — `#dashboard.panel` uses same panel padding + `.content:has(#dashboard.active)` as others; `.panel-header` flex row + intro `flex:1` (queue/insights stay column); `#dashboard .project-grid` gap 24px, margin-top 0.
- Check: Not run.
- Next: None.

## 2026-04-28

- Task: Remove Insights from left sidebar navigation.
- Changes: `index.html` — removed nav button `data-section="insights"`; `i18n.js` — dropped `navInsights` strings and STATIC_BINDINGS entry for sidebar Insights.
- Check: Not run.
- Next: Insights panel remains reachable via Project workspace “Insights” control (`open-insights-btn`) if desired.

## 2026-04-28 13:15

- Task: Match reduced top spacing on Insights, VOC, Watch list, Alerts, Settings (same as queue).
- Changes: `styles.css` — combined `#insights`, `#voc`, `#watchlist`, `#alerts`, `#settings` with queue panel padding rule; extended `.content:has(...)` for those panels’ `.active` state.
- Check: Not run.
- Next: None.

## 2026-04-28 13:00

- Task: Reduce empty vertical gap below topbar on project workspace (queue) page.
- Changes: `styles.css` — `#queue.panel` top padding 12px; `.content:has(#queue.panel.active)` padding-top 16px (stacks with panel less than before 24+40).
- Check: Not run.
- Next: None.

## 2026-04-28 12:30

- Task: Queue / project workspace header — same exit icon pattern as Insights (bordered icon-only back).
- Changes: `index.html` queue-header-row + `btn-secondary btn-icon-only`; `styles.css` queue header flex; `i18n.js` `back` on `aria-label`.
- Check: Not run.
- Next: None.

## 2026-04-28 12:00

- Task: Insights header — move back control top-right; icon-only (keep arrow).
- Changes: `index.html` insights header row + `btn-icon-only`; `styles.css` flex row; `i18n.js` bind `insightsBackToProject` to `aria-label`.
- Check: Not run.
- Next: None.

## 2026-04-24 15:00

- Task: Deploy Sushi app to Cloud Run + Firebase; create Cloud SQL instance, database, user; enable APIs; build container; configure env vars and IAM.
- Changes: Cloud infrastructure deployed (see DEPLOY_LOG.md); AGENT_WORK_LOG.md updated.
- Check: Cloud Run service created but running placeholder image due to SQLite→PostgreSQL SQL compatibility issue in app code.
- Next: Fix SQLite-specific `datetime()` SQL syntax in app to be PostgreSQL-compatible, then rebuild and redeploy.

## 2026-04-24 16:15

- Task: Implement PostgreSQL SQL compatibility fix; modify `cleanup_orphan_video_data()` to detect database dialect and use appropriate timestamp comparison syntax.
- Changes: `app/db_migrations.py` - added dialect detection with `connection.dialect.name` and conditional SQL generation for SQLite (`datetime()`) vs PostgreSQL (direct comparison); submitted Cloud Build; deployed new revision to Cloud Run.
- Check: `python3 -m pytest tests/unit/` — 93 passed; Cloud Run revision `sushi-backend-00006-pfk` deployed; startup logs show "Application startup complete" and "Uvicorn running on http://0.0.0.0:8080"; database connection successful.
- Next: Debug separate Jinja2 template caching error causing 500 errors on HTTP requests, or investigate if it's a library version compatibility issue.

## 2026-04-23 17:10

- Task: Deploy prep items 1–8 and 15: Postgres driver, env/cookies, auth user list lock + manual login, Docker, Firebase Hosting → Cloud Run rewrites.
- Changes: `requirements.txt`, `app/config.py`, `app/db.py`, `app/api/auth_router.py`, `Dockerfile`, `.dockerignore`, `.env.example`, `firebase.json`, `public/index.html` removed, `index.html` / `auth.js`, `tests/unit/test_auth_list_users.py`.
- Check: `python3 -m pytest tests/unit/` — 93 passed.
- Next: Deploy Cloud Run service id `sushi-backend` in `asia-southeast1`, set `DATABASE_URL` + attach Cloud SQL; `firebase deploy --only hosting`.

## 2026-04-21 19:35

- Task: Remove inline "Any time" link when custom date range is set; rely on native `<select>` for Any time / presets; clear date inputs when leaving custom.
- Changes: `index.html` / `queue.js` / `styles.css` / `i18n` static binding cleanup; removed mousedown `preventDefault` on preset.
- Check: Not run.
- Next: Re-edit custom via another preset then Custom if needed.

## 2026-04-21 19:10

- Task: Discover time dimension — date-only (no hours): `type="date"`, local calendar bounds for custom + presets; UI labels; `formatVideoPublishedAt` / new `formatLocalDateYmd` in `ui-utils`.
- Check: Not run (JS/HTML).
- Next: QA DST boundaries for non-UTC locales.

## 2026-04-21 18:40

- Task: Replace custom time summary strip with short label on `<select>` custom option; mousedown re-opens editors; inline link resets to Any time.
- Changes: `index.html` preset row + `id` on custom option; `queue.js` `syncDiscoverPresetCustomOptionLabel`, `clearDiscoverPublishToAnytime`, mousedown handler; removed summary strip CSS; i18n static for inline reset; removed summary strings / custom option static overwrite.
- Check: Not run (UI/JS).
- Next: QA mousedown vs keyboard-only users.

## 2026-04-21 18:05

- Task: Collapse custom discover time inputs when start/end are valid; show summary chip to re-open.
- Changes: `#discover-publish-custom-summary` in `index.html`; `parseCustomPublishRangeFromDom` + `refreshDiscoverPublishCustomUi` in `queue.js`; styles; i18n strings.
- Check: Not run (JS/HTML/CSS).
- Next: Optional `input` debounce if browsers omit `change` until blur.

## 2026-04-21 17:35

- Task: Queue discover controls — grow custom time panel downward instead of flex-end “push up”.
- Changes: `.queue-controls` `align-items: flex-start`; Discover button `margin-top` to line up with field row; custom wrap panel + short reveal animation (`prefers-reduced-motion` safe).
- Check: Not run (CSS only).
- Next: Visual QA at 1080/860 breakpoints.

## 2026-04-21 17:10

- Task: Discover publish window — add custom local datetime range UI (start/end) alongside presets.
- Changes: Wrapped preset in `discover-publish-controls`, `datetime-local` inputs + visibility toggle in `queue.js`, CSS, i18n + static bindings for custom option and labels.
- Check: Not run (UI/JS only).
- Next: E2E or manual pass for locale switching and narrow layouts.

## 2026-04-21 16:45

- Task: Video discover optional publish time window + show published time in queue list and detail.
- Changes: Extended `VideoDiscoveryRequest` / triage / YouTube Data API + yt-dlp filtering; queue preset select and `formatVideoPublishedAt`; tests in `test_video_discovery_schema`, `test_youtube_discovery_service`, `test_triage_service`, `test_video_router`.
- Check: `pytest tests/unit/test_video_discovery_schema.py tests/unit/test_youtube_discovery_service.py tests/unit/test_triage_service.py tests/unit/test_video_router.py` (31 passed).
- Next: Optional custom date range UI; persist last-used preset if desired.

## 2026-04-21

- Task: Add Cursor agent skill `architect` for system design and ADRs.
- Changes: Created `.cursor/skills/architect/SKILL.md` with review process, principles, patterns, ADR template, checklist, and red flags; aligned frontmatter with project skills; grounded guidance with Read/Grep/Glob.
- Check: Not run (markdown-only).
- Next: Mention the skill in team onboarding or rules if you want it applied by default.

## 2026-04-10 13:59

- Task: Enable bulk URL paste on Project page and add `New` video label behavior.
- Changes: Added multi-URL textarea (max 100), auto-grow to 5 rows with scroll, batch add flow, `New` badge rendering, and auto-clear badges after any video action.
- Check: Not run (manual verification recommended in Project workspace UI).
- Next: Validate UX with mixed valid/invalid URLs and confirm badge clearing matches team expectations.

## 2026-04-10 16:32

- Task: Refine Project page URL input layout and sizing.
- Changes: Removed helper line under URL input and matched textarea/button baseline height to selector row while preserving expand-to-5 + scroll behavior.
- Check: Not run (visual check recommended on Project workspace).
- Next: Validate spacing/alignment at common desktop breakpoints.

## 2026-04-10 16:39

- Task: Remove over-explanatory placeholder copy in project form token inputs.
- Changes: Replaced “Type … then Enter” placeholders with concise labels (`Market`, `Language`, `Product name`) in create/edit forms.
- Check: Not run (quick UI copy check recommended).
- Next: Sweep remaining form placeholders for similarly verbose copy.

## 2026-04-10 16:42

- Task: Remove placeholder copy from project token input boxes.
- Changes: Cleared placeholders for market, language, and product-name token fields in create/edit project forms.
- Check: Not run (visual confirmation recommended).
- Next: Align placeholder strategy across all forms for consistent minimal UI.

## 2026-04-10 16:47

- Task: Remove dashboard subtitle copy under Projects header.
- Changes: Deleted “Create monitoring scopes and editorial rules.” from the Projects panel header.
- Check: Not run (quick visual check recommended).
- Next: Review remaining secondary helper copy for consistency with minimal style.

## 2026-04-10 18:23

- Task: Implement bilingual analysis (EN + ZH) with right-aligned detail toggle.
- Changes: Added per-language analysis persistence/query, dual-language analyze orchestration, DB migration for language index, and UI toggle in video detail action row.
- Check: `python3 -m compileall app`; lint diagnostics clean.
- Next: Verify migration on existing DB and manually validate toggle behavior on real videos.

## 2026-04-10 18:39

- Task: Make analysis language toggle independent from global UI locale and per-video.
- Changes: Switched to per-video analysis language state, preserved toggle across locale changes, and hardened Gemini output-language enforcement with mismatch correction fallback.
- Check: `python3 -m compileall app`; lint diagnostics clean.
- Next: Manually verify EN/ZH toggles on multiple videos with UI language set to Chinese.

## 2026-04-10 18:45

- Task: Prevent pipeline break on Gemini region-restriction errors.
- Changes: Added fallback in analysis service to reuse previous completed per-language analysis when Gemini returns location-not-supported errors instead of failing the run.
- Check: `python3 -m compileall app/services/analysis_service.py`.
- Next: Add UI metadata to indicate fallback-used vs freshly generated analysis.

## 2026-04-10 19:08

- Task: Switch to single Gemini analysis + translation workflow for EN/ZH persistence.
- Changes: Refactored analysis service to run canonical English analysis once, translate result/comments to zh-Hans in one translation stage, and persist both language rows with improved fallback sourcing.
- Check: `python3 -m compileall app/services/analysis_service.py app/services/gemini_client.py app/repositories/analysis_repository.py`.
- Next: Add integration tests for location-restricted fallback and partial translation failures.

## 2026-04-10 17:10

- Task: Add Chinese UI localization with a scalable i18n structure and Settings language switch.
- Changes: Added centralized `i18n` module, Chinese/English dictionaries, static DOM translation bindings, language persistence, a new Settings language selector, and localized runtime UI/status/error strings across dashboard/queue/video/voc/settings modules.
- Check: ReadLints run on edited files; no linter errors.
- Next: Validate full UI copy coverage in browser and refine any untranslated edge labels.

## 2026-04-10 18:31

- Task: Research comments-sentiment feasibility for the project video analysis pipeline.
- Changes: Reviewed current code paths and external API docs; identified no existing comment ingestion support and outlined robust implementation options.
- Check: Not run (research-only, no runtime changes).
- Next: Choose API strategy (YouTube Data API first, optional managed fallback) and implement async ingestion + sentiment stage.

## 2026-04-10 18:41

- Task: Add comments sentiment section to video analysis flow.
- Changes: Implemented YouTube comments ingestion + persistence, added comments sentiment summary/highlights/lowlights generation, exposed new API fields, and rendered the new section in video detail UI.
- Check: `python3 -m compileall app`; `pytest` not available in current shell.
- Next: Add `YOUTUBE_DATA_API_KEY` in env and validate with real videos in the Project page.

## 2026-04-14 15:22

- Task: Improve comments authenticity by adding user quote snippets.
- Changes: Updated comments prompt/output to require `{point, quote}` objects, added robust backward-compatible normalization in service/mapper, and updated video detail UI to render each point with its verbatim quote snippet.
- Check: `python3 -m compileall app`; ReadLints on edited files returned clean.
- Next: Re-run analysis on a real video and verify quotes appear under comment highlights/lowlights.

## 2026-04-14 16:03

- Task: Fix `[object Object]` comments rendering and add comprehensive tests.
- Changes: Hardened JS list renderers for object/string compatibility, updated analysis stubs/tests for structured comment points, and added mapper unit tests for both new `{point, quote}` and legacy string payloads.
- Check: `python3 -m pytest -q tests/unit/test_analysis_service.py tests/unit/test_api_mappers.py tests/unit/test_video_router.py`; `python3 -m compileall app`; ReadLints clean.
- Next: Validate in browser with hard refresh after re-run analysis to confirm quote snippets render correctly.

## 2026-04-14 16:48

- Task: Make comments sentiment prompt more unbiased and fact-based.
- Changes: Updated comments prompt instructions to enforce neutral tone, proportionate positive/negative coverage, explicit uncertainty for mixed evidence, and stricter anti-speculation guidance.
- Check: `python3 -m compileall app/services/gemini_client.py`; ReadLints clean.
- Next: Re-run video analysis and verify comments summaries read more balanced and evidence-grounded.

## 2026-04-13

- Task: Shorten manual video URL placeholder copy.
- Changes: Removed “one per line” / “每行一条” from `manualUrlsPlaceholder` in `app/static/i18n.js` (en + zh).
- Check: ReadLints on `i18n.js`; no issues.
- Next: None.

## 2026-04-13

- Task: Fix missing project `<select>` on Project workspace after i18n runs.
- Changes: Wrapped queue “Select Project” copy in `#queue-project-label` in `app/templates/index.html`; pointed `STATIC_BINDINGS` at that span in `app/static/i18n.js` so `textContent` no longer removes `#profile-select`.
- Check: ReadLints on edited files; no issues.
- Next: Smoke-test Project page in browser (en/zh).

## 2026-04-14

- Task: Duplicate-video manual add UX: structured 409, bottom toast with CTA, deep link `?video=`.
- Changes: `VideoProjectConflictError` + JSON409 from `POST /videos/manual`; `ApiError` in `api-client.js`; queue attaches `videoConflict`; `main.js` toast + `navigateToProjectVideo`; `#app-message` moved and fixed to bottom; `/projects/:id?video=:id` hydration on load.
- Check: `python3 -m pytest tests/unit/test_video_router.py tests/unit/test_triage_service.py -q` (12 passed).
- Next: Browser smoke-test toast above mobile nav and “Open video in project” navigation.

## 2026-04-14 (settings all videos)

- Task: Settings → expandable “All videos” list across projects with delete; duplicate-video toast adds “All videos” action.
- Changes: `all-videos-settings.js` (`GET /videos`, `DELETE`), `<details>` block in `index.html`, i18n + `STATIC_BINDINGS`, table styles, `showMessage` multi-action row, `appVideoSettingsActions` bridge in `main.js`.
- Check: `python3 -m pytest tests/unit/test_video_router.py -q` (7 passed); ReadLints on touched JS.
- Next: Browser check expand/load/delete and toast buttons on narrow viewports.

## 2026-04-14 (all videos chevron)

- Task: Show expanded/collapsed affordance on Settings → All videos.
- Changes: `expand_more` icon in summary + `[open]` rotate 180° in `styles.css`; summary `align-items: center`, `user-select: none`.
- Check: Not run (visual).
- Next: None.

## 2026-04-14 17:01

- Task: Fix VOC project selector not selecting reliably.
- Changes: Hardened `app/static/voc.js` project selection with valid-id fallback, empty-state placeholder/disable behavior, and state/report reset when no projects exist.
- Check: ReadLints on `app/static/voc.js`; no issues.
- Next: Quick browser smoke test: switch VOC projects and confirm uploads/report refresh per selection.

## 2026-04-14 17:04

- Task: Restore missing VOC project dropdown control.
- Changes: Prevented i18n from replacing the VOC label container by adding `#voc-project-label` span in `index.html` and targeting it in `i18n.js`; added `vocNoProjectsYet` translations and wired VOC empty-state placeholder to that key.
- Check: ReadLints on edited files; no issues.
- Next: Hard refresh browser and confirm VOC project select renders and remains visible after locale switch.

## 2026-04-14 17:27

- Task: Rewrite VOC cleaner/analyzer default prompts to suppress nonsensical report text without failing rows.
- Changes: Updated `DEFAULT_CLEANER_SKILL_CONTENT` in `app/voc_defaults.py` to always keep `status=cleaned` while blanking nonsensical rows via `cleaned_text=""`; added hard evidence-hygiene constraints to `DEFAULT_ANALYZER_SKILL_CONTENT`.
- Check: ReadLints on `app/voc_defaults.py`; no issues.
- Next: Re-activate or create new VOC cleaner/analyzer skill versions in Settings and rerun cleaning + analysis.

## 2026-04-14 17:29

- Task: Add VOC re-run and clean analysis actions.
- Changes: Added `Re-run Analysis` and `Clean Result` buttons to VOC Analyze panel (`index.html`), wired handlers in `app/static/voc.js` (`startAnalysis` reuse + report-state clear), and added i18n keys/bindings in `app/static/i18n.js` (en/zh).
- Check: ReadLints on touched files; no issues.
- Next: Hard refresh and verify both new Analyze actions update report/meta text as expected.

## 2026-04-14 17:48

- Task: Execute cleaner->analyzer->Gemini VOC report flow with reliability fallback.
- Changes: Added `GeminiClient.generate_voc_report`, integrated `VocService.start_analysis` to pass cleaned rows + active analyzer prompt to Gemini, and added local-report fallback on Gemini failure.
- Check: `python3 -m pytest -q tests/unit/test_voc_service.py tests/unit/test_voc_policy.py` (7 passed); `python3 -m compileall` on edited files.
- Next: Add API/integration tests for Gemini failure codes and payload-size chunking for very large VOC uploads.

## 2026-04-14 18:06

- Task: Fix chat composer flow where Send appears stuck and messages do not progress naturally.
- Changes: Updated `app/static/video-detail.js` with optimistic user/assistant chat entries, sending/disabled composer state, Enter-to-send, inline error + retry, and unified chat `user_id`; added i18n and chat error styling.
- Check: `python3 -m pytest tests/unit/test_analysis_service.py tests/unit/test_api_mappers.py tests/unit/test_voc_service.py` (9 passed); ReadLints clean for touched static files.
- Next: Hard refresh UI and verify chat send flow visually (input clears, “Sending...” appears, reply renders, retry works on failure).

## 2026-04-15 11:48

- Task: Build account auth, Watch list, and assignee workflow across API + UI.
- Changes: Added auth/session + watchlist models/routes/services, assignee patch endpoint, queue/detail bookmark controls, Watch list panel, login gate, i18n, and styling updates.
- Check: `python3 -m pytest tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py` (10 passed); ReadLints clean.
- Next: Optional follow-up: resolve existing `tests/unit/test_gemini_client.py` failures on this branch.

## 2026-04-15 14:06

- Task: Remove Watch list text from detail bookmark action button.
- Changes: Updated `app/static/video-detail.js` bookmark toggle to icon-only using `btn-icon-only`, with accessible `aria-label` and tooltip preserved.
- Check: ReadLints on edited file (no issues).
- Next: Confirm in browser if sidebar Watch list label should also be icon-only.

## 2026-04-15 14:35

- Task: Fix project search to match existing video list titles and clean the search UI.
- Changes: Added `title` filter plumbing (`video_router` -> `triage_service` -> `video_repository` normalized title contains), rewired queue search to refresh `/videos` with title query, removed candidate strip markup, and tightened search bar spacing.
- Check: `python3 -m pytest -p no:cacheprovider tests/unit/test_video_repository.py tests/unit/test_video_router.py` (15 passed); ReadLints clean.
- Next: Browser smoke-test keyword typing/search button in Project page for both project and global queue scopes.

## 2026-04-15 16:06

- Task: Add Garry Tan-style GSTACK QA skill for founder-mode product review.
- Changes: Created `.cursor/skills/gstack-qa/SKILL.md` with trigger terms, GSTACK framework, 10-star planning ladder, and reusable output template.
- Check: `ReadLints` on `.cursor/skills/gstack-qa/SKILL.md` (no issues).
- Next: Invoke with prompts like "run gstack qa on this feature" for strategic critique before implementation.

## 2026-04-15 16:16

- Task: Update alpha QA plan and run release-readiness testing.
- Changes: Expanded `.cursor` alpha QA plan with full P0/P1/P2 case catalog, release gates, and kill criteria; executed core and full unit suites.
- Check: `python3 -m pytest tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_gemini_client.py`; `python3 -m pytest tests/unit` (5 failures in `test_gemini_client.py`).
- Next: Align `GeminiClient.analyze_video` call contract with tests/analysis flow and rerun alpha gate.

## 2026-04-15 16:52

- Task: Enforce canonical Gemini analysis contract in tests and verify pipeline.
- Changes: Updated `tests/unit/test_gemini_client.py` to use `source_language` and `target_output_language` in all `analyze_video` calls.
- Check: `python3 -m pytest tests/unit/test_gemini_client.py tests/unit/test_analysis_service.py tests/unit/test_video_router.py` and `python3 -m pytest tests/unit` (all passing).
- Next: Optional cleanup: migrate FastAPI startup lifecycle from deprecated `on_event`.

## 2026-04-15 17:08

- Task: Restore project create/edit form and publish alpha release test cases.
- Changes: Updated dashboard form labels to use dedicated span targets in `index.html`, switched i18n bindings to safe span selectors, and added `ALPHA_RELEASE_TEST_CASES.md`.
- Check: `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py` (26 passed); ReadLints clean.
- Next: Browser smoke check create/edit project in EN and ZH locales.

## 2026-04-15 17:15

- Task: Remove global search UI from topbar.
- Changes: Deleted `global-search-input` and its `search-wrap` container from `index.html`, removed corresponding i18n bindings in `i18n.js`, and cleaned up `bindGlobalSearch` and its call in `main.js`.
- Check: ReadLints on edited files; no linter errors.
- Next: None.

## 2026-04-15 17:37

- Task: Tighten video discovery to keyword-gated title matching and prefill project keywords.
- Changes: Added title keyword filter in `TriageService.discover_for_profile` with normalized boundary matching and slash-term expansion; prefilled create-project `brand_keywords` defaults in `main.js` while keeping the input editable.
- Check: `python3 -m pytest tests/unit/test_triage_service.py -q` (8 passed); ReadLints clean on touched files.
- Next: Optionally apply same title-gating to keyword search preview if you want identical behavior there.

## 2026-04-15 17:53

- Task: Add multilingual discovery query expansion across selected project languages.
- Changes: Updated `YouTubeDiscoveryService` to normalize language tags, generate per-language queries (English + localized review intent), localize keyword tokens (e.g., Smart), and merge/dedupe ytsearch results by `youtube_video_id`.
- Check: `python3 -m pytest tests/unit/test_youtube_discovery_service.py tests/unit/test_triage_service.py tests/unit/test_video_router.py -q` (18 passed); ReadLints clean.
- Next: Optionally add richer per-language keyword phrase dictionary for brand-specific local phrasing.

## 2026-04-15 18:01

- Task: Enforce language+market-aware discovery with localized keyword gating.
- Changes: Added YouTube Data API search using `relevanceLanguage` + `regionCode` per language×market, expanded localized keyword generation for filtering/scoring, and made title matching Unicode-safe in `TriageService`.
- Check: `python3 -m pytest tests/unit/test_youtube_discovery_service.py tests/unit/test_triage_service.py tests/unit/test_video_router.py -q` (22 passed); ReadLints clean.
- Next: Expand phrase dictionaries for additional non-Latin locales beyond current JP-focused mappings.

## 2026-04-15 18:19

- Task: Fix stale inherited videos on new projects and add Japanese mock regression coverage.
- Changes: Cascade-deleted all video-related rows in `MonitorRepository.delete`, added startup/data migration cleanup for orphan or stale video rows, and added tests including a `Mock HOVERAir Japan` project creation path.
- Check: `python3 -m pytest tests/unit/test_monitor_repository.py tests/unit/test_db_migrations.py tests/unit/test_monitor_router.py tests/unit/test_video_router.py tests/unit/test_triage_service.py tests/unit/test_youtube_discovery_service.py -q` (30 passed); ReadLints clean.
- Next: Optionally add a CLI/admin endpoint to run cleanup-on-demand without app restart.

## 2026-04-15 18:39

- Task: Ensure discovery query planning includes every keyword per language and market.
- Changes: Refactored `YouTubeDiscoveryService` query planner to generate per-keyword localized bundles across each language×market pair; added JP phrase mappings for default terms and tightened per-query result budgets to avoid over-fetching.
- Check: `python3 -m pytest tests/unit/test_youtube_discovery_service.py tests/unit/test_triage_service.py tests/unit/test_video_router.py -q` (23 passed); manual smoke run confirms `QUERY_COUNT=24` and non-empty JP results.
- Next: Add quality ranking/allowlist to reduce off-topic matches from broad terms like `ZZR`.

## 2026-04-15 17:37

- Task: Re-run alpha release validation and issue go/no-go recommendation.
- Changes: Executed P0 gate + full unit regression from `ALPHA_RELEASE_TEST_CASES.md`, browser smoke-tested create/edit/cancel + locale safety, and ran endpoint latency smoke on local server.
- Check: `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py`; `python3 -m pytest tests/unit`; browser smoke (pass); curl latency smoke (`/`, `/videos`).
- Next: Optional follow-up: add automated browser test for responsive viewport to remove manual gap.

## 2026-04-15 19:00

- Task: Rebuild video discover pipeline with Gemini localized queries and JP/DE tests.
- Changes: Added `DiscoveryKeywordService` + `GeminiClient.plan_youtube_discovery_queries`; `TriageService` builds plans (Gemini or keyword join fallback), calls `discover_live_with_specs` with `relevanceLanguage`/`regionCode`; removed hardcoded review/hint maps from `YouTubeDiscoveryService`; added `test_discovery_keyword_service.py` and JP/DE API tests.
- Check: `python3 -m pytest tests/unit/ -q` (81 passed).
- Next: Tune Gemini prompt if quota or off-topic queries appear; consider caching plans per profile hash.

## 2026-04-27 17:45

- Task: Fix failing auth tests and add missing discovery pipeline tests.
- Changes: Fixed auth router to use settings-based cookie security (`secure=settings.use_secure_cookies()`); fixed auth tests to mock settings for non-secure cookies; added 5 YouTube API edge case tests (empty results, errors, malformed, partial data, timeout); added 7 Gemini keyword fallback tests; added 4 video analysis 404/validation tests.
- Check: `python3 -m pytest tests/unit/` — 109 passed (was 90 passing, 3 failing).
- Next: Address the actual video discovery pipeline issue where "Discovery completed" shows 0 videos (possible API key or YouTube API quota issue).

## 2026-04-27 18:05

- Task: Add comprehensive logging to video discovery pipeline to diagnose "0 videos" issue.
- Changes: Added logging to `youtube_discovery_service.py` (10+ log points for API requests, responses, errors, timeouts, transport errors, JSON parse errors); added logging to `discovery_keyword_service.py` (Gemini vs fallback decision logging); added logging to `triage_service.py` (full discovery flow tracing including filters); fixed silent exception handling that was swallowing network errors.
- Check: `python3 -m pytest tests/unit/` — 109 passed.
- Next: Deploy and check Cloud Run logs to identify exact failure point in discovery pipeline.

## 2026-04-28 10:55

- Task: Implement project-level Insights snapshots and history on Project Workspace.
- Changes: Added `project_insight_reports` model, repository/service/router, new `/monitor-profiles/{id}/insights/*` APIs, queue-level Insights entry/panel, refresh/history UI, and i18n/style updates; snapshots use completed analyses with DB transcripts only.
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py tests/unit/test_video_router.py tests/unit/test_monitor_repository.py tests/unit/test_db_migrations.py` (all passed).
- Next: Optional follow-up: async refresh jobs + month-over-month compare deltas.

## 2026-04-28 11:03

- Task: Auto-fill auth account ID and password from account selector.
- Changes: Updated `app/static/auth.js` to sync selected user into `auth-user-id` and auto-apply default password on selector load/change and login gate open.
- Check: `python3 -m pytest tests/unit/test_auth_list_users.py tests/unit/test_auth_watchlist_router.py`; ReadLints clean on `app/static/auth.js`.
- Next: Optional UI tweak: surface selected account ID visibly under selector.

## 2026-04-28 11:12

- Task: Add Insights return button and history deletion controls.
- Changes: Added Back-to-Project and Clear History buttons in Insights UI, per-snapshot delete action in history list, and new backend delete endpoints (`DELETE /insights/history/{id}` and `DELETE /insights/history`).
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py tests/unit/test_video_router.py`; ReadLints clean on touched files.
- Next: Optional polish: add undo toast for accidental history delete.

## 2026-04-28 11:22

- Task: Upgrade Insights report structure and Gemini synthesis pipeline.
- Changes: Renamed sections to Praise/Criticism, added Team Action Plan + Methodology sections, and updated project insights generation to pass project transcript evidence + AGENTS prompt into Gemini with deterministic fallback.
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py tests/unit/test_video_router.py`; ReadLints clean on touched files.
- Next: Optional improvement: dedicated insights prompt versioning separate from AGENTS.md.

## 2026-04-28 11:26

- Task: Clarify that Insights synthesis is multi-video comprehensive reporting.
- Changes: Updated `generate_project_insights_report` prompt in `app/services/gemini_client.py` with explicit “not a single-video review” and “aggregate cross-video patterns” instructions before AGENTS.md guidance.
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py`; ReadLints clean on touched file.
- Next: Optional: add stronger conflict rule (“if AGENTS prompt conflicts, prioritize project-level aggregation”).

## 2026-04-28 12:02

- Task: Diagnose why dashboard projects disappear after login.
- Changes: Traced dashboard to `/monitor-profiles`, inspected Cloud Run revisions, and confirmed latest revision lacks `DATABASE_URL` and `ENVIRONMENT`, causing fallback to local SQLite.
- Check: `.venv/bin/python -m pytest tests/unit/test_monitor_router.py tests/unit/test_monitor_repository.py -q` (5 passed); live `/health` + monitor create/list/delete API checks; `gcloud run revisions describe` env diff.
- Next: Restore production DB/env vars on Cloud Run and rotate exposed secrets.

## 2026-04-28 14:13

- Task: Implement Cloud Run production DB fix for disappearing project data.
- Changes: Updated `sushi-backend` service env with `ENVIRONMENT=production` and Cloud SQL `DATABASE_URL`, rolled to revision `sushi-backend-00016-ktl`, and validated env/runtime behavior.
- Check: Live checks passed: `/health` 200, `/auth/users` 403, monitor profile create/list/delete persistence smoke test succeeded.
- Next: Rotate exposed DB/API credentials and migrate secrets to Secret Manager.

## 2026-04-28 11:58

- Task: Remove leaked credentials from deployment docs and add secret guards.
- Changes: Redacted raw `GEMINI_API_KEY` and DB password/URL in `DEPLOY_LOG.md`, switched deploy example to `--set-secrets`, added `.pre-commit-config.yaml`, `secret-scan.yml`, and README setup notes.
- Check: `rg` leak-pattern scan clean for real keys; `ReadLints` clean on touched files; `pre-commit` not installed locally.
- Next: Rotate compromised credentials and enable pre-commit on each developer machine.

## 2026-04-28 13:26

- Task: Improve Insights UX for generation state and project clarity.
- Changes: Added non-clickable `Generating...` refresh state with click guard in `insights.js`, and displayed current project name in Insights header via `insights-project-context`.
- Check: `node --check app/static/insights.js` and `node --check app/static/i18n.js`.
- Next: Optional polish: add spinner icon and elapsed time while generation runs.

## 2026-04-28 15:30

- Task: Run alpha test execution and report for Project Insights readiness.
- Changes: Executed P0 gate, full unit regression, and Project Insights module tests in live and deterministic modes.
- Check: `.venv/bin/python -m pytest tests/unit -q` (111/112 with live synthesis; 112/112 with `GEMINI_API_KEY=''`); P0 gate 32/32 pass.
- Next: Stabilize Insights refresh test path by disabling live Gemini in tests or enforcing deterministic synthesis.

## 2026-04-28 15:46

- Task: Create canonical backend deployment runbook.
- Changes: Added `BACKEND_DEPLOYMENT.md` with preflight, deploy, verify, rollback, and update-policy steps.
- Check: Matched values with `firebase.json`, `.firebaserc`, `.env.example`; `ReadLints` clean.
- Next: Optional: add `scripts/deploy_backend.sh` to mirror runbook commands.

## 2026-04-28 16:55

- Task: Document backend database design for fast onboarding.
- Changes: Added `DATABASE_DESIGN.md` with architecture flow, ER diagram, domain table map, transcript/analysis storage path, and Cloud Run/Cloud SQL linkage.
- Check: `ReadLints` clean on `DATABASE_DESIGN.md`.
- Next: Optional: add generated schema export (column/type matrix) for SQL-level auditing.

## 2026-04-28 17:09

- Task: Add rule for mandatory DB doc updates.
- Changes: Updated `AGENTS.md` with a Database Change Governance section requiring `DATABASE_DESIGN.md` updates and explicit "What Changed" notes for schema-impacting changes.
- Check: `ReadLints` clean on `AGENTS.md`.
- Next: Optional: add a PR checklist item enforcing this rule.

## 2026-04-28 17:58

- Task: Restore Cloud Run backend after DB credential update.
- Changes: Updated production `DATABASE_URL` to use `sushi-d9036-database` while preserving current credentials/socket config.
- Check: Cloud Run revision `sushi-backend-00021-h7g` deployed; root URL returned 200; startup log shows "Application startup complete".
- Next: Rotate exposed API keys/passwords and move DB URL to Secret Manager.

## 2026-04-28 18:05

- Task: Deploy latest backend to Cloud Run.
- Changes: Made project insights router tests deterministic by bypassing live Gemini synthesis in unit tests, then deployed source to `sushi-backend`.
- Check: `python3 -m pytest tests/unit -q` passed; revision `sushi-backend-00022-pn6` serves 100%; `/health` and root returned 200.
- Next: Move production secrets into Secret Manager before the next runbook-aligned deploy.

## 2026-04-28 18:08

- Task: Update backend deployment documentation for current env handling.
- Changes: Documented that `DATABASE_URL` is a Cloud Run env var and should not use missing Secret Manager entry `DATABASE_URL:latest`.
- Check: `ReadLints` clean on updated markdown files.
- Next: Keep future deploys preserving env vars unless runtime config changes.

## 2026-04-28 18:13

- Task: Deploy exact backend commit to Cloud Run.
- Changes: Deployed detached commit `05cf4a53a5971d28ab0a86e1b1e4e0b1c505348c` from a temporary worktree.
- Check: `python3 -m pytest tests/unit -q` passed; revision `sushi-backend-00023-wbj` serves 100%; `/health` and root returned 200.
- Next: Use this revision as rollback target if later local dirty-tree deploys regress.

## 2026-04-28 18:15

- Task: Add OTA web app deployment playbook.
- Changes: Created `OTA_DEPLOYMENT.md` and linked it from `BACKEND_DEPLOYMENT.md`.
- Check: Read back updated docs and checked git status for changed files.
- Next: Use the OTA playbook before future web app releases.

## 2026-04-29 11:30

- Task: Make Video AI chat follow the user's question language.
- Changes: Added chat prompt rules so context/transcript/video language does not override the user's latest question language.
- Check: `ReadLints` clean on `app/services/gemini_client.py`.
- Next: Test with a Chinese question over non-Chinese transcript content before release.

## 2026-04-29 11:36
- Task: Expand alpha release test plan with full real-world pipeline validation.
- Changes: Updated ALPHA_RELEASE_TEST_CASES.md with end-to-end single-video scenario and added analysis/report/chatbot reliability cases.
- Check: not run (documentation update only).
- Next: Execute PIPE-REAL-001 and mark pass/fail with defects.

## 2026-04-29 11:39
- Task: Add DB/account integrity tests to alpha release checklist.
- Changes: Added DB-ACC-001, DB-ACC-002, and DB-DATA-001 in ALPHA_RELEASE_TEST_CASES.md for ownership, access control, and idempotency validation.
- Check: not run (documentation update only).
- Next: Convert new DB cases into executable integration tests and SQL verification script.

## 2026-04-29 11:44
- Task: Run full unit regression and report alpha readiness test status.
- Changes: Executed complete pytest suite for tests/unit and collected summary.
- Check: 112 passed, 0 failed, 2 deprecation warnings.
- Next: Run PIPE-REAL-001 manual E2E scenario with one new YouTube video.

## 2026-04-29 11:47
- Task: Migrate FastAPI startup event hook to lifespan and verify no regressions.
- Changes: Replaced @app.on_event("startup") with FastAPI lifespan context in app/main.py; preserved migration/init sequence.
- Check: full unit suite passed (112 passed, 0 failed).
- Next: Optional smoke test app boot in deployed-like runtime.

## 2026-04-30 10:28
- Task: Implement the new project-level insights template with portfolio metrics and reach-weighted impact.
- Changes: Added sentiment/risk/reach/top-negative fields to project insights persistence/API, integrated YouTube view-count aggregation, removed Methodology/Snapshot UI blocks, and rendered new executive dashboard sections.
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py tests/unit/test_db_migrations.py`; `node --check app/static/insights.js && node --check app/static/i18n.js`.
- Next: Optional: persist periodic view-count snapshots per video to enable period-over-period reach trend charts.

## 2026-04-30 10:34
- Task: Tighten project insights LLM prompt schema to align output with new executive template.
- Changes: Updated `generate_project_insights_report` prompt with explicit field-level rules (decision-first summary, no methodology/snapshot language, competitor-win handling, tactical recommendations).
- Check: `python3 -m pytest tests/unit/test_project_insights_router.py -q`.
- Next: Evaluate one live refresh output and tune wording constraints if needed.

## 2026-04-30 11:05
- Task: Improve Insights distribution cards UI clarity.
- Changes: Replaced shorthand symbols/codes with explicit labels, counts, and percentages for sentiment and risk distribution cards.
- Check: `node --check app/static/insights.js && node --check app/static/i18n.js`.
- Next: Optionally add color badges/icons per risk tier for faster scanning.

## 2026-04-30 11:22
- Task: Redesign insights distribution UI with visual charts and reposition reach-weighted impact.
- Changes: Added three-card visual summary block (sentiment pie, risk pie, reach impact at right), removed old textual distribution cards and duplicate reach section.
- Check: `node --check app/static/insights.js && node --check app/static/i18n.js`; `python3 -m pytest tests/unit/test_project_insights_router.py -q`.
- Next: Optionally add tooltip hover for each pie segment to show exact count and percent.

## 2026-04-30 13:46
- Task: Refine insights visual typography, alignment, and spacing quality.
- Changes: Upgraded chart cards with stronger hierarchy, larger pie size, aligned legend label/value columns, tabular-number values, and structured reach rows with right-aligned metrics.
- Check: `node --check app/static/insights.js && node --check app/static/i18n.js`.
- Next: Optional final polish: add subtle hover state and micro-animation for chart cards.

## 2026-04-30 14:02
- Task: Redesign Insights history from fixed side panel to icon-triggered drawer.
- Changes: Removed persistent right history pane, added history icon beside Refresh, implemented right-side history drawer with backdrop, close button, and version selection/clear actions.
- Check: `node --check app/static/insights.js && node --check app/static/i18n.js`.
- Next: Optional: add keyboard Escape-to-close support for drawer.

## 2026-04-30 17:40
- Task: Replace executive summary with insights-first template and de-emphasize business impact.
- Changes: Updated AGENTS instructions, Gemini project-insights JSON contract, payload mapping, and UI labels/rendering for Headline/Core Insight/Top Risk Trigger/Immediate Focus.
- Check: python3 -m py_compile app/services/gemini_client.py app/services/project_insights_service.py app/api/project_insights_router.py app/schemas/project_insights.py
- Next: Refresh Insights for one project and confirm new fields render correctly.

## 2026-04-30 18:05
- Task: Retire legacy business_impact field end-to-end.
- Changes: Removed business_impact from models/schemas/services/UI/tests, added startup migration to drop legacy columns, and updated DATABASE_DESIGN.md with a What Changed note.
- Check: python3 -m py_compile app/main.py app/db_migrations.py app/services/gemini_client.py app/services/analysis_service.py app/repositories/project_insights_repository.py app/services/project_insights_service.py app/api/project_insights_router.py app/api/mappers.py app/schemas/analysis.py app/schemas/project_insights.py app/models/analysis_result.py app/models/project_insight_report.py tests/unit/test_db_migrations.py tests/unit/test_gemini_client.py tests/unit/test_analysis_service.py tests/unit/test_api_mappers.py tests/unit/test_project_insights_router.py tests/unit/test_video_router.py
- Next: Run full pytest suite in CI/local env with pytest installed.

## 2026-04-30 18:18
- Task: Remove sentiment/exclusion line and Immediate Focus from executive summary display.
- Changes: Updated AGENTS summary contract to 3 fields, removed immediate_focus from project insights payload/schema/API, and removed summary meta lines from insights/video detail UI.
- Check: python3 -m py_compile app/services/gemini_client.py app/services/project_insights_service.py app/schemas/project_insights.py app/api/project_insights_router.py
- Next: Refresh Insights UI and confirm summary now shows only Headline/Core Insight/Top Risk Trigger.

## 2026-04-30 18:28
- Task: Production-readiness testing for summary-template feature changes.
- Changes: Installed pytest and executed targeted + full unit suites covering migrations, mappers, analysis, Gemini parsing, video/router, and project insights.
- Check: 114 passed, 0 failed (tests/unit), plus targeted 35 passed.
- Next: Add integration smoke tests for UI rendering and startup migration against production-like PostgreSQL.

## 2026-04-30 14:55
- Task: Run full alpha release validation with focus on `ALPHA_RELEASE_TEST_CASES.md` and git diff risk review.
- Changes: Added release-readiness assessment; identified committed Cloud SQL export and metadata artifacts as blockers.
- Check: `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py`; `python3 -m pytest tests/unit` (all pass).
- Next: Remove sensitive export/artifact files from release commits and rerun P0 + real pipeline case before deploy.

## 2026-04-30 15:00
- Task: Fix release blockers by removing committed export artifacts and hardening ignore rules.
- Changes: Untracked/deleted `cloudsql_export_2026-04-28/*` and `.DS_Store`; updated `.gitignore`; cleaned trailing whitespace in docs.
- Check: `git diff --check`; `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py`.
- Next: Commit cleanup patch, then run PIPE-REAL-001 before production deploy.

## 2026-04-30 15:04
- Task: Commit release-cleanup patch and rerun full automated regression.
- Changes: Created commit `57aab8c` removing tracked export artifacts and strengthening `.gitignore`.
- Check: `python3 -m pytest tests/unit` (114 passed).
- Next: Execute manual `PIPE-REAL-001` in production-like env for final go/no-go.

## 2026-04-30 15:10
- Task: Deploy backend to Cloud Run using `BACKEND_DEPLOYMENT.md` runbook.
- Changes: Deployed `sushi-backend` to revision `sushi-backend-00024-xcv` in `asia-southeast1` with existing Cloud SQL attachment.
- Check: `python3 -m pytest tests/unit -q`; `/health` returned ok; revision status Ready; log scan shows clean startup.
- Next: Run manual `PIPE-REAL-001` end-to-end in production-like flow and record outcome.

## 2026-04-30 15:31
- Task: Re-test Video AI chat reply language and fix mismatch with user question language.
- Changes: Updated `ChatService` to detect language from latest question text and pass it to Gemini chat instead of video language; added regression test for Chinese question with German video language.
- Check: `PYTHONPATH=. ./.venv/bin/pytest -q tests/unit/test_chat_service.py` (5 passed).
- Next: Manually verify chat UI with Chinese/English/Japanese prompts on a non-English video record.

## 2026-04-30 15:35
- Task: Deploy latest minor updates to production Cloud Run.
- Changes: Deployed new backend revision `sushi-backend-00025-bl9` with 100% traffic.
- Check: `python3 -m pytest tests/unit -q` (115 passed); `/health` ok; latest revision Ready; startup logs clean.
- Next: Spot-check updated UI/chat behavior in production and monitor logs for 15-30 minutes.

## 2026-04-30 15:45
- Task: Diagnose and fix discovery mismatch + queue delete failure for new Aqua project.
- Changes: Enforced key-product title match during discovery; added full dependent-row cleanup in single-video delete; added regression tests.
- Check: `python3 -m pytest tests/unit/test_triage_service.py tests/unit/test_video_repository.py -q` and `python3 -m pytest tests/unit/test_video_router.py -q`.
- Next: Deploy patch and re-test delete + discovery behavior on production UI.

## 2026-04-30 16:49
- Task: Prepare alpha release deployment test-case runbook.
- Changes: Reworked ALPHA_RELEASE_TEST_CASES.md with P0/P1/P2 gates, deploy timeline, evidence, and sign-off blocks.
- Check: not run (document update only).
- Next: Execute P0 staging gate and capture evidence per case.

## 2026-04-30 16:51
- Task: Run alpha release test gates from checklist.
- Changes: Executed P0 core gate suite and full unit regression suite.
- Check: `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py`; `python3 -m pytest tests/unit`.
- Next: Run staging/prod manual smoke cases (PIPE-REAL-001, RPT-001, CHAT-001).

## 2026-04-30 16:55
- Task: Deploy backend to Cloud Run using backend runbook.
- Changes: Ran preflight tests, deployed sushi-backend revision 00026, verified health and traffic.
- Check: `python3 -m pytest tests/unit -q`; `curl /health` returned ok; latest revision serves 100% traffic.
- Next: Execute manual P0 smoke (PIPE-REAL-001, RPT-001, CHAT-001) in production.

## 2026-04-30 17:50
- Task: Make “Run all analysis” production-grade async with refresh-safe progress.
- Changes: Added durable batch queue tables/APIs, worker (`app/workers/analysis_batch_worker.py`), frontend polling/resume, and schema/docs updates.
- Check: `python3 -m py_compile ...`; `python3 -m pytest -q tests/unit/test_video_router.py tests/unit/test_monitor_repository.py tests/unit/test_db_migrations.py` (20 passed).
- Next: Deploy worker as separate service/process and add batch retry endpoint for failed items.

## 2026-04-30 17:53
- Task: Run full unit suite and update alpha release test checklist.
- Changes: Executed full `tests/unit` run and added async analysis batch test cases plus latest regression evidence in `ALPHA_RELEASE_TEST_CASES.md`.
- Check: `python3 -m pytest -q tests/unit` (117 passed, 1 warning).
- Next: Add dedicated unit/API tests for `/analysis/batches` endpoints and worker claim/cancel race conditions.

## 2026-05-06 10:20
- Task: Align insights generation with project scope and remove misleading risk-level UI.
- Changes: Switched project-insights Gemini input from transcript excerpts to full per-video transcripts; added strict prompt guardrails with project `brand_keywords` and `key_products`; removed insights Risk Level cards while keeping risk distribution visuals.
- Check: `python3 -m pytest -q tests/unit/test_project_insights_router.py tests/unit/test_gemini_client.py` (9 passed).
- Next: Refresh one Aqua insights report in UI to confirm summary stays project-focused and no off-scope competitor references appear.

## 2026-05-06 13:39
- Task: Redeploy backend with project-insights transcript/prompt scope updates.
- Changes: Deployed Cloud Run revision `sushi-backend-00027-llb` for service `sushi-backend` in `asia-southeast1`.
- Check: `python3 -m pytest tests/unit -q` (117 passed); `/health` returned `{"status":"ok","service":"sushi-backend"}`; revision serves 100% traffic; startup logs clean.
- Next: Trigger an Aqua insights refresh and verify summary references only project-scoped products/competitors.

## 2026-05-06 14:55
- Task: Migrate production database from Cloud SQL to Supabase to reduce fixed backend cost.
- Changes: Exported Cloud SQL, imported into Supabase, updated Cloud Run revision `sushi-backend-00028-86k`, cleared Cloud SQL attachment, stopped Cloud SQL, and updated backend/database docs.
- Check: Supabase table counts verified; `/health` and `/monitor-profiles` returned live data; Cloud Run logs had no revision errors.
- Next: Rotate exposed credentials and delete Cloud SQL after a short rollback window.

## 2026-05-06 16:10
- Task: Fix run-all analysis for discovered videos and deploy async worker.
- Changes: Removed approved-only batch filter, reset run-all button on create failure, added worker health server, deployed backend `00029-s8h` and worker `00001-lb6`.
- Check: `python -m pytest -q tests/unit` (119 passed); `/health` OK for backend/worker; live batch `1` completed `9/11`, with 2 transcript/ASR availability failures.
- Next: Add ASR fallback or clearer per-video transcript failure messaging, and rotate exposed API/database credentials.

## 2026-05-07 16:30
- Task: Remove Critical Risk Reach from project insights impact UI.
- Changes: Updated `app/static/insights.js` so the Impact card keeps Negative Reach while no longer rendering Critical Risk Reach.
- Check: `node --check app/static/insights.js`.
- Next: Refresh a project Insights report in the browser to visually confirm the Impact card layout.
## 2026-05-09 14:53
- Task: Improve first-run auth, dashboard visibility, queue layout, and settings clarity.
- Changes: Added demo login hint/fallback, dashboard loading state, desktop queue split layout, and collapsed advanced prompt settings.
- Check: `pytest tests/unit/test_auth_list_users.py tests/unit/test_auth_watchlist_router.py`; local Chrome visual verification.
- Next: Deploy updated static assets and verify the Cloud Run site after release.

## 2026-05-09 15:22
- Task: Fix misleading escalation and alerts behavior.
- Changes: Escalation now returns whether an alert was created; low-risk escalation shows follow-up copy; alerts include video, severity, owner, channel, and time.
- Check: `pytest tests/unit/test_incident_service.py tests/unit/test_incident_router.py tests/unit/test_video_router.py -q`; JS syntax checks; local browser/API verification.
- Next: Deploy and verify the production Alerts page after release.

## 2026-05-11 16:44
- Task: Align backend/database documentation with current design.
- Changes: Updated backend and database docs, Supabase env template, and stale managed-database comments.
- Check: `python3 -m compileall app/db.py app/main.py`.
- Next: Keep `BACKEND_SETUP.md` and `DATABASE_DESIGN.md` updated with dated notes for backend/database changes.

## 2026-05-11 18:10
- Task: Install Supabase Postgres best-practices skill.
- Changes: Added `supabase-postgres-best-practices` under `.agents/skills`.
- Check: Verified installed `SKILL.md` and reference files exist.
- Next: Restart Codex so the new skill is picked up.

## 2026-05-11 18:59
- Task: Implement account-scoped projects, videos, and per-user agent settings.
- Changes: Added project ownership, owner-aware API scoping, scoped YouTube uniqueness, DB-backed agent settings, hash-aware analysis cache, frontend conflict cleanup, and docs.
- Check: `python3 -m pytest -q tests/unit` (125 passed, 1 warning); `node --check app/static/main.js app/static/queue.js app/static/agent-settings.js`; Python compile checks.
- Next: Add transcript provider operational logging (`credits_used`, requested/returned language, source) without adding a shared transcript table.

## 2026-05-11 20:26
- Task: Run alpha release test gates on the current branch.
- Changes: Executed the documented P0 fast gate and full unit regression using the repo `.venv`.
- Check: `.venv/bin/python -m pytest ...` P0 fast gate (33 passed, 1 warning); `.venv/bin/python -m pytest -q tests/unit` (125 passed, 1 warning); `git diff --check` clean.
- Next: Complete staging/production manual and E2E alpha cases before final release sign-off.

## 2026-05-13 22:23
- Task: Move analysis worker from always-on polling to request-triggered Cloud Tasks draining.
- Changes: Added Cloud Tasks wake client, HTTP worker drain mode, continuation handling, worker env config, tests, and deployment/setup/database docs.
- Check: `python3 -m pytest tests/unit -q` (131 passed, 1 warning); `git diff --check` clean.
- Next: Deploy Cloud Tasks queue/private worker config and verify a production test batch drains.

## 2026-05-14 11:45
- Task: Run alpha release automated test gates.
- Changes: Executed `ALPHA_RELEASE_TEST_CASES.md` fast gate/full regression, Python compile, JS syntax, health startup probe, and diff whitespace check.
- Check: Fast gate 33 passed; full unit 131 passed; health returned 200; JS syntax and `git diff --check` clean.
- Next: Complete staging/production E2E and manual PMM quality gates before GO.

## 2026-05-14 11:53
- Task: Add subtle welcome motion to the sign-in popup.
- Changes: Added CSS-only overlay fade and auth card lift animations with reduced-motion handling.
- Check: `ReadLints` on `app/static/styles.css` passed.
- Next: Visually verify the first-load sign-in experience in browser.

## 2026-05-14 11:56
- Task: Remove unnecessary login-page account helper UI.
- Changes: Removed visible account selector and demo account hint while preserving default account selection behind the scenes.
- Check: `ReadLints` on edited auth template, JS, and CSS passed; `node --check app/static/auth.js`.
- Next: Refresh the login page to visually confirm only the password field remains.

## 2026-05-14 11:58
- Task: Fix login submit after removing account helper UI.
- Changes: Replaced hidden Account ID dependency with an internal default login user and removed leftover account-field markup.
- Check: Browser login verified locally; `node --check app/static/auth.js`; auth pytest subset 5 passed.
- Next: Deploy static/login assets and verify production sign-in.

## 2026-05-14 12:08
- Task: Add account input to login page.
- Changes: Added a visible Account text field and made sign-in use the typed account ID while keeping the demo hint removed.
- Check: Browser login verified with `Sushi_14`; `node --check app/static/auth.js`; auth pytest subset 5 passed.
- Next: Deploy static/login assets and verify production multi-account sign-in.

## 2026-05-14 13:52
- Task: Deploy the multi-account backend and request-triggered analysis worker.
- Changes: Enabled Cloud Tasks, configured worker IAM/queue, deployed backend `sushi-backend-00030-824`, deployed worker `sushi-analysis-worker-00002-9x6`, and updated deploy log.
- Check: `python3 -m pytest tests/unit -q` (131 passed); backend `/health` 200; Cloud Tasks worker health task completed; recent backend/worker error logs empty.
- Next: Production-smoke test login/project isolation and one analysis batch when ready.

## 2026-05-14 14:01
- Task: Add waiting state for manual multi-URL adds.
- Changes: Manual Add Videos now disables, shows busy state, and reuses the Discover button pulse until parsing/add completes.
- Check: `ReadLints` on `app/static/queue.js` and `app/static/i18n.js` passed.
- Next: Browser-test pasting multiple URLs on a project detail page.

## 2026-05-14 14:10
- Task: Remove topbar Project Sushi title.
- Changes: Left the topbar title area empty while preserving the right-side header actions.
- Check: `ReadLints` on `app/templates/index.html` passed.
- Next: Refresh the app to visually confirm the blank topbar title area.

## 2026-05-14 14:10
- Task: Add a minimal Help Center tutorial page.
- Changes: Added Help Center navigation, a three-step product guide, neutral documentation styling, and i18n bindings.
- Check: `ReadLints`; `node --check app/static/main.js app/static/i18n.js`; `git diff --check` on edited UI files.
- Next: Refresh the app and visually confirm Help Center layout and copy.

## 2026-05-14 14:13
- Task: Add visual guidance to Help Center tutorial.
- Changes: Added lightweight SVG guide images with numbered button callouts for project creation, video analysis, and insights.
- Check: `ReadLints`; `git diff --check` on edited Help Center files.
- Next: Refresh Help Center and confirm the guide images are visually clear.

## 2026-05-14 14:18
- Task: Align Help Center visuals with current frontend design.
- Changes: Replaced illustrative SVGs with mini guide panels built from existing app button/nav/pane classes.
- Check: `ReadLints`; `git diff --check` on edited Help Center files.
- Next: Refresh Help Center and compare the guide controls against the live UI.

## 2026-05-14 14:21
- Task: Refine Help Center visual guide alignment.
- Changes: Moved the Insights guide button to the right-side project header area and tightened callout/button spacing.
- Check: `ReadLints`; `git diff --check` on edited Help Center files.
- Next: Refresh Help Center and visually confirm spacing against the live UI.

## 2026-05-14 14:31
- Task: Redeploy backend for Help Center and URL button updates.
- Changes: Deployed Cloud Run backend revision `sushi-backend-00031-9h4` from commit `f7af631e9bcfdf8976273ef7ff50db31e3a414ef` and updated deploy log.
- Check: `python3 -m pytest tests/unit -q` (131 passed); static JS syntax checks passed; `/health` and `/` returned 200; recent backend error logs empty.
- Next: Open production Help Center and confirm the new URL button and guide visuals.

## 2026-05-14 15:21
- Task: Fix async Run All Analysis duplicate comment worker failure.
- Changes: Scoped `video_comments` uniqueness to each video candidate, added rollback-safe comment sync, and documented the DB index change.
- Check: `.venv/bin/python -m pytest -q tests/unit` (135 passed, 1 warning); `git diff --check`; Python compile checks.
- Next: Deploy backend/worker revision and run one production Run All Analysis smoke without rolling back the scale-to-zero worker.

## 2026-05-14 15:35
- Task: Deploy backend and scale-to-zero analysis worker fix.
- Changes: Deployed `sushi-backend-00032-mc2` and `sushi-analysis-worker-00003-mfq`, preserving Cloud Tasks request-triggered worker settings.
- Check: Backend and worker `/health` passed; Firebase Hosting returned 200; recent backend/worker ERROR logs empty.
- Next: Run a production Run All Analysis smoke test on a small QA batch.

## 2026-05-14 15:52
- Task: Harden manual multi-URL add UI.
- Changes: Add Videos now uses the shared busy pulse/disabled state, disables URL input during add, forces video refresh, and selects the first newly visible video.
- Check: `node --check app/static/queue.js`; local browser add-two-URLs smoke; `git diff --check`.
- Next: Deploy backend static asset refresh and verify production after cache refresh.

## 2026-05-14 15:57
- Task: Deploy manual multi-URL add UI refresh.
- Changes: Deployed `sushi-backend-00033-87k`; worker stayed on `sushi-analysis-worker-00003-mfq`.
- Check: `/health` passed; Hosting returned 200; production `queue.js` includes busy-state code; recent backend ERROR logs empty.
- Next: User smoke the Add Video URLs flow in production after a hard refresh.

## 2026-05-14 18:11
- Task: Add video reach metrics to analysis detail.
- Changes: Added a reach endpoint, YouTube subscriber lookup, and title-area UI pills for views/subscribers.
- Check: `PYTHONPATH=. pytest tests/unit/test_youtube_video_stats_service.py`; Python compile checks; router pytest blocked by missing FastAPI.
- Next: Run router tests in the project environment with FastAPI installed.

## 2026-05-14 18:15
- Task: Add audience and usage context to video analysis.
- Changes: Extended analysis prompts/API/UI to capture audience profiles and usage scenarios for future analyses while legacy videos stay empty.
- Check: `ReadLints`; `PYTHONPATH=. pytest tests/unit/test_api_mappers.py tests/unit/test_analysis_service.py` (11 passed).
- Next: Run a new analysis and verify the section appears below Summary.

## 2026-05-19 17:57
- Task: Align project card open buttons.
- Changes: Anchored Open Project to the bottom-left of project cards regardless of card content length.
- Check: `git diff --check`; local HTTP smoke.
- Next: Refresh the browser and compare cards with different keyword/product counts.

## 2026-05-19 17:56
- Task: Clean proactive monitoring card spacing.
- Changes: Shortened the card label to Monitoring, moved cadence to the right side, and reduced the cadence selector label size.
- Check: JS syntax checks; `git diff --check`; local HTTP smoke.
- Next: Refresh the browser and visually confirm the card row spacing.

## 2026-05-19 17:44
- Task: Refine proactive monitoring project-card UX.
- Changes: Moved edit form inline under the selected project card and added clickable daily/weekly/monthly cadence beside the proactive monitoring label when enabled.
- Check: `.venv/bin/python -m pytest -q tests/unit` (148 passed); JS syntax checks; `git diff --check`.
- Next: Visually confirm card edit expansion and cadence selector in the browser.

## 2026-05-19 17:35
- Task: Add proactive monitoring UI-first contract.
- Changes: Added persisted monitoring toggle/read-state fields, dashboard red dot, topbar digest button, proactive video New labels, API endpoints, migration docs, and tests.
- Check: `.venv/bin/python -m pytest -q tests/unit` (148 passed); JS syntax checks; `git diff --check`; local HTTP smoke on `127.0.0.1:8001`.
- Next: Implement backend scheduler, layered project-keyword YouTube discovery, monitor runs/items, and automatic analysis enqueue.

## 2026-05-14 18:24
- Task: Fix local startup migration failure.
- Changes: Skipped the legacy three-column analysis unique index when hash-aware analysis uniqueness is already present.
- Check: `PYTHONPATH=. pytest tests/unit/test_db_migrations.py tests/unit/test_api_mappers.py tests/unit/test_analysis_service.py` (19 passed); startup migration script printed `startup migrations ok`.
- Next: Restart local `uvicorn app.main:app --reload`.

## 2026-05-14 18:33
- Task: Clarify create-project validation failures.
- Changes: Added frontend project-name min-length validation and surfaced FastAPI validation messages instead of generic request failures.
- Check: `.venv/bin/python -m pytest tests/unit/test_monitor_router.py`; JS syntax checks; `git diff --check`.
- Next: Retry with a project name of at least 2 characters.

## 2026-05-15 15:35
- Task: Create standalone Project Workspace tutorial.
- Changes: Added a clean interactive HTML tutorial with playback, scene scrubber, spotlight, and product-marketing workflow narrative.
- Check: Browser smoke via local static server; controls and report scene verified; console errors empty.
- Next: Open the tutorial and adjust copy or pacing after product review.

## 2026-05-15 15:49
- Task: Align tutorial with Help Center colorway.
- Changes: Moved tutorial steps to the left, switched to white/soft-gray styling, removed the spotlight aura, and clarified step labels; removed the Help Center Tutorial link after review.
- Check: Browser visual smoke on tutorial; console errors empty; `git diff --check`.
- Next: Decide whether to keep or delete the standalone tutorial file.

## 2026-05-15 16:22
- Task: Run latest alpha release QA plan.
- Changes: Executed the plan's focused P0/P1 pytest gate and full unit regression without code changes.
- Check: `python3 -m pytest ...` focused gate 36 passed; `python3 -m pytest -q tests/unit` 144 passed, 1 warning.
- Next: Complete staging/manual alpha cases for report/chat, real pipeline, rollout telemetry, and rollback readiness.

## 2026-05-15 16:27
- Task: Improve shared bottom notification popup and discovery completion copy.
- Changes: Added larger glass-style toast design, longer default duration, and discovered-video count messaging.
- Check: `node --check` on edited JS; `git diff --check`.
- Next: Hard-refresh the app and visually confirm the toast treatment in the browser.

## 2026-05-15 17:33
- Task: Commit and deploy discovery toast backend release.
- Changes: Committed the toast/discovery copy changes, deployed Cloud Run revision `sushi-backend-00035-wr9`, and recorded the release.
- Check: P0 pytest gate passed; full unit suite 144 passed; Cloud Run `/health` and public URL passed.
- Next: Monitor alpha discovery flow and roll back to `sushi-backend-00034-6c2` if production health degrades.

## 2026-05-18 17:31
- Task: Deploy backend and analysis worker to US Cloud Run.
- Changes: Deployed `sushi-backend` and `sushi-analysis-worker` to `us-central1`; kept Gemini and Supabase settings unchanged; did not deploy Firebase.
- Check: US backend `/health` and root returned 200; US Cloud Tasks smoke invoked worker drain with HTTP 200; recent US ERROR logs empty.
- Next: Use the US Cloud Run backend URL for pilot testing.

## 2026-05-18 18:20
- Task: Update backend deployment docs and run alpha gates.
- Changes: Documented the `sushi-free-us-20260518` free-tier pilot target, `us-central1`, direct Cloud Run usage, and scale-to-zero worker behavior.
- Check: Alpha fast gate 36 passed; full unit regression 144 passed; `git diff --check` passed.
- Next: Deploy backend and worker to the new project, then run production smoke/manual alpha cases.

## 2026-05-18 18:28
- Task: Deploy free-tier pilot backend and worker.
- Changes: Deployed `sushi-backend` and private `sushi-analysis-worker` to `sushi-free-us-20260518` in `us-central1`; recorded the deployment.
- Check: Backend health/root/Gemini probe passed; Cloud Tasks worker smoke reached HTTP 200; no post-ready ERROR logs.
- Next: Run real YouTube import, analysis, report, and chat smoke on the new Cloud Run URL.

## 2026-05-18 21:21
- Task: Correct free-tier pilot database wiring.
- Changes: Updated Cloud Run backend and worker `DATABASE_URL` from local SQLite default to the existing Supabase session pooler.
- Check: Cloud Run env inspection confirmed Supabase host; backend health and Gemini probe passed; Supabase table counts were present.
- Next: Confirm existing projects/videos appear in the deployed app UI.

## 2026-05-18 21:30
- Task: Document local SQLite and production Supabase requirements.
- Changes: Updated backend deployment/setup docs to forbid deploying local SQLite `.env` to Cloud Run and require Supabase for backend and worker.
- Check: `git diff --check` passed.
- Next: Preserve or explicitly inject the Supabase `DATABASE_URL` on every production deploy.

## 2026-05-19 10:54
- Task: Clarify account prompt behavior for new video analysis.
- Changes: Updated agent prompt UI copy and added a unit test proving new analysis uses the latest saved account prompt.
- Check: `PYTHONPATH=. pytest -q tests/unit/test_analysis_service.py`.
- Next: Completed videos remain unchanged unless manually re-analyzed.
