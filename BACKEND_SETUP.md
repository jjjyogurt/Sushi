# Backend setup

**Document date:** 2026-05-23
**Scope:** Backend runtime, persistence, integrations, and deployment as implemented in this repository.

---

## Summary


| Layer                    | Technology                                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Language**             | Python 3.12 (see `Dockerfile`)                                                                        |
| **Framework**            | FastAPI on Starlette (ASGI)                                                                           |
| **Server**               | Uvicorn                                                                                               |
| **ORM / DB**             | SQLAlchemy 2.x · SQLite locally (`./sushi.db` default) · Supabase PostgreSQL in production (`psycopg2-binary`) |
| **Settings**             | `pydantic-settings` + `.env` (`python-dotenv`)                                                        |
| **Validation / schemas** | Pydantic v2 (`app/schemas/`)                                                                          |
| **HTTP client**          | `httpx`                                                                                               |
| **Async wake queue**     | Google Cloud Tasks wakes the analysis worker on demand                                                |
| **AI**                   | Google Generative AI SDK (`google-generativeai`) — Gemini                                             |
| **YouTube / media**      | `yt-dlp`, external YouTube Transcript API, YouTube Data API for comments/discovery                    |


---

## Repository layout


| Path                   | Role                                                           |
| ---------------------- | -------------------------------------------------------------- |
| `app/main.py`          | FastAPI app, static mount, routers, startup DB init/migrations |
| `app/api/`             | HTTP routers                                                   |
| `app/services/`        | Business logic                                                 |
| `app/repositories/`    | DB access                                                      |
| `app/models/`          | SQLAlchemy models                                              |
| `app/schemas/`         | Request/response models                                        |
| `app/db.py`            | Engine singleton, retries, session generator                   |
| `app/db_migrations.py` | Imperative migrations (PostgreSQL-aware where noted)           |
| `app/config.py`        | Environment-backed `Settings`                                  |
| `requirements.txt`     | Locked Python dependencies                                     |
| `Dockerfile`           | Production-style container (`uvicorn` on `$PORT`)              |
| `tests/unit/`          | `pytest` + in-memory SQLite                                    |


---

## Runtime

- **Entry:** `uvicorn app.main:app` (locally `--reload`; Docker/cmd uses `--host 0.0.0.0`).
- **Async worker:** Production runs `sushi-analysis-worker` with `python -m app.workers.analysis_batch_worker`. The backend enqueues a Cloud Task after creating either an analysis batch or a project insights refresh job, and the worker drains queued work through `POST /internal/analysis-worker/drain`. The worker scales to zero when idle.
- **App identity:** `FastAPI(title="Influencer Video Intelligence", version="0.1.0")` in `app/main.py`.
- **Startup:** After DB connection (with retries for managed databases), SQLAlchemy `Base.metadata.create_all` runs, then helpers in `app/db_migrations.py`.

---

## Persistence

- **Engine:** `sqlalchemy.create_engine` from `DATABASE_URL`.
- **Sessions:** Request-scoped `Session` via `get_db_session()` (`sessionmaker`, `autocommit=False`).
- **Local SQLite:** Local development and tests may use `DATABASE_URL=sqlite:///./sushi.db` or in-memory SQLite fixtures. This is local-only and must not be deployed as the Cloud Run production database.
- **Production Supabase PostgreSQL:** Cloud Run backend and worker must use the Supabase session pooler DSN. Current Supabase project ref is `uzqsrsdpfxykujbjjsqu`, region is `ap-southeast-2`, and the pooler host is `aws-1-ap-southeast-2.pooler.supabase.com`.
- **SQLite handling:** `check_same_thread=False` when URL starts with `sqlite`.
- **PostgreSQL handling:** `pool_pre_ping=True`; connection retries in `get_db_engine()` help managed Postgres / cold starts.
- **Schema evolution:** `create_all` + imperative migrations in code (no Alembic in dependencies).

Current durable async tables:

- `analysis_batches` and `analysis_batch_items`: created by `/analysis/batches` for the “Run all analysis” workflow. Items are claimed by the worker and processed with `AnalysisService.analyze_video()`.
- `project_insight_jobs`: created by project insights refresh. One active job (`queued` or `running`) is allowed per project, while different projects can refresh concurrently. Completed jobs link to the generated `project_insight_reports.id`.

---

## Configuration

Centralized in `app/config.py` (`Settings`). Notable categories:

- **Environment:** `ENVIRONMENT`, `DATABASE_URL`, cookie/security flags (`SECURE_COOKIES`, `AUTH_*`).
- **Gemini:** `GEMINI_API_KEY`, `GEMINI_MODEL_ANALYSIS`, `GEMINI_MODEL_CHAT`, analysis/chat limits.
- **YouTube / transcripts:** transcript API (`YOUTUBE_TRANSCRIPT_*`), Data API (`YOUTUBE_DATA_API_KEY`), comment pagination limits (`YOUTUBE_COMMENTS_*`).
- **Analysis worker wake tasks:** `GCP_PROJECT_ID`, `GCP_REGION`, `ANALYSIS_WORKER_URL`, `ANALYSIS_WORKER_TASKS_QUEUE`, `ANALYSIS_WORKER_TASK_SERVICE_ACCOUNT_EMAIL`, `ANALYSIS_WORKER_DRAIN_*`, optional `ANALYSIS_WORKER_INTERNAL_TOKEN`.
- **VOC thresholds:** `VOC_FAILED_RATIO_*`, `VOC_CONFIDENCE_*`.

See `.env.example` for names and sane defaults.

### Local vs production database requirement

`.env` is allowed to use SQLite for local testing:

```text
DATABASE_URL=sqlite:///./sushi.db
```

Cloud Run production is different. The backend and analysis worker must both use the Supabase session pooler:

```text
postgresql+psycopg2://postgres.PROJECT_REF:PASSWORD@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require
```

Do not deploy local `.env` directly to Cloud Run if it contains the SQLite `DATABASE_URL`. Doing so creates a container-local database and the app will appear to have no existing Supabase data. For Cloud Run deploys, preserve the existing production `DATABASE_URL` or inject the Supabase DSN separately from local `.env`.

---

## HTTP API surface

Routers are registered from `app/main.py`, including:

- Health, authentication, monitors, videos, chat, incidents, agent settings, knowledge, VOC, watchlist.
- Async analysis batches (`/analysis/batches` create/status/items/cancel).
- Project insights reports and async refresh jobs:
  - `GET /monitor-profiles/{id}/insights/current`
  - `GET /monitor-profiles/{id}/insights/history`
  - `POST /monitor-profiles/{id}/insights/refresh`
  - `GET /monitor-profiles/{id}/insights/jobs/active`
  - `GET /monitor-profiles/{id}/insights/jobs/{job_id}`
- Project, video, analysis, batch, knowledge, chat, incident, alert, watchlist, and agent settings APIs are authenticated and scoped to the current account. Account-wide list/batch requests mean “all projects owned by the current user,” not global database access.

**Multipart uploads:** `python-multipart` where file uploads apply.

**Agent settings:** Runtime analysis instructions are stored per user in the `agent_settings` database table. The root `AGENTS.md` is not shared product settings.

### Video analysis pipeline

1. A project owns `video_candidates`.
2. Single-video analysis runs through `POST /videos/{id}/analyze`.
3. Batch analysis creates `analysis_batches` plus `analysis_batch_items`.
4. The backend enqueues a Cloud Task to wake `sushi-analysis-worker`.
5. The worker claims queued batch items, fetches transcript/comments, calls Gemini, and writes `analysis_results`.
6. Analysis reads the current owner’s DB-backed agent settings, so the same video in another account/project can have a separate analysis cache row.
7. Completed analysis rows store transcript text in `analysis_results.transcript_text`; project insights and chat read from that stored transcript instead of fetching transcripts again.

### Project insights pipeline

