# Deployment Log - Sushi App to Firebase + Cloud Run

## Date: 2026-05-19

### Video Detail Summary Order Backend Deploy

- Deployed `sushi-backend` revision `sushi-backend-00004-nbf` to `sushi-free-us-20260518` in `us-central1`, with 100% traffic.
- Scope: refreshed backend-served static assets so video detail pages show Sentiment and Risk Level above Summary.
- Verification: full unit suite passed (`144 passed, 1 warning`), backend `/health` returned 200, root GET returned HTML, deployed `video-detail.js` contains the new sentiment/risk-before-summary order, Cloud Run env inspection confirmed the Supabase pooler host, and recent new-revision ERROR logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00003-ckg` if the video detail UI regresses. Worker was not deployed because no batch or analysis worker code changed.

## Date: 2026-05-18

### Free-Tier US Pilot Cloud Run Deploy

- Deployed `sushi-backend` revision `sushi-backend-00002-2wc` to new project `sushi-free-us-20260518` in `us-central1`, with 100% traffic and direct Cloud Run access.
- Deployed private `sushi-analysis-worker` revision `sushi-analysis-worker-00002-4bh` from the same backend image, with `min-instances=0`, `max-instances=1`, `concurrency=1`, and `timeout=1800`.
- Corrected `DATABASE_URL` after initial deploy created revisions with the local SQLite default from `.env`; current revisions are `sushi-backend-00003-ckg` and `sushi-analysis-worker-00003-kpk`, both using the Supabase session pooler.
- Scope: moved the pilot backend and request-triggered analysis worker to a US free-tier-friendly Cloud Run project. Supabase remains the database. Firebase was not deployed.
- Runtime config: `gemini-3.1-flash-lite` is configured for both analysis and chat; the new Gemini key and new YouTube Data API key are Cloud Run env vars, not stored in git.
- Verification: alpha fast gate passed (`36 passed, 1 warning`), full unit regression passed (`144 passed, 1 warning`), backend `/health` returned 200, backend `/health/gemini?probe=true` returned `probe_ok=true`, root returned 200, Cloud Tasks invoked the private worker drain endpoint with HTTP 200 after cold start retries, Cloud Run backend/worker env inspection confirmed the Supabase pooler host, Supabase table counts were present, and no backend/worker ERROR logs appeared after the worker became ready.
- Rollback impact: route traffic to the previous `sushi-backend` revision in `sushi-free-us-20260518` if this deployment regresses. If worker dispatch regresses, redeploy `sushi-analysis-worker` from the same image and preserve `min-instances=0` unless actively debugging.

## Date: 2026-05-14

### Analysis Startup Migration Hotfix Deploy

- Deployed `sushi-backend` revision `sushi-backend-00034-6c2` from branch `codex/backend-startup-hotfix` at commit `a7b391c`, with 100% traffic.
- Scope: stopped the `analysis_results` language-column startup migration from recreating obsolete unique index `ix_analysis_video_version_language`; the intended uniqueness remains `ix_analysis_video_version_language_settings`.
- Verification: migration tests passed (`9 passed`), full unit suite passed (`144 passed, 1 warning`), production DB metadata confirmed `language` + `agent_settings_hash` columns and zero duplicate groups under the hash-aware key, backend `/health` returned 200 on both Cloud Run URLs, root page returned 200, new revision logs showed `Application startup complete`, and recent revision ERROR logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00033-87k` only if this hotfix regresses; note that `00033` can fail cold starts on the same duplicate-data startup path.

### Manual Multi-URL Add UI Deploy

- Deployed `sushi-backend` revision `sushi-backend-00033-87k` from branch `multi-account` at commit `f7af631e9bcfdf8976273ef7ff50db31e3a414ef` plus the approved uncommitted manual-add UI fix, with 100% traffic.
- Scope: Add Videos now uses the same waiting pulse/disabled state as Discover Videos, disables the URL input during submission, forces the video-list refresh after completion, and selects the first newly visible video.
- Verification: `node --check app/static/queue.js`, related API tests passed (`17 passed, 1 warning`), local browser add-two-URLs smoke passed, backend `/health` returned 200, Firebase Hosting returned 200, production `queue.js` contains the new busy-state code, and recent backend ERROR logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00032-mc2` if manual URL add UI regresses. Worker remains `sushi-analysis-worker-00003-mfq`.

### Run-All Analysis Duplicate Comment Worker Fix Deploy

- Deployed `sushi-backend` revision `sushi-backend-00032-mc2` from branch `multi-account` at commit `f7af631e9bcfdf8976273ef7ff50db31e3a414ef` plus the approved uncommitted duplicate-comment fix, with 100% traffic.
- Deployed `sushi-analysis-worker` revision `sushi-analysis-worker-00003-mfq` from the same backend image digest, preserving request-triggered Cloud Tasks settings (`min-instances=0` default, `max-instances=1`, `concurrency=1`, `timeout=1800`, private invocation).
- Scope: fixes async Run All Analysis failures caused by global YouTube comment uniqueness and rollback-poisoned SQLAlchemy sessions.
- Verification: alpha automated gates passed (`135 passed, 1 warning`), backend `/health` returned 200, worker authenticated `/health` returned 200, Firebase Hosting returned 200, and recent backend/worker ERROR logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00031-9h4` and worker traffic back to `sushi-analysis-worker-00002-9x6` if batch processing regresses.

