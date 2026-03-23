# Influencer Video Intelligence (YouTube MVP)

Web app for marketing teams to monitor influencer video narratives, analyze sentiment/risk, and collaborate on follow-up actions with a grounded AI chatbot.

## What is implemented

- Monitoring profile creation (`brand keywords`, `markets`, `languages`)
- Candidate discovery queue (live YouTube search with mock fallback)
- Manual YouTube URL add flow for guaranteed real-video analysis
- Relevance scoring from title/description keyword matches
- Human-in-the-loop approve/reject queue state
- Transcript-first Gemini analysis pipeline with durable storage
- Re-analysis dedupe by `youtube_video_id + analysis_version`
- Shared analysis details (transcript, summary, sentiment, risk, evidence)
- Per-video chatbot with citation support and insufficient-evidence behavior
- Incident escalation and inbox alert generation
- Audit logs for discovery/approve/analyze/chat/escalate actions
- Key unit tests for dedupe, re-analysis, chat grounding behavior, and escalation

## Architecture summary

- **Frontend**: server-rendered HTML + vanilla JS (minimal Notion-like layout)
- **API**: FastAPI routers
- **Data**: SQLite via SQLAlchemy models
- **AI**: Gemini client wrapper (`gemini-3` configurable via env vars)
- **Safety**: transcript prompt-injection sanitization, evidence-first answers, fallback responses

## Project structure

- `app/main.py` - application bootstrap and router registration
- `app/api/` - HTTP route handlers
- `app/services/` - business logic (discovery, analysis, chat, escalation)
- `app/repositories/` - DB access abstraction
- `app/models/` - SQLAlchemy schema
- `app/schemas/` - request/response models
- `app/templates/` + `app/static/` - minimal UI
- `tests/unit/` - key unit tests

## Environment variables

- `GEMINI_API_KEY` - required for live Gemini summarization/chat.
- `GEMINI_MODEL_ANALYSIS` - Gemini model used for analysis (default: `gemini-3`).
- `GEMINI_MODEL_CHAT` - Gemini model used for per-video chat (default: `gemini-3`).
- `ENABLE_MOCK_DISCOVERY` - `false` uses live search, `true` forces deterministic mock videos.
- `TRANSCRIPT_LANGUAGES` - comma-separated transcript preference order.
- `ANALYSIS_MAX_TRANSCRIPT_CHARS` - transcript size cap sent to Gemini prompt.
- `DATABASE_URL` - sqlite/postgres DSN for storage.

## Setup

1. Create and activate virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create env file:
   - `cp .env.example .env`
4. Run app:
   - `uvicorn app.main:app --reload`
5. Open:
   - [http://127.0.0.1:8000](http://127.0.0.1:8000)

## API endpoints (MVP)

- `POST /monitor-profiles`
- `GET /monitor-profiles`
- `POST /videos/discover`
- `GET /videos?monitor_profile_id=&title=`
- `POST /videos/{video_id}/approve`
- `POST /videos/{video_id}/analyze`
- `GET /videos/{video_id}/analysis`
- `POST /videos/{video_id}/chat`
- `GET /videos/{video_id}/chat`
- `POST /videos/{video_id}/escalate`
- `GET /alerts`

## Security note

Do not commit raw API keys. Since a key was previously shared in chat, rotate/revoke it and update `.env` with the new key before production usage.