1. The user clicks `Refresh Report` in a selected project.
2. `POST /monitor-profiles/{id}/insights/refresh` creates or returns the project’s active `project_insight_jobs` row. It does not return a finished report.
3. The frontend disables only that project’s refresh button and polls `/insights/jobs/active` plus `/insights/jobs/{job_id}`.
4. The backend enqueues a Cloud Task for the shared worker drain endpoint. In local/dev, the backend can fall back to processing after the HTTP response when Cloud Tasks is not configured.
5. The worker claims queued insight jobs before normal analysis batch items.
6. The job aggregates the latest completed transcript-backed analysis rows, calls Gemini for executive synthesis, writes `project_insight_reports`, then marks the job `completed` with `report_id`.
7. Same-project double clicks return the same active job. Different projects can refresh concurrently, including across users, because the active-job guard is scoped to `monitor_profile_id`.

Operational note: Gemini provider calls currently determine the long tail for insight generation. A normal small/medium refresh should finish in seconds to a few minutes, but a provider/network hang can leave jobs `running` until timeout or recovery behavior handles them. If the UI stays on `Generating...`, inspect `project_insight_jobs.status`, `last_error`, and worker logs first.

---

## GCP deployment (documented pattern)

Deployments are described in `DEPLOY_LOG.md` and implied by `firebase.json` and `.env.example`.


| Piece                           | Typical setup                                                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Cloud Run**                   | Service name `sushi-backend`, free-tier pilot region `us-central1`, listens on `PORT` (8080).                                        |
| **Cloud Run worker**            | Service name `sushi-analysis-worker`, command `python -m app.workers.analysis_batch_worker`, drains both analysis batch items and project insight jobs, request-triggered with `min-instances=0`, `max-instances=1`, `concurrency=1`. |
| **Cloud Tasks**                 | Queue `sushi-analysis-worker` in `us-central1`; backend enqueues drain tasks for analysis batches and insights refresh jobs, and the queue invokes the private worker service.         |
| **Supabase PostgreSQL**         | Production database accessed through the Supabase session pooler.                                                                     |
| `DATABASE_URL` on Cloud Run     | Must use Supabase TCP/TLS DSN via `postgresql+psycopg2://postgres.PROJECT_REF:PASSWORD@HOST:5432/postgres?sslmode=require`; never local SQLite. |
| **Artifact Registry**           | Docker image builds created by Cloud Run source deploys.                                                                              |
| **Firebase Hosting**            | Not used for the free-tier pilot. Use the Cloud Run service URL directly.                                                             |
| **IAM**                         | Unauthenticated hosting often uses `allUsers` with `roles/run.invoker` on Cloud Run (document only; confirm in GCP console).          |


**Build/deploy commands** (adapt project/region/instance):

- `gcloud builds submit ...` or `gcloud run deploy sushi-backend --source ...` with `--clear-cloudsql-instances`, `--set-env-vars`, `--allow-unauthenticated` as needed.
- `gcloud tasks queues create sushi-analysis-worker --location us-central1` once per environment, then grant the backend runtime service account `roles/cloudtasks.enqueuer`.
- `gcloud run deploy sushi-analysis-worker ... --min-instances 0 --max-instances 1 --concurrency 1 --timeout 1800 --no-allow-unauthenticated`.
- Do not deploy Firebase for the free-tier pilot.

Store secrets (API keys, DB passwords) in **Secret Manager** or Cloud Run secrets — not in markdown or git.

Before considering a Cloud Run deploy healthy, verify both services point to Supabase:

```bash
gcloud run services describe sushi-backend --region us-central1 --format=json
gcloud run services describe sushi-analysis-worker --region us-central1 --format=json
```

Inspect only the `DATABASE_URL` host/ref, not the password. It must contain the Supabase pooler host, not `sqlite:///./sushi.db`.

If a release changes analysis batch processing, project insight refresh, Gemini client behavior, or any worker-drained job, deploy and verify both `sushi-backend` and `sushi-analysis-worker` from the same code revision. Deploying only the backend can leave new queued job rows unprocessed by an older worker.

---

## Testing