### Help Center and URL Button Backend Deploy

- Deployed `sushi-backend` revision `sushi-backend-00031-9h4` from branch `multi-account` at commit `f7af631e9bcfdf8976273ef7ff50db31e3a414ef`, with 100% traffic.
- Scope: refreshed backend-served static/template assets for the Help Center and URL button updates.
- Verification: unit tests passed (`131 passed`), static JS syntax checks passed for `auth.js`, `main.js`, and `queue.js`, backend `/health` returned 200, root page returned 200, and recent backend error logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00030-824` if the Help Center or URL button update regresses.

### Multi-Account Backend and Request-Triggered Worker Deploy

- Deployed `sushi-backend` revision `sushi-backend-00030-824` from branch `multi-account` at base commit `406ce65a261f1f47a44b70de8727e5fa25b638e4` plus the approved uncommitted working tree, with 100% traffic.
- Enabled Cloud Tasks, created the `sushi-analysis-worker` queue in `asia-southeast1`, and configured IAM so the backend runtime service account can enqueue authenticated worker wake tasks.
- Deployed `sushi-analysis-worker` revision `sushi-analysis-worker-00002-9x6` from the same backend image with HTTP drain mode, `min-instances=0`, `max-instances=1`, `concurrency=1`, and `timeout=1800`.
- Verification: unit tests passed (`131 passed`), backend `/health` returned 200, Cloud Tasks worker health task dispatched successfully, and recent backend/worker error logs were empty.
- Rollback impact: route backend traffic back to `sushi-backend-00029-s8h` and worker traffic back to `sushi-analysis-worker-00001-lb6` if the new account isolation or worker wake path regresses.

## Date: 2026-05-13

### Request-Triggered Analysis Worker Plan

- Changed the deployment method for `sushi-analysis-worker` from an always-on polling service to a Cloud Tasks-triggered drain endpoint.
- Planned worker Cloud Run settings are `min-instances=0`, `max-instances=1`, `concurrency=1`, `timeout=1800`, and private invocation through `roles/run.invoker`.
- Added Cloud Tasks queue configuration requirements so `sushi-backend` can wake the worker immediately after creating an analysis batch.
- Verification before production deploy: run unit tests, create/verify the Cloud Tasks queue, deploy the private worker, update backend worker env vars, then create a test analysis batch and confirm queued items drain.
- Rollback impact: redeploy the worker with `ANALYSIS_WORKER_MODE=poll`, `min-instances=1`, `max-instances=1`, and CPU always allocated if the Cloud Tasks wake path fails in production.

## Date: 2026-05-06

### Run-All Analysis Fix

- Updated batch creation so "Run all analysis" includes all project videos in the current video list, not only `APPROVED` videos.
- Added frontend button cleanup so failed batch creation does not leave the button stuck at `Analyzing 0/N`.
- Added a Cloud Run health listener to `app.workers.analysis_batch_worker`.
- Deployed backend revision `sushi-backend-00029-s8h`.
- Deployed worker service `sushi-analysis-worker` revision `sushi-analysis-worker-00001-lb6` with `minScale=1`, `maxScale=1`, and CPU throttling disabled.
- Verified a live VCOPTER batch was created for 11 discovered videos and completed with `9/11` successes. The 2 failures were per-video transcript availability failures where the provider reported no captions and required ASR.

### Supabase Cost-Down Migration

- Exported Cloud SQL database `sushi-d9036-database` to `gs://run-sources-sushi-d9036-asia-southeast1/db-backups/sushi-cloudsql-20260506-143816.sql`.
- Imported the dump into Supabase PostgreSQL after filtering Cloud SQL-only ACL grants for `cloudsqlsuperuser` and `cloudsqlimportexport`.
- Updated Cloud Run revision `sushi-backend-00028-86k` to use the Supabase session pooler `DATABASE_URL`.
- Cleared the Cloud SQL attachment from Cloud Run and reduced Cloud Run limits to `1 CPU`, `1Gi`, `maxScale=2`.
- Verified `/health`, startup logs, and `/monitor-profiles` against the migrated database.
- Stopped the legacy Cloud SQL instance as rollback-only infrastructure.

