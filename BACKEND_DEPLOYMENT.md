# Backend Deployment Runbook

This is the canonical backend deployment instruction for this repository.

For web app OTA release gates, deployment decision rules, and post-release records, read `OTA_DEPLOYMENT.md` before deploying.

If deployment method changes, update this file in the same PR before deploying.

---

## 1) Current production targets

- Primary free-tier pilot GCP project: `sushi-free-us-20260518`
- Legacy GCP project: `sushi-d9036`
- Cloud Run service: `sushi-backend`
- Cloud Run worker service: `sushi-analysis-worker`
- Cloud Run region: `us-central1`
- Production database: Supabase PostgreSQL session pooler (`aws-1-ap-southeast-2.pooler.supabase.com`)
- Legacy Cloud SQL rollback instance: `sushi-d9036:asia-southeast1:sushi-d9036-instance` (stopped after 2026-05-06 migration)
- Firebase Hosting: not used for the free-tier pilot deployment. Use the Cloud Run service URL directly.

---

## 2) Safety rules (do not skip)

1. Deploy only from the intended branch/commit.
2. Do not put secrets in command history, docs, or source files.
3. Do not put Supabase database passwords in markdown, git, or shell history.
4. Treat `.env` as local development configuration unless each production value has been explicitly reviewed.
5. Never deploy Cloud Run production directly from local `.env` when it contains `DATABASE_URL=sqlite:///./sushi.db`.
6. Production Cloud Run backend and worker must use the Supabase session pooler `DATABASE_URL`.
7. Run tests before deploy.
8. Verify health immediately after deploy.
9. If verification fails, rollback traffic to previous stable revision.

---

## 3) Required runtime config

### Database configuration rule

Local development and production intentionally use different database targets:

| Environment | Required `DATABASE_URL` | Purpose |
| --- | --- | --- |
| Local development / unit testing | `sqlite:///./sushi.db` or in-memory SQLite fixtures | Fast local testing without touching production data |
| Cloud Run production / pilot | Supabase PostgreSQL session pooler DSN | Existing shared production data |

Current Cloud Run production stores the Supabase PostgreSQL DSN as a Cloud Run environment variable:

- `DATABASE_URL`

Preserve the existing value during code-only deploys. If runtime config must change, update it directly as a Cloud Run env var or move it to Secret Manager first. The expected production shape uses Supabase project ref `uzqsrsdpfxykujbjjsqu` and the session pooler host:

```text
postgresql+psycopg2://postgres.PROJECT_REF:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require
```

Do not use `.env` as a Cloud Run env-var source unless the production Supabase `DATABASE_URL` is injected or preserved separately. If `.env` has `DATABASE_URL=sqlite:///./sushi.db`, deploying it to Cloud Run will create a separate container-local SQLite database and the app will not show existing Supabase data.

Before and after deployment, verify Cloud Run is wired to Supabase without printing the password:

```bash
gcloud run services describe sushi-backend \
  --region us-central1 \
  --format=json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); env=d["spec"]["template"]["spec"]["containers"][0].get("env", []); v=next((e.get("value","") for e in env if e.get("name")=="DATABASE_URL"), ""); print("postgresql", v.startswith("postgresql+psycopg2://"), "host", v.split("@")[-1] if "@" in v else "<missing>")'
```

Do not attach Cloud SQL for normal deploys. The previous Cloud SQL instance is retained only as a short-term rollback source after the 2026-05-06 Supabase migration.

Other sensitive values may be plain env vars or Secret Manager-backed depending on the current service configuration:

- `GEMINI_API_KEY`
- `YOUTUBE_TRANSCRIPT_API_KEY`
- `YOUTUBE_DATA_API_KEY`
- `ANALYSIS_WORKER_INTERNAL_TOKEN` (optional defense-in-depth header shared by Cloud Tasks and the worker)

Expected non-secret runtime env:

