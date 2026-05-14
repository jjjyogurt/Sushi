# Backend setup

**Document date:** 2026-05-13
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
- **Async analysis worker:** Production runs `sushi-analysis-worker` with `python -m app.workers.analysis_batch_worker`. The backend enqueues a Cloud Task after creating an analysis batch, and the worker drains queued items through `POST /internal/analysis-worker/drain`. The worker scales to zero when idle.
- **App identity:** `FastAPI(title="Influencer Video Intelligence", version="0.1.0")` in `app/main.py`.
- **Startup:** After DB connection (with retries for managed databases), SQLAlchemy `Base.metadata.create_all` runs, then helpers in `app/db_migrations.py`.

---

## Persistence

- **Engine:** `sqlalchemy.create_engine` from `DATABASE_URL`.
- **Sessions:** Request-scoped `Session` via `get_db_session()` (`sessionmaker`, `autocommit=False`).
- **SQLite:** `check_same_thread=False` when URL starts with `sqlite`.
- **PostgreSQL:** `pool_pre_ping=True`; connection retries in `get_db_engine()` help managed Postgres / cold starts.
- **Schema evolution:** `create_all` + imperative migrations in code (no Alembic in dependencies).

---

## Configuration

Centralized in `app/config.py` (`Settings`). Notable categories:

- **Environment:** `ENVIRONMENT`, `DATABASE_URL`, cookie/security flags (`SECURE_COOKIES`, `AUTH_*`).
- **Gemini:** `GEMINI_API_KEY`, `GEMINI_MODEL_ANALYSIS`, `GEMINI_MODEL_CHAT`, analysis/chat limits.
- **YouTube / transcripts:** transcript API (`YOUTUBE_TRANSCRIPT_*`), Data API (`YOUTUBE_DATA_API_KEY`), comment pagination limits (`YOUTUBE_COMMENTS_*`).
- **Analysis worker wake tasks:** `GCP_PROJECT_ID`, `GCP_REGION`, `ANALYSIS_WORKER_URL`, `ANALYSIS_WORKER_TASKS_QUEUE`, `ANALYSIS_WORKER_TASK_SERVICE_ACCOUNT_EMAIL`, `ANALYSIS_WORKER_DRAIN_*`, optional `ANALYSIS_WORKER_INTERNAL_TOKEN`.
- **VOC thresholds:** `VOC_FAILED_RATIO_*`, `VOC_CONFIDENCE_*`.

See `.env.example` for names and sane defaults.

---

## HTTP API surface

Routers are registered from `app/main.py`, including:

- Health, authentication, monitors, videos, chat, incidents, agent settings, knowledge, VOC, watchlist.
- Async analysis batches (`/analysis/batches` create/status/items/cancel).
- Project, video, analysis, batch, knowledge, chat, incident, alert, watchlist, and agent settings APIs are authenticated and scoped to the current account. Account-wide list/batch requests mean “all projects owned by the current user,” not global database access.

**Multipart uploads:** `python-multipart` where file uploads apply.

**Agent settings:** Runtime analysis instructions are stored per user in the `agent_settings` database table. The root `AGENTS.md` is not shared product settings.

---

## GCP deployment (documented pattern)

Deployments are described in `DEPLOY_LOG.md` and implied by `firebase.json` and `.env.example`.


| Piece                           | Typical setup                                                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Cloud Run**                   | Service name `sushi-backend`, region `asia-southeast1`, listens on `PORT` (8080).                                                    |
| **Cloud Run worker**            | Service name `sushi-analysis-worker`, command `python -m app.workers.analysis_batch_worker`, request-triggered with `min-instances=0`, `max-instances=1`, `concurrency=1`. |
| **Cloud Tasks**                 | Queue `sushi-analysis-worker` in `asia-southeast1`; backend enqueues drain tasks and the queue invokes the private worker service.     |
| **Supabase PostgreSQL**         | Production database accessed through the Supabase session pooler.                                                                     |
| `DATABASE_URL` on Cloud Run     | Uses TCP/TLS DSN via `postgresql+psycopg2://postgres.PROJECT_REF:PASSWORD@HOST:5432/postgres?sslmode=require`.                       |
| **Artifact Registry**           | Docker image builds (example path in deploy docs: `asia-southeast1-docker.pkg.dev/.../sushi-backend/...`).                           |
| **Firebase Hosting**            | Serves static `public/`; `rewrites` send all routes to Cloud Run `sushi-backend` in `asia-southeast1` (`firebase.json`).              |
| **IAM**                         | Unauthenticated hosting often uses `allUsers` with `roles/run.invoker` on Cloud Run (document only; confirm in GCP console).          |


**Build/deploy commands** (adapt project/region/instance):

- `gcloud builds submit ...` or `gcloud run deploy sushi-backend --source ...` with `--clear-cloudsql-instances`, `--set-env-vars`, `--allow-unauthenticated` as needed.
- `gcloud tasks queues create sushi-analysis-worker --location asia-southeast1` once per environment, then grant the backend runtime service account `roles/cloudtasks.enqueuer`.
- `gcloud run deploy sushi-analysis-worker ... --min-instances 0 --max-instances 1 --concurrency 1 --timeout 1800 --no-allow-unauthenticated`.
- `firebase deploy --only hosting` after Hosting config changes.

Store secrets (API keys, DB passwords) in **Secret Manager** or Cloud Run secrets — not in markdown or git.

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
