from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.mappers import map_analysis_response, map_video_response
from app.db import get_db_session
from app.models.enums import QueueState
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.video import ManualVideoCreateRequest, VideoApproveRequest, VideoDiscoveryRequest, VideoListResponse
from app.services.analysis_service import AnalysisService
from app.services.triage_service import TriageService

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/discover", response_model=VideoListResponse)
def discover_videos(payload: VideoDiscoveryRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        videos = service.discover_for_profile(
            monitor_profile_id=payload.monitor_profile_id,
            max_results=payload.max_results,
        )
        responses = [map_video_response(item) for item in videos]
        return VideoListResponse(items=responses, total=len(responses))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/manual")
def add_manual_video(payload: ManualVideoCreateRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        candidate = service.add_manual_video(
            monitor_profile_id=payload.monitor_profile_id,
            video_url=payload.video_url,
            language=payload.language,
        )
        return map_video_response(candidate)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("", response_model=VideoListResponse)
def list_videos(
    monitor_profile_id: Optional[int] = None,
    queue_state: Optional[QueueState] = Query(default=None),
    title: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    service = TriageService(db)
    videos = service.list_candidates(
        monitor_profile_id=monitor_profile_id,
        queue_state=queue_state,
        title_filter=title,
    )
    responses = [map_video_response(item) for item in videos]
    return VideoListResponse(items=responses, total=len(responses), title_filter=title)


@router.post("/{video_id}/approve")
def approve_video(video_id: int, payload: VideoApproveRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        candidate = service.approve(video_id=video_id, approved=payload.approved)
        return map_video_response(candidate)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        service.delete_video(video_id=video_id)
        return {"status": "success", "message": "Video deleted"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{video_id}/analyze", response_model=AnalysisResponse)
def analyze_video(video_id: int, payload: AnalysisRequest, db: Session = Depends(get_db_session)):
    service = AnalysisService(db)
    try:
        result = service.analyze_video(video_id=video_id, force_reanalyze=payload.force_reanalyze)
        return map_analysis_response(result)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{video_id}/analysis", response_model=AnalysisResponse)
def get_latest_analysis(video_id: int, db: Session = Depends(get_db_session)):
    service = AnalysisService(db)
    result = service.analysis_repository.get_latest_for_video(video_candidate_id=video_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return map_analysis_response(result)