Verification counts after import:

| Table | Count |
| --- | ---: |
| `monitor_profiles` | 2 |
| `video_candidates` | 42 |
| `analysis_results` | 84 |
| `video_comments` | 1,157 |
| `app_users` | 15 |
| `audit_logs` | 75 |

## Date: 2026-04-24

---

## What Was Deployed

### 1. Cloud SQL Instance
- **Instance ID:** `sushi-d9036-instance`
- **Region:** `asia-southeast1` (Singapore)
- **Connection Name:** `sushi-d9036:asia-southeast1:sushi-d9036-instance`
- **Database:** `sushi-d9036-database`
- **User:** `sushi-d9036-instance` / Password: `REDACTED` (store in Secret Manager only)

### 2. Cloud Run Service
- **Service Name:** `sushi-backend`
- **URL:** `https://sushi-backend-hsh3uwib4a-as.a.run.app`
- **Region:** `asia-southeast1`
- **Status:** ⚠️ Using placeholder image (see Issues below)
- **IAM:** Public access enabled (`allUsers` with `run.invoker`)

### 3. Firebase Hosting
- **Project:** `sushi-d9036`
- **URL:** `https://sushi-d9036.web.app`
- **Config:** Rewrites all paths to Cloud Run service
- **Status:** ✅ Deployed

### 4. Artifact Registry
- **Repository:** `sushi-backend` (Docker format)
- **Image:** `asia-southeast1-docker.pkg.dev/sushi-d9036/sushi-backend/sushi-backend:latest`

---

## Environment Variables Set

| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+psycopg2://APP_USER:***REDACTED***@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE` |
| `GEMINI_API_KEY` | `***REDACTED***` |

### Security Note

- Raw credentials were removed from this document.
- If the previous values were used in production, rotate the DB password and API key immediately.

---

## Issues Found & Blockers

### ❌ Critical Issue: SQLite-Specific SQL on PostgreSQL

**Error:**
```
HINT:  No function matches the given name and argument types. 
[SQL: DELETE FROM alerts WHERE ... datetime(vc.created_at) < datetime(mp.created_at)]
```

**Problem:**
Your app uses SQLite-specific `datetime()` function which doesn't exist in PostgreSQL. This query is in your cleanup/background task logic.

**Files Likely Affected:**
- Any file using `datetime()` in SQL queries
- Look for SQL queries with `datetime(column_name)` pattern

**Fix Required:**
Replace SQLite `datetime(column)` with PostgreSQL equivalent:
- SQLite: `datetime(created_at)`
- PostgreSQL: `created_at::timestamp` or just `created_at` (timestamps are comparable directly)

**Example Fix:**
```python
# BEFORE (SQLite only)
"WHERE datetime(vc.created_at) < datetime(mp.created_at)"

# AFTER (PostgreSQL compatible)  
"WHERE vc.created_at < mp.created_at"
```

---

## What's Working

✅ Cloud SQL instance created and accessible
✅ Database user created with password
✅ Database created
✅ Cloud Run service deployed with Cloud SQL connection
✅ Container builds successfully
✅ Environment variables configured correctly
✅ IAM permissions set for public access
✅ Firebase Hosting deployed and routing to Cloud Run

---

## Current State

The Cloud Run service is currently running a placeholder `gcr.io/cloudrun/hello` image because your app crashes on startup due to the SQLite/PostgreSQL compatibility issue.

Once you fix the SQL compatibility issue and rebuild/redeploy, the app will work.

---

## Next Steps to Complete Deployment

1. **Fix SQLite-specific SQL** in your codebase
2. **Rebuild the image** (Cloud Build will pick up the new code)
3. **Deploy new revision** to Cloud Run

### Quick Fix Commands (after code fix):

```bash
# 1. Build new image
gcloud builds submit --config cloudbuild.yaml .

# OR use the source-based approach again

# 2. Deploy to Cloud Run
gcloud run deploy sushi-backend \
  --source . \
  --region asia-southeast1 \
  --add-cloudsql-instances sushi-d9036:asia-southeast1:sushi-d9036-instance \
  --allow-unauthenticated

# Current production note:
# DATABASE_URL is a Cloud Run environment variable, not a Secret Manager entry.
# Preserve existing env vars on code-only deploys, or update specific keys with
# --update-env-vars when runtime config changes.

# 3. Deploy Firebase (if needed)
firebase deploy --only hosting
```

