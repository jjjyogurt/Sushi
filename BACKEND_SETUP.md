# Backend setup

**Document date:** 2026-04-28  
**Scope:** Backend runtime, persistence, integrations, and deployment as implemented in this repository.

---

## Summary


| Layer                    | Technology                                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------------------------- |
| **Language**             | Python 3.12 (see `Dockerfile`)                                                                        |
| **Framework**            | FastAPI on Starlette (ASGI)                                                                           |
| **Server**               | Uvicorn                                                                                               |
| **ORM / DB**             | SQLAlchemy 2.x · SQLite locally (`./sushi.db` default) · PostgreSQL in production (`psycopg2-binary`) |
| **Settings**             | `pydantic-settings` + `.env` (`python-dotenv`)                                                        |
| **Validation / schemas** | Pydantic v2 (`app/schemas/`)                                                                          |
| **HTTP client**          | `httpx`                                                                                               |
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
- **App identity:** `FastAPI(title="Influencer Video Intelligence", version="0.1.0")` in `app/main.py`.
- **Startup:** After DB connection (with retries for managed databases), SQLAlchemy `Base.metadata.create_all` runs, then helpers in `app/db_migrations.py`.

---

## Persistence

- **Engine:** `sqlalchemy.create_engine` from `DATABASE_URL`.
- **Sessions:** Request-scoped `Session` via `get_db_session()` (`sessionmaker`, `autocommit=False`).
- **SQLite:** `check_same_thread=False` when URL starts with `sqlite`.
- **PostgreSQL:** `pool_pre_ping=True`; connection retries in `get_db_engine()` help Cloud SQL / cold starts.
- **Schema evolution:** `create_all` + imperative migrations in code (no Alembic in dependencies).

---

## Configuration

Centralized in `app/config.py` (`Settings`). Notable categories:

- **Environment:** `ENVIRONMENT`, `DATABASE_URL`, cookie/security flags (`SECURE_COOKIES`, `AUTH_*`).
- **Gemini:** `GEMINI_API_KEY`, `GEMINI_MODEL_ANALYSIS`, `GEMINI_MODEL_CHAT`, analysis/chat limits.
- **YouTube / transcripts:** transcript API (`YOUTUBE_TRANSCRIPT_*`), Data API (`YOUTUBE_DATA_API_KEY`), comment pagination limits (`YOUTUBE_COMMENTS_*`).
- **VOC thresholds:** `VOC_FAILED_RATIO_*`, `VOC_CONFIDENCE_*`.

See `.env.example` for names and sane defaults.

---

## HTTP API surface

Routers are registered from `app/main.py`, including:

- Health, authentication, monitors, videos, chat, incidents, agent settings, knowledge, VOC, watchlist.

**Multipart uploads:** `python-multipart` where file uploads apply.

---

## GCP deployment (documented pattern)

Deployments are described in `DEPLOY_LOG.md` and implied by `firebase.json` and `.env.example`.


| Piece                           | Typical setup                                                                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Cloud Run**                   | Service name `**sushi-backend`**, region `**asia-southeast1`**, listens on `**PORT**` (8080).                                        |
| **Cloud SQL**                   | PostgreSQL; instance attached via `**--add-cloudsql-instances PROJECT:REGION:INSTANCE`**.                                            |
| `**DATABASE_URL` on Cloud Run** | Uses Unix socket via `postgresql+psycopg2://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE` (see `.env.example`).      |
| **Artifact Registry**           | Docker image builds (example path in deploy docs: `asia-southeast1-docker.pkg.dev/.../sushi-backend/...`).                           |
| **Firebase Hosting**            | Serves static `public/`; `**rewrites`** send all routes to Cloud Run `**sushi-backend`** in `**asia-southeast1**` (`firebase.json`). |
| **IAM**                         | Unauthenticated hosting often uses `**allUsers`** with `**roles/run.invoker`** on Cloud Run (document only; confirm in GCP console). |


**Build/deploy commands** (adapt project/region/instance):

- `gcloud builds submit ...` or `gcloud run deploy sushi-backend --source ...` with `--add-cloudsql-instances`, `--set-env-vars`, `--allow-unauthenticated` as needed.
- `firebase deploy --only hosting` after Hosting config changes.

Store secrets (API keys, DB passwords) in **Secret Manager** or Cloud Run secrets — not in markdown or git.

---

## Testing

- **Runner:** `pytest` under `tests/unit/`.
- **DB fixtures:** In-memory SQLite in `tests/unit/conftest.py` for many tests.

---

## Related documents


| File                            | Contents                                        |
| ------------------------------- | ----------------------------------------------- |
| `LOCAL_SETUP.md`                | Local venv and run instructions                 |
| `DEPLOY_LOG.md`                 | Historical deployment notes and troubleshooting |
| `PRDs/TECH_STACK_2026-04-01.md` | Broader stack write-up                          |


---

## Dependency list (`requirements.txt`)

`fastapi`, `starlette`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `pydantic-settings`, `python-dotenv`, `google-generativeai`, `youtube-search-python`, `yt-dlp`, `pytest`, `httpx`, `jinja2`, `python-multipart`