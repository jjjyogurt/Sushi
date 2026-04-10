# Local setup and running guide

Use this when setting up **Sushi** (Influencer Video Intelligence) on your machine for the first time.

## Prerequisites

- **Python 3** (3.10+ recommended)
- **Terminal** (macOS/Linux or Windows PowerShell)
- **Secrets** (not in git): `GEMINI_API_KEY`, `YOUTUBE_TRANSCRIPT_API_KEY` — get these from whoever hands off the project, or create your own keys

## 1. Go to the project folder

```bash
cd /path/to/Sushi
```

## 2. Create and activate a virtual environment

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your shell prompt should show `(.venv)` when the venv is active.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Environment variables

1. Copy the example env file in the **project root** (same folder as `README.md`):

   ```bash
   cp .env.example .env
   ```

2. Edit **`.env`** and set at least:

   - `GEMINI_API_KEY`
   - `YOUTUBE_TRANSCRIPT_API_KEY`

3. Optional: tune other variables; defaults match `.env.example`. Full list: see **Environment variables** in `README.md`.

**Security:** Never commit `.env` or paste API keys into chat or tickets.

## 5. Run the application

With the virtual environment **activated**:

```bash
uvicorn app.main:app --reload
```

Open in a browser: **http://127.0.0.1:8000**

## 6. Health check (optional)

Visit or curl:

`http://127.0.0.1:8000/health/gemini?probe=true`

If Gemini is not configured, analysis/chat endpoints may return **503** until keys and the SDK are valid.

## 7. Run tests

```bash
pytest
```

## Every new terminal session

If you open a new terminal, activate the venv again before running commands:

```bash
cd /path/to/Sushi
source .venv/bin/activate
uvicorn app.main:app --reload
```

Windows:

```powershell
cd \path\to\Sushi
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| `uvicorn` not found | Activate `.venv`, then `pip install -r requirements.txt` |
| Gemini / analysis errors about missing key | Set `GEMINI_API_KEY` in `.env`, restart `uvicorn` |
| Port 8000 already in use | `uvicorn app.main:app --reload --port 8001` and open **http://127.0.0.1:8001** |

## Related files

- `README.md` — product overview, architecture, API list, env reference
- `.env.example` — template for `.env`
- `AGENTS.md` — optional domain/agent context for AI-assisted work (not runtime config)
