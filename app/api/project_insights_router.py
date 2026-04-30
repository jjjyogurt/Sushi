from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.schemas.project_insights import (
    ProjectInsightCurrentResponse,
    ProjectInsightHistoryResponse,
    ProjectInsightReportResponse,
)
from app.services.project_insights_service import ProjectInsightsService
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
        analyzed_video_count=model.analyzed_video_count,
        total_video_count=model.total_video_count,
        excluded_video_count=model.excluded_video_count,
        coverage_pct=model.coverage_pct,
        overall_sentiment=model.overall_sentiment,
        risk_level=model.risk_level,
        risk_score=model.risk_score,
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


@router.get("/current", response_model=ProjectInsightCurrentResponse)
def get_current_report(monitor_profile_id: int, db: Session = Depends(get_db_session)):
    service = ProjectInsightsService(db)
    try:
        report = service.get_current_report(monitor_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ProjectInsightCurrentResponse(current=_map_report(report) if report is not None else None)


@router.get("/history", response_model=ProjectInsightHistoryResponse)
def list_report_history(
    monitor_profile_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
):
    service = ProjectInsightsService(db)
    try:
        reports = service.list_report_history(monitor_profile_id, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    mapped = [_map_report(item) for item in reports]
    return ProjectInsightHistoryResponse(items=mapped, total=len(mapped))


@router.post("/refresh", response_model=ProjectInsightReportResponse)
def refresh_report(monitor_profile_id: int, db: Session = Depends(get_db_session)):
    service = ProjectInsightsService(db)
    try:
        report = service.refresh_report(monitor_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _map_report(report)


@router.delete("/history/{report_id}")
def delete_history_item(monitor_profile_id: int, report_id: int, db: Session = Depends(get_db_session)):
    service = ProjectInsightsService(db)
    try:
        deleted = service.delete_history_item(
            monitor_profile_id=monitor_profile_id,
            report_id=report_id,
        )
    except ValueError as error:
        detail = str(error)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from error
    return {"status": "success", "deleted": deleted}


@router.delete("/history")
def clear_history(monitor_profile_id: int, db: Session = Depends(get_db_session)):
    service = ProjectInsightsService(db)
    try:
        deleted = service.clear_history(monitor_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"status": "success", "deleted": deleted}
