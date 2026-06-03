from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.models  # noqa: F401
from app.api.agent_settings_router import router as agent_settings_router
from app.api.analysis_batch_router import router as analysis_batch_router
from app.api.auth_router import router as auth_router
from app.api.chat_router import router as chat_router
from app.api.health_router import router as health_router
from app.api.incident_router import router as incident_router
from app.api.knowledge_router import router as knowledge_router
from app.api.monitor_router import router as monitor_router
from app.api.project_insights_router import router as project_insights_router
from app.api.video_router import router as video_router
from app.api.voc_router import router as voc_router
from app.api.watchlist_router import router as watchlist_router
from app.db_migrations import (
    cleanup_orphan_video_data,
    ensure_agent_settings_table,
    ensure_analysis_batch_tables,
    ensure_analysis_results_agent_settings_hash_column_and_index,
    ensure_analysis_results_comment_columns,
    ensure_analysis_results_language_column_and_index,
    ensure_analysis_results_summary_columns,
    ensure_analysis_results_transcript_provenance_columns,
    ensure_default_app_users,
    ensure_monitor_profiles_owner_user_id,
    ensure_monitor_profiles_key_products_column,
    ensure_project_insight_job_tables,
    ensure_project_insight_reports_portfolio_columns,
    retire_legacy_business_impact_columns,
    ensure_video_candidate_scoped_youtube_uniqueness,
    ensure_video_candidate_assignment_columns,
    ensure_video_candidate_reach_columns,
    ensure_video_comments_table,
)
from app.db import get_db_engine
from app.models.base import Base
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Get database engine with retry logic for managed database connections.
    engine = get_db_engine(max_retries=15, retry_delay=2.0)

    # Run database migrations after the database connection is ready.
    Base.metadata.create_all(bind=engine)
    ensure_default_app_users(engine)
    ensure_agent_settings_table(engine)
    ensure_analysis_batch_tables(engine)
    ensure_monitor_profiles_key_products_column(engine)
    ensure_monitor_profiles_owner_user_id(engine)
    ensure_project_insight_job_tables(engine)
    ensure_analysis_results_summary_columns(engine)
    ensure_analysis_results_language_column_and_index(engine)
    ensure_analysis_results_agent_settings_hash_column_and_index(engine)
    ensure_analysis_results_comment_columns(engine)
    ensure_analysis_results_transcript_provenance_columns(engine)
    ensure_video_comments_table(engine)
    ensure_video_candidate_assignment_columns(engine)
    ensure_video_candidate_reach_columns(engine)
    ensure_video_candidate_scoped_youtube_uniqueness(engine)
    ensure_project_insight_reports_portfolio_columns(engine)
    retire_legacy_business_impact_columns(engine)
    cleanup_orphan_video_data(engine)
    logger.info("Application startup complete - all migrations finished")

    yield


app = FastAPI(
    title="Influencer Video Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def render_home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def render_project(request: Request, project_id: int):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"project_id": project_id}
    )


app.include_router(monitor_router)
app.include_router(project_insights_router)
app.include_router(video_router)
app.include_router(analysis_batch_router)
app.include_router(chat_router)
app.include_router(incident_router)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(agent_settings_router)
app.include_router(knowledge_router)
app.include_router(voc_router)
app.include_router(watchlist_router)
