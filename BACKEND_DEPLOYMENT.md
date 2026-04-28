# Backend Deployment Runbook

This is the canonical backend deployment instruction for this repository.

If deployment method changes, update this file in the same PR before deploying.

---

## 1) Current production targets

- GCP project: `sushi-d9036`
- Cloud Run service: `sushi-backend`
- Cloud Run region: `asia-southeast1`
- Cloud SQL instance connection: `sushi-d9036:asia-southeast1:sushi-d9036-instance`
- Firebase Hosting project: `sushi-d9036` (rewrites to `sushi-backend`)

---

## 2) Safety rules (do not skip)

1. Deploy only from the intended branch/commit.
2. Do not put secrets in command history, docs, or source files.
3. Do not use `--set-secrets DATABASE_URL=DATABASE_URL:latest`; that Secret Manager entry is not available in current production.
4. Run tests before deploy.
5. Verify health immediately after deploy.
6. If verification fails, rollback traffic to previous stable revision.

---

## 3) Required runtime config

Current production stores the Cloud SQL DSN as a plain Cloud Run environment variable:

- `DATABASE_URL`

This is acceptable for current deployments. Preserve the existing value during code-only deploys, or update it directly as a Cloud Run env var when the DB user/password/name changes. The expected production shape is:

```text
postgresql+psycopg2://APP_USER:PASSWORD@/sushi-d9036-database?host=/cloudsql/sushi-d9036:asia-southeast1:sushi-d9036-instance
```

Other sensitive values may be plain env vars or Secret Manager-backed depending on the current service configuration:

- `GEMINI_API_KEY`
- `YOUTUBE_TRANSCRIPT_API_KEY`
- `YOUTUBE_DATA_API_KEY`

Expected non-secret runtime env:

- `ENVIRONMENT=production`
- `ENABLE_MOCK_DISCOVERY=false`
- `GEMINI_MODEL_ANALYSIS=gemini-3-flash`
- `GEMINI_MODEL_CHAT=gemini-3-flash`

---

## 4) Standard deployment steps

Run all commands from repo root.

### Step A - Preflight checks

```bash
# 1) Authenticate and target project
gcloud auth login
gcloud config set project sushi-d9036

# 2) Optional but recommended: confirm firebase target project
firebase use sushi-d9036

# 3) Run backend unit tests
python3 -m pytest tests/unit -q
```

If tests fail, stop and fix first.

### Step B - Deploy backend to Cloud Run

```bash
gcloud run deploy sushi-backend \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --add-cloudsql-instances sushi-d9036:asia-southeast1:sushi-d9036-instance
```

For code-only deploys, preserve the service's existing env vars. If runtime config must change, update only the specific keys with `--update-env-vars`; do not replace `DATABASE_URL` with a Secret Manager reference unless that secret has first been created and verified.

### Step C - Post-deploy verification

```bash
# 1) Resolve service URL
SERVICE_URL="$(gcloud run services describe sushi-backend --region asia-southeast1 --format='value(status.url)')"
echo "$SERVICE_URL"

# 2) Health check
curl -fsS "$SERVICE_URL/health"

# 3) Verify latest revision + traffic
gcloud run revisions list --service=sushi-backend --region=asia-southeast1

# 4) Quick log scan for startup/runtime errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sushi-backend" --limit=100
```

If health check fails or logs show critical runtime errors, rollback immediately.

### Step D - Deploy Firebase Hosting (only when needed)

Only run when `firebase.json` or `public/` changed.

```bash
firebase deploy --only hosting
```

---

## 5) Rollback procedure

### Step A - Identify last stable revision

```bash
gcloud run revisions list --service=sushi-backend --region=asia-southeast1
```

### Step B - Route all traffic to stable revision

Replace `<STABLE_REVISION>` with the actual known-good revision.

```bash
gcloud run services update-traffic sushi-backend \
  --region asia-southeast1 \
  --to-revisions <STABLE_REVISION>=100
```

### Step C - Re-verify

```bash
SERVICE_URL="$(gcloud run services describe sushi-backend --region asia-southeast1 --format='value(status.url)')"
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