- `ENVIRONMENT=production`
- `ENABLE_MOCK_DISCOVERY=false`
- `GEMINI_MODEL_ANALYSIS=gemini-3.1-flash-lite`
- `GEMINI_MODEL_CHAT=gemini-3.1-flash-lite`
- `GCP_PROJECT_ID=sushi-free-us-20260518`
- `GCP_REGION=us-central1`
- `ANALYSIS_WORKER_URL=<sushi-analysis-worker Cloud Run URL>`
- `ANALYSIS_WORKER_TASKS_QUEUE=sushi-analysis-worker`
- `ANALYSIS_WORKER_TASK_SERVICE_ACCOUNT_EMAIL=<task invoker service account email>`
- `ANALYSIS_WORKER_DRAIN_PATH=/internal/analysis-worker/drain`
- `ANALYSIS_WORKER_DISPATCH_DEADLINE_SECONDS=1800`
- `ANALYSIS_WORKER_DRAIN_MAX_SECONDS=1200`

---

## 4) Standard deployment steps

Run all commands from repo root.

### Step A - Preflight checks

```bash
# 1) Authenticate and target project
gcloud auth login
gcloud config set project sushi-free-us-20260518

# 2) Run backend unit tests
python3 -m pytest tests/unit -q
```

If tests fail, stop and fix first.

### Step B - Deploy backend to Cloud Run

```bash
gcloud run deploy sushi-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --clear-cloudsql-instances
```

For code-only deploys, preserve the service's existing env vars. If runtime config must change, update only the specific keys with `--update-env-vars`; do not replace `DATABASE_URL` unless the Supabase connection string has first been verified.

Do not pass `--env-vars-file .env` to production deploys while `.env` is configured for local SQLite. If an env vars file is used, build a production-only file that contains the Supabase `DATABASE_URL`, or preserve the existing Cloud Run `DATABASE_URL` and update only non-database keys.

### Step C - Post-deploy verification

```bash
# 1) Resolve service URL
SERVICE_URL="$(gcloud run services describe sushi-backend --region us-central1 --format='value(status.url)')"
echo "$SERVICE_URL"

# 2) Health check
curl -fsS "$SERVICE_URL/health"

# 3) Verify latest revision + traffic
gcloud run revisions list --service=sushi-backend --region=us-central1

# 4) Quick log scan for startup/runtime errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sushi-backend" --limit=100
```

If health check fails or logs show critical runtime errors, rollback immediately.

### Step D - Firebase Hosting

Do not deploy Firebase Hosting for the free-tier pilot. Use the Cloud Run URL directly.

### Step E - Configure analysis worker wake queue

The async "Run all analysis" flow is request-triggered. The backend creates the durable database batch and enqueues a Cloud Task that wakes the private worker drain endpoint.

Create the queue once per region:

```bash
gcloud services enable cloudtasks.googleapis.com

gcloud tasks queues create sushi-analysis-worker \
  --location us-central1 \
  --max-dispatches-per-second 1 \
  --max-concurrent-dispatches 1
```

Use a dedicated service account for Cloud Tasks to invoke the worker:

```bash
gcloud iam service-accounts create sushi-analysis-worker-invoker \
  --display-name "Sushi analysis worker invoker"

gcloud run services add-iam-policy-binding sushi-analysis-worker \
  --region us-central1 \
  --member serviceAccount:sushi-analysis-worker-invoker@sushi-free-us-20260518.iam.gserviceaccount.com \
  --role roles/run.invoker
```

For the backend service account that enqueues tasks, grant queue enqueue permissions:

```bash
gcloud projects add-iam-policy-binding sushi-free-us-20260518 \
  --member serviceAccount:<BACKEND_RUNTIME_SERVICE_ACCOUNT> \
  --role roles/cloudtasks.enqueuer

gcloud iam service-accounts add-iam-policy-binding \
  sushi-analysis-worker-invoker@sushi-free-us-20260518.iam.gserviceaccount.com \
  --member serviceAccount:<BACKEND_RUNTIME_SERVICE_ACCOUNT> \
  --role roles/iam.serviceAccountTokenCreator
```

### Step F - Deploy analysis worker after batch/analysis changes

