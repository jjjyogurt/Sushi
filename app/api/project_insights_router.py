from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.project_insights import (
    ProjectInsightCurrentResponse,
    ProjectInsightActiveJobResponse,
    ProjectInsightJobResponse,
    ProjectInsightHistoryResponse,
    ProjectInsightReportResponse,
)
from app.services.analysis_worker_tasks import AnalysisWorkerTaskClient
from app.services.project_insight_job_service import ProjectInsightJobService
from app.services.project_insights_service import ProjectInsightsService, normalize_project_insight_language
from app.services.access_control import AccessControlService
from app.utils.json_codec import decode_json

router = APIRouter(prefix="/monitor-profiles/{monitor_profile_id}/insights", tags=["project-insights"])


def _map_report(model) -> ProjectInsightReportResponse:
    praise_points = decode_json(model.praise_points_json, [])
    criticism_points = decode_json(model.criticism_points_json, [])
    user_recommendations = decode_json(model.user_recommendations_json, [])
    top_risk_trigger = criticism_points[0] if isinstance(criticism_points, list) and criticism_points else ""
    return ProjectInsightReportResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        monitor_profile_id=model.monitor_profile_id,
        language=getattr(model, "language", "en"),
        analyzed_video_count=model.analyzed_video_count,
        total_video_count=model.total_video_count,
        excluded_video_count=model.excluded_video_count,
        coverage_pct=model.coverage_pct,
        overall_sentiment=model.overall_sentiment,
        risk_level=model.risk_level,
        summary_headline=model.summary_headline,
        summary_body=model.summary_body,
        top_risk_trigger=top_risk_trigger,
        praise_points=praise_points,
        criticism_points=criticism_points,
        user_recommendations=user_recommendations,
        excluded_reasons=decode_json(model.excluded_reasons_json, []),
        sentiment_breakdown=decode_json(getattr(model, "sentiment_breakdown_json", "{}"), {}),
        risk_breakdown=decode_json(getattr(model, "risk_breakdown_json", "{}"), {}),
        reach_metrics=decode_json(getattr(model, "reach_metrics_json", "{}"), {}),
        top_negative_videos=decode_json(getattr(model, "top_negative_videos_json", "[]"), []),
        report_markdown=model.report_markdown,
    )


def _map_job(model) -> ProjectInsightJobResponse:
    return ProjectInsightJobResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        monitor_profile_id=model.monitor_profile_id,
        language=getattr(model, "language", "en"),
        created_by=model.created_by,
        status=getattr(model.status, "value", str(model.status)).lower(),
        report_id=model.report_id,
        last_error=model.last_error,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


def _enqueue_or_process_project_insight_job(*, db: Session, reason: str) -> None:
    task_client = AnalysisWorkerTaskClient()
    if task_client.enqueue_drain(reason=reason):
        return
    ProjectInsightJobService(db).process_next_job()


@router.get("/current", response_model=ProjectInsightCurrentResponse)
def get_current_report(
    monitor_profile_id: int,
    language: str = Query(default="en"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightsService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        report = service.get_current_report(monitor_profile_id, language=normalized_language)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ProjectInsightCurrentResponse(current=_map_report(report) if report is not None else None)


@router.get("/history", response_model=ProjectInsightHistoryResponse)
def list_report_history(
    monitor_profile_id: int,
    language: str = Query(default="en"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightsService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        reports = service.list_report_history(monitor_profile_id, language=normalized_language, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    mapped = [_map_report(item) for item in reports]
    return ProjectInsightHistoryResponse(items=mapped, total=len(mapped))


@router.post("/refresh", response_model=ProjectInsightJobResponse)
def refresh_report(
    monitor_profile_id: int,
    background_tasks: BackgroundTasks,
    language: str = Query(default="en"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightJobService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        active_job = service.get_active_job(
            monitor_profile_id=monitor_profile_id,
            user_id=current_user.id,
            language=normalized_language,
        )
        if active_job is not None:
            return _map_job(active_job)
        job = service.create_or_get_active_job(
            monitor_profile_id=monitor_profile_id,
            user_id=current_user.id,
            language=normalized_language,
        )
        background_tasks.add_task(
            _enqueue_or_process_project_insight_job,
            db=db,
            reason=f"project_insight_job:{job.id}",
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _map_job(job)


@router.get("/jobs/active", response_model=ProjectInsightActiveJobResponse)
def get_active_job(
    monitor_profile_id: int,
    language: str = Query(default="en"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightJobService(db)
    try:
        job = service.get_active_job(
            monitor_profile_id=monitor_profile_id,
            user_id=current_user.id,
            language=normalized_language,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ProjectInsightActiveJobResponse(active=_map_job(job) if job is not None else None)


@router.get("/jobs/{job_id}", response_model=ProjectInsightJobResponse)
def get_job(
    monitor_profile_id: int,
    job_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = ProjectInsightJobService(db)
    try:
        job = service.get_job(monitor_profile_id=monitor_profile_id, job_id=job_id, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _map_job(job)


@router.delete("/history/{report_id}")
def delete_history_item(
    monitor_profile_id: int,
    report_id: int,
    language: str = Query(default="en"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightsService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        deleted = service.delete_history_item(
            monitor_profile_id=monitor_profile_id,
            report_id=report_id,
            language=normalized_language,
        )
    except ValueError as error:
        detail = str(error)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from error
    return {"status": "success", "deleted": deleted}


@router.delete("/history")
def clear_history(
    monitor_profile_id: int,
    language: str = Query(default="en"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    normalized_language = normalize_project_insight_language(language)
    service = ProjectInsightsService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        deleted = service.clear_history(monitor_profile_id, language=normalized_language)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"status": "success", "deleted": deleted}
