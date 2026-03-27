# Influencer Video Intelligence (YouTube MVP)

Web app for marketing teams to monitor influencer video narratives, analyze sentiment/risk, and collaborate on follow-up actions with a grounded AI chatbot.

## What is implemented

- Monitoring profile creation (`brand keywords`, `markets`, `languages`)
- Candidate discovery queue (live YouTube search with mock fallback)
- Manual YouTube URL add flow for guaranteed real-video analysis
- Relevance scoring from title/description keyword matches
- Human-in-the-loop approve/reject queue state
- Transcript-first Gemini analysis pipeline with durable storage
- Chunked map-reduce Gemini analysis for long transcripts
- Re-analysis dedupe by `youtube_video_id + analysis_version`
- Shared analysis details (transcript, summary, sentiment, risk, evidence)
- Per-video chatbot with citation support and insufficient-evidence behavior
- Fail-closed Gemini runtime (no analysis/chat mock fallback when key or SDK is missing)
- Incident escalation and inbox alert generation
- Audit logs for discovery/approve/analyze/chat/escalate actions
- Key unit tests for dedupe, re-analysis, chat grounding behavior, and escalation

## Architecture summary

- **Frontend**: server-rendered HTML + vanilla JS (minimal Notion-like layout)
- **API**: FastAPI routers
- **Data**: SQLite via SQLAlchemy models
- **AI**: Gemini client wrapper (`gemini-3-flash` configurable via env vars)
- **Safety**: transcript prompt-injection sanitization, evidence-first answers, fail-closed runtime errors

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
- `GEMINI_MODEL_ANALYSIS` - Gemini model used for analysis (default: `gemini-3-flash`).
- `GEMINI_MODEL_CHAT` - Gemini model used for per-video chat (default: `gemini-3-flash`).
- `ENABLE_MOCK_DISCOVERY` - `false` uses live search, `true` forces deterministic mock videos.
- `TRANSCRIPT_LANGUAGES` - comma-separated transcript preference order.
- `YOUTUBE_TRANSCRIPT_API_KEY` - required API key for YouTubeTranscript.dev transcript extraction.
- `YOUTUBE_TRANSCRIPT_BASE_URL` - transcript API base URL (default: `https://www.youtubetranscript.dev/api/v2`).
- `YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS` - per-request timeout for transcript provider calls.
- `YOUTUBE_TRANSCRIPT_MAX_RETRIES` - retry count for transient transcript transport failures.
- `ANALYSIS_MAX_TRANSCRIPT_CHARS` - max transcript chars considered before chunking.
- `ANALYSIS_CHUNK_CHARS` - per-chunk character budget used in map-reduce analysis.
- `ANALYSIS_CHUNK_OVERLAP_CHARS` - overlap budget retained between adjacent chunks.
- `ANALYSIS_MAX_CHUNKS` - hard cap for number of analysis chunks.
- `CHAT_MAX_CONTEXT_CHARS` - chat context cap before transcript truncation.
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
- `GET /health/gemini?probe=true|false`

## Security note

Do not commit raw API keys. Keep `GEMINI_API_KEY` and `YOUTUBE_TRANSCRIPT_API_KEY` only in local/prod environment variables.

## Gemini troubleshooting

- `GEMINI_API_KEY is not configured` means analysis/chat now fail closed by design; set a valid key in `.env`.
- `google-generativeai package is required` means the dependency is missing; run `pip install -r requirements.txt`.
- If `/health/gemini` returns `ready: false`, analysis/chat endpoints will return `503` until key and SDK are available.