---

## URLs

| Service | URL |
|---------|-----|
| Cloud Run | https://sushi-backend-hsh3uwib4a-as.a.run.app |
| Firebase Hosting | https://sushi-d9036.web.app |
| Cloud SQL | sushi-d9036:asia-southeast1:sushi-d9036-instance |

---

## Troubleshooting Commands

```bash
# Check Cloud Run service status
gcloud run services describe sushi-backend --region asia-southeast1

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sushi-backend" --limit=50

# Test database connection from Cloud Run (if you need to debug)
# The service account needs Cloud SQL Client role (already has Editor which includes this)

# List revisions
gcloud run revisions list --service=sushi-backend --region=asia-southeast1
```

---

## Infrastructure Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Firebase Hosting                            │
│                     https://sushi-d9036.web.app                     │
│                              │                                      │
│                              ▼                                      │
│                      ┌───────────────┐                              │
│                      │  Cloud Run    │                              │
│                      │ sushi-backend │◄──────────────────────────┐  │
│                      │  (placeholder │                           │  │
│                      │    image)     │                           │  │
│                      └───────┬───────┘                           │  │
│                              │                                   │  │
│                              │ Unix Socket                       │  │
│                              ▼                                   │  │
│         ┌──────────────────────────────────────┐                │  │
│         │      Cloud SQL Proxy (automatic)       │                │  │
│         └──────────────────┬───────────────────┘                │  │
│                            │                                    │  │
│                            ▼                                    │  │
│                   ┌─────────────────┐                        │  │
│                   │  Cloud SQL        │                        │  │
│                   │  sushi-d9036-     │                        │  │
│                   │  instance         │                        │  │
│                   │  (PostgreSQL)     │                        │  │
│                   └─────────────────┘                        │  │
│                                                                 │  │
└─────────────────────────────────────────────────────────────────┘  │
                                                                     │
┌────────────────────────────────────────────────────────────────────┘
│  Your App Container (needs code fix for PostgreSQL compatibility)
│  • Image: asia-southeast1-docker.pkg.dev/sushi-d9036/sushi-backend
│  • Built successfully but crashes due to SQLite-specific SQL
└──────────────────────────────────────────────────────────────────────
```

---

## Deployment Status: ✅ SQL FIX DEPLOYED

- Infrastructure: ✅ Complete
- PostgreSQL Compatibility: ✅ Fixed and deployed
- App Startup: ✅ Successful (Uvicorn running)
- Database Connection: ✅ Connected to Cloud SQL PostgreSQL
- End-to-End: ⚠️ Template rendering issue (separate from SQL fix)

## Fix Applied

**File**: `app/db_migrations.py:148`

**Change**: Added dialect-aware SQL generation:
```python
# Detect dialect inside transaction
dialect_name = connection.dialect.name
if supports_stale_timestamp_check:
    if dialect_name == "sqlite":
        stale_condition = " OR datetime(vc.created_at) < datetime(mp.created_at)"
    else:
        # PostgreSQL and other databases: direct timestamp comparison
        stale_condition = " OR vc.created_at < mp.created_at"
```

## Remaining Issue

**Jinja2 Template Error**: `TypeError: unhashable type: 'dict'` in template cache
- This is a separate issue from the PostgreSQL fix
- The app starts and serves requests but fails on template rendering
- May be related to Jinja2/Starlette version compatibility

---

## Date: 2026-05-15 17:33 CST

- Type: OTA web app release via Cloud Run backend
- Commit: `fe633d41cb98ecfbd50ea8794c8e3a0f79b7ab91`
- Release owner: Cursor agent
- What changed: Discovery completion toast now reports discovered video count and uses the updated shared notification styling/timing.
- Tests: `python3 -m pytest tests/unit/test_monitor_router.py tests/unit/test_auth_watchlist_router.py tests/unit/test_video_router.py tests/unit/test_analysis_service.py tests/unit/test_gemini_client.py` passed; `python3 -m pytest tests/unit -q` passed; `node --check app/static/main.js app/static/queue.js app/static/i18n.js` passed; `git diff --check` passed.
- Cloud Run revision: `sushi-backend-00035-wr9`
- Firebase Hosting: not deployed
- Verification: Cloud Run `/health` passed, revision `sushi-backend-00035-wr9` served 100% traffic, new revision ERROR log scan was clean, public URL returned HTTP 200, and deployed static assets included the new toast/discovery markers.
- Rollback target: `sushi-backend-00034-6c2`
