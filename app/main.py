from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.models  # noqa: F401
from app.api.agent_settings_router import router as agent_settings_router
from app.api.chat_router import router as chat_router
from app.api.health_router import router as health_router
from app.api.incident_router import router as incident_router
from app.api.knowledge_router import router as knowledge_router
from app.api.monitor_router import router as monitor_router
from app.api.video_router import router as video_router
from app.db import engine
from app.models.base import Base

app = FastAPI(title="Influencer Video Intelligence", version="0.1.0")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Ensure local SQLite tables exist for both API runtime and local script usage.
Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def render_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def render_project(request: Request, project_id: int):
    return templates.TemplateResponse("index.html", {"request": request, "project_id": project_id})


app.include_router(monitor_router)
app.include_router(video_router)
app.include_router(chat_router)
app.include_router(incident_router)
app.include_router(health_router)
app.include_router(agent_settings_router)
app.include_router(knowledge_router)