Deploy the worker from the same backend image or source revision and override the command. The worker now exposes an HTTP drain endpoint and scales to zero when idle:

```bash
gcloud run deploy sushi-analysis-worker \
  --image IMAGE_FROM_LATEST_BACKEND_REVISION \
  --platform managed \
  --region us-central1 \
  --command python \
  --args=-m,app.workers.analysis_batch_worker \
  --clear-cloudsql-instances \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 1 \
  --timeout 1800 \
  --no-allow-unauthenticated
```

The worker uses the same runtime env vars as `sushi-backend`, including `DATABASE_URL`, Gemini keys, YouTube transcript keys, YouTube Data API keys, and optional `ANALYSIS_WORKER_INTERNAL_TOKEN`. Do not set `--no-cpu-throttling`; the worker does useful work only while Cloud Tasks is calling the drain endpoint.

The worker must use the same Supabase `DATABASE_URL` as the backend. If the backend points to Supabase but the worker points to local SQLite, async analysis will not read or update the existing production rows.

After the worker is deployed, update `sushi-backend` with the worker task settings, especially `ANALYSIS_WORKER_URL` and `ANALYSIS_WORKER_TASK_SERVICE_ACCOUNT_EMAIL`.

Optional fallback: add a Cloud Scheduler job every 5-10 minutes to enqueue or call the same drain endpoint so missed task creation events do not leave queued work idle.

---

## 5) Rollback procedure

### Step A - Identify last stable revision

```bash
gcloud run revisions list --service=sushi-backend --region=us-central1
```

### Step B - Route all traffic to stable revision

Replace `<STABLE_REVISION>` with the actual known-good revision.

```bash
gcloud run services update-traffic sushi-backend \
  --region us-central1 \
  --to-revisions <STABLE_REVISION>=100
```

### Step C - Re-verify

```bash
SERVICE_URL="$(gcloud run services describe sushi-backend --region us-central1 --format='value(status.url)')"
curl -fsS "$SERVICE_URL/health"
```

---

## 6) Change management for this runbook

Whenever deployment method changes, update this file in the same PR/release:

- Service name, project id, region, Cloud SQL connection name
- Required env vars and secrets
- Deploy command flags
- Verification checks
- Rollback command

Also add a short note in `DEPLOY_LOG.md`:

- Date/time
- What changed in deployment method
- Why it changed
- Verification result
- Rollback impact (if used)

---

## 7) Known current method decisions

- Source-based Cloud Run deploy (`gcloud run deploy --source .`) is the active method.
- No `scripts/deploy_backend_dual_region.sh` script is currently part of this repo workflow.
- Web app OTA releases are governed by `OTA_DEPLOYMENT.md`; Cloud Run remains the deploy path. Firebase Hosting is not part of the free-tier pilot path.
- The analysis worker must remain request-triggered with `min-instances=0` so it scales to zero when idle.
- Current free-tier pilot uses `gemini-3.1-flash-lite` for both analysis and chat.

### What Changed (2026-05-18, free-tier US pilot deployment)

- What changed: Updated the deployment target from the legacy `sushi-d9036` / `asia-southeast1` Firebase-routed setup to the free-tier pilot project `sushi-free-us-20260518` in `us-central1`, using direct Cloud Run URLs and a scale-to-zero analysis worker.
- Why it changed: Keep backend and worker runtime in a US Cloud Run region with free-tier-friendly settings and avoid Firebase for the pilot.
- Impact on existing data and compatibility: Supabase remains the production database. No database schema, API contract, or Firebase config change is required.

### What Changed (2026-05-18, local SQLite vs production Supabase rule)

- What changed: Added explicit deployment rules that `.env` may remain local SQLite, but Cloud Run backend and worker must use the Supabase session pooler `DATABASE_URL`.
- Why it changed: Prevent future production deploys from accidentally using the local SQLite default and hiding existing Supabase data.
- Impact on existing data and compatibility: Documentation-only. The deployed backend and worker already point to Supabase; no schema or data migration is required.
