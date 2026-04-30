# OTA Web App Deployment Playbook

This is the canonical over-the-air (OTA) release playbook for shipping web app changes to production.

In this repository, the public web app is served through Firebase Hosting and rewritten to the Cloud Run backend. That means most web app OTA releases are Cloud Run releases, not Firebase Hosting releases. Use this playbook to decide what to deploy, what must be tested, and how to verify or roll back.

For the exact Cloud Run backend deploy command, environment rules, and rollback commands, refer to `BACKEND_DEPLOYMENT.md`.

---

## 1) What OTA means in this repo

OTA means users receive the latest web app behavior without installing anything. The production path is:

1. User opens Firebase Hosting URL.
2. Firebase Hosting rewrites requests to the Cloud Run service.
3. Cloud Run serves the app/API behavior for the deployed revision.

Current production targets are defined in `BACKEND_DEPLOYMENT.md`:

- Firebase Hosting project: `sushi-d9036`
- Cloud Run service: `sushi-backend`
- Cloud Run region: `asia-southeast1`
- GCP project: `sushi-d9036`

---

## 2) Deployment decision tree

Use this before every OTA release.

### Deploy Cloud Run

Deploy Cloud Run when any of these changed:

- Python backend code under `app/`
- Static assets served by the backend, such as `app/static/`
- Templates or server-rendered web UI
- API behavior, schemas, services, repositories, or auth
- Runtime dependencies, environment-dependent behavior, or migrations
- Anything that changes the behavior users see through the web app rewrite

Follow `BACKEND_DEPLOYMENT.md` for the deploy command and rollback procedure.

### Deploy Firebase Hosting

Deploy Firebase Hosting only when any of these changed:

- `firebase.json`
- `.firebaserc`
- Files under `public/`
- Hosting rewrite behavior

Command:

```bash
firebase deploy --only hosting
```

If both Cloud Run code and Hosting config changed, deploy Cloud Run first, verify it, then deploy Hosting and verify the public URL.

---

## 3) OTA release gates

These gates are mandatory. Do not deploy if any blocking gate fails.

### Gate A - Environment and target

Confirm the intended production target before running deploy commands:

```bash
gcloud config get-value project
firebase use
```

Expected:

- `gcloud` project: `sushi-d9036`
- Firebase project: `sushi-d9036`

If the target is wrong, stop and switch only after confirming the environment change.

### Gate B - Source control

Deploy only from the intended branch and commit:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

Rules:

- Prefer deploying a committed SHA, not an uncommitted working tree.
- Do not deploy if unrelated local changes are present.
- Record the deployed commit SHA in `DEPLOY_LOG.md`.
- Do not paste secrets, env var values, or credentials into logs or docs.

### Gate C - Tests and test matrix must pass

OTA must pass tests before deployment. The release test matrix, or TestM, is tracked in `ALPHA_RELEASE_TEST_CASES.md`.

Minimum blocking test command:

```bash
python3 -m pytest tests/unit -q
```

For alpha or user-facing workflow releases, also run the P0 TestM gate from `ALPHA_RELEASE_TEST_CASES.md`:

```bash
python3 -m pytest \
  tests/unit/test_monitor_router.py \
  tests/unit/test_auth_watchlist_router.py \
  tests/unit/test_video_router.py \
  tests/unit/test_analysis_service.py \
  tests/unit/test_gemini_client.py
```

If tests fail, stop. Fix the failure, rerun the relevant suite, and only deploy after the suite is green.

### Gate D - Risk review

Before OTA, identify the release risk:

- Low risk: copy-only, styling-only, or isolated UI behavior with no data writes
- Medium risk: API response changes, auth-adjacent UI, queue/watchlist behavior, or provider error handling
- High risk: auth/session changes, database writes, migrations, background jobs, billing/cost behavior, or production config changes

High-risk releases need a clear rollback owner and a known-good revision before deploy.

---

## 4) Standard OTA procedure

Run all commands from repo root.

### Step A - Preflight

```bash
gcloud auth login
gcloud config set project sushi-d9036
firebase use sushi-d9036

git status --short
git branch --show-current
git rev-parse HEAD

python3 -m pytest tests/unit -q
```

If this is an alpha/user-facing workflow release, run the `ALPHA_RELEASE_TEST_CASES.md` P0 command too.

### Step B - Deploy Cloud Run

Use the canonical command in `BACKEND_DEPLOYMENT.md`:

```bash
gcloud run deploy sushi-backend \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --add-cloudsql-instances sushi-d9036:asia-southeast1:sushi-d9036-instance
```

For code-only OTA releases, preserve the existing Cloud Run environment variables. If runtime config must change, follow the runtime config guidance in `BACKEND_DEPLOYMENT.md`.

### Step C - Deploy Firebase Hosting only if needed

Only run this when Hosting config or `public/` changed:

```bash
firebase deploy --only hosting
```

### Step D - Verify production

Resolve and check the Cloud Run service:

```bash
SERVICE_URL="$(gcloud run services describe sushi-backend --region asia-southeast1 --format='value(status.url)')"
echo "$SERVICE_URL"
curl -fsS "$SERVICE_URL/health"
gcloud run revisions list --service=sushi-backend --region=asia-southeast1
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sushi-backend" --limit=100
```

Then verify the public web URL:

```bash
curl -I https://sushi-d9036.web.app
```

Manual smoke test the changed user path in a browser. For user-facing releases, cover at least:

- Login/session state
- Dashboard load
- Changed workflow
- API-backed state update, if applicable
- Locale switch, if the changed area has translated copy

---

## 5) Rollback

Use the rollback procedure in `BACKEND_DEPLOYMENT.md`.

Fast rollback shape:

```bash
gcloud run revisions list --service=sushi-backend --region=asia-southeast1

gcloud run services update-traffic sushi-backend \
  --region asia-southeast1 \
  --to-revisions <STABLE_REVISION>=100

SERVICE_URL="$(gcloud run services describe sushi-backend --region asia-southeast1 --format='value(status.url)')"
curl -fsS "$SERVICE_URL/health"
```

Rollback immediately if:

- `/health` fails
- Production logs show startup/runtime errors
- Auth or core workflows are broken
- Data writes are failing or corrupting user-visible state
- The public URL cannot reach the app

If Firebase Hosting caused the incident, roll back Hosting from the Firebase console or redeploy the last known-good Hosting config.

---

## 6) Post-release record

Add a short entry to `DEPLOY_LOG.md` after every OTA release:

- Date/time
- Deployed commit SHA
- Release owner
- What changed
- Test commands run and result
- Cloud Run revision deployed
- Whether Firebase Hosting was deployed
- Verification result
- Rollback revision, if applicable

Example:

```markdown
## Date: YYYY-MM-DD HH:mm TZ

- Type: OTA web app release
- Commit: `<SHA>`
- Tests: `python3 -m pytest tests/unit -q` passed
- Cloud Run revision: `<REVISION>`
- Firebase Hosting: not deployed
- Verification: `/health` passed, public URL smoke test passed
- Rollback target: `<PREVIOUS_STABLE_REVISION>`
```

---

## 7) No-go conditions

Do not OTA deploy when:

- Tests are failing or were skipped.
- You are not sure which project or branch is targeted.
- The working tree has unrelated changes.
- Required secrets or env vars are unknown.
- A migration or database structure change lacks the required design documentation update.
- There is no rollback target for a high-risk release.

When in doubt, hold the release and verify the target, test status, and rollback plan first.
