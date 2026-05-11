# Deployment Log - Sushi App to Firebase + Cloud Run

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