- **Runner:** `pytest` under `tests/unit/`.
- **DB fixtures:** In-memory SQLite in `tests/unit/conftest.py` for many tests.

---

## Documentation governance

Backend runtime, deployment, integration, or environment-variable changes must update this file in the same change set.

Database structure, migration, persistence behavior, production database target, transcript/analysis storage, or JSON contract changes must update `DATABASE_DESIGN.md` in the same change set with a dated **What Changed** note.

### What Changed (2026-05-11, setup documentation alignment)

- What changed: Updated this setup document date, fixed Cloud Run table formatting, and clarified the documentation update rule for backend and database changes.
- Why it changed: Keep the setup document aligned with the current Supabase-backed backend design and make future documentation updates mandatory when backend or database behavior changes.
- Impact on existing data and compatibility: Documentation-only. No runtime, API, schema, or persisted data behavior changed.

### What Changed (2026-05-23, async project insights jobs)

- What changed: Documented `project_insight_jobs`, the async project insights refresh API contract, frontend job polling, and the shared worker drain behavior for both analysis batch items and project insight jobs.
- Why it changed: Project insights refresh is now durable and project-scoped instead of a synchronous report-generation request. The docs must make clear that same-project duplicate clicks reuse one job while different projects can refresh concurrently.
- Impact on existing data and compatibility: Documentation-only. Runtime schema is covered in `DATABASE_DESIGN.md`; deployment must keep backend and worker revisions aligned when changing insight refresh behavior.

### What Changed (2026-05-18, free-tier US pilot deployment)

- What changed: Documented the free-tier pilot backend target as project `sushi-free-us-20260518` in `us-central1`, with direct Cloud Run access and a request-triggered analysis worker that scales to zero when idle. Gemini runtime model settings are `gemini-3.1-flash-lite` for both analysis and chat.
- Why it changed: Keep backend and analysis worker deployment in a US Cloud Run region with free-tier-friendly behavior and avoid Firebase for pilot testing.
- Impact on existing data and compatibility: Supabase remains the production database. No schema migration, persisted data rewrite, or API contract change is required.

### What Changed (2026-05-18, local SQLite vs production Supabase rule)

- What changed: Added explicit local and production database requirements. Local `.env` may use SQLite, but Cloud Run backend and worker must use the Supabase session pooler DSN for project ref `uzqsrsdpfxykujbjjsqu`.
- Why it changed: Prevent Cloud Run deployments from accidentally using local SQLite and hiding existing Supabase data.
- Impact on existing data and compatibility: Documentation-only. No schema migration or data rewrite is required.

### What Changed (2026-05-13, request-triggered analysis worker)

- What changed: The analysis worker is now documented as a Cloud Tasks-triggered Cloud Run service that drains queued batch items on request and scales to zero when idle.
- Why it changed: The previous always-on worker incurred idle Cloud Run cost even when no internal users were running analyses.
- Impact on existing data and compatibility: Analysis batch tables and API responses are unchanged. New runtime configuration is required in production before disabling the always-on polling deployment.

### What Changed (2026-05-11, account-scoped backend APIs)

- What changed: Documented authenticated account scoping for project/video-related APIs and clarified that agent settings are DB-backed per user.
- Why it changed: Backend behavior now isolates projects, videos, derived analysis, and settings by account.
- Impact on existing data and compatibility: Operationally, callers must be authenticated before using project/video APIs. Legacy projects are backfilled to `Sushi_1` by startup migration.

---

## Related documents


| File                            | Contents                                        |
| ------------------------------- | ----------------------------------------------- |
| `LOCAL_SETUP.md`                | Local venv and run instructions                 |
| `DEPLOY_LOG.md`                 | Historical deployment notes and troubleshooting |
| `PRDs/TECH_STACK_2026-04-01.md` | Broader stack write-up                          |


---

## Dependency list (`requirements.txt`)

`fastapi`, `starlette`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `pydantic-settings`, `python-dotenv`, `google-generativeai`, `google-cloud-tasks`, `youtube-search-python`, `yt-dlp`, `pytest`, `httpx`, `jinja2`, `python-multipart`
