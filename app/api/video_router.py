import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user, get_optional_current_user
from app.api.mappers import map_analysis_response, map_video_response
from app.db import get_db_session
from app.models.app_user import AppUser
from app.models.enums import QueueState
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.schemas.video import (
    ManualVideoCreateRequest,
    VideoApproveRequest,
    VideoAssigneeUpdateRequest,
    VideoBulkAddRequest,
    VideoBulkAddResponse,
    VideoDiscoveryRequest,
    VideoListResponse,
    VideoSearchRequest,
    VideoSearchResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.exceptions import (
    GeminiConfigurationError,
    GeminiDependencyError,
    GeminiProviderError,
    GeminiResponseError,
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptUnavailableError,
)
from app.services.exceptions import VideoProjectConflictError
from app.services.triage_service import TriageService
from app.repositories.watchlist_repository import WatchlistRepository

router = APIRouter(prefix="/videos", tags=["videos"])
logger = logging.getLogger(__name__)


def map_videos_with_context(service: TriageService, videos, *, current_user_id: Optional[str] = None):
    profile_names = service.get_monitor_profile_names_for_videos(videos)
    sentiment_labels = service.get_sentiment_labels_for_videos(videos)
    analysis_statuses = service.get_analysis_statuses_for_videos(videos)
    bookmarked_video_ids = set()
    if current_user_id:
        video_ids = [video.id for video in videos]
        watchlist_repository = WatchlistRepository(service.video_repository.session)
        bookmarked_video_ids = watchlist_repository.list_bookmarked_video_ids(
            user_id=current_user_id,
            video_ids=video_ids,
        )
    return [
        map_video_response(
            item,
            monitor_profile_name=profile_names.get(item.monitor_profile_id),
            sentiment_label=sentiment_labels.get(item.id),
            latest_analysis_status=analysis_statuses.get(item.id),
            is_bookmarked=item.id in bookmarked_video_ids,
        )
        for item in videos
    ]


@router.post("/discover", response_model=VideoListResponse)
def discover_videos(payload: VideoDiscoveryRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        videos = service.discover_for_profile(
            monitor_profile_id=payload.monitor_profile_id,
            max_results=payload.max_results,
        )
        responses = map_videos_with_context(service, videos)
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
        responses = map_videos_with_context(service, [candidate])
        return responses[0]
    except VideoProjectConflictError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(error),
                "code": "VIDEO_PROJECT_CONFLICT",
                "existing_video_id": error.existing_video_id,
                "existing_monitor_profile_id": error.existing_monitor_profile_id,
            },
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("", response_model=VideoListResponse)
def list_videos(
    monitor_profile_id: Optional[int] = None,
    queue_state: Optional[QueueState] = Query(default=None),
    risk_level: Optional[str] = None,
    sentiment: Optional[str] = None,
    title: Optional[str] = Query(default=None, max_length=255),
    current_user: Optional[AppUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db_session),
):
    service = TriageService(db)
    videos = service.list_candidates(
        monitor_profile_id=monitor_profile_id,
        queue_state=queue_state,
        risk_level=risk_level,
        sentiment=sentiment,
        title_query=title,
    )
    responses = map_videos_with_context(
        service,
        videos,
        current_user_id=current_user.id if current_user else None,
    )
    return VideoListResponse(
        items=responses,
        total=len(responses),
        risk_level=risk_level,
        sentiment=sentiment,
    )


@router.post("/search", response_model=VideoSearchResponse)
def search_videos(payload: VideoSearchRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        items = service.search_candidates(
            monitor_profile_id=payload.monitor_profile_id,
            query=payload.query,
            max_results=payload.max_results,
        )
        return VideoSearchResponse(items=items, total=len(items), query=payload.query)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/bulk-add", response_model=VideoBulkAddResponse)
def bulk_add_videos(payload: VideoBulkAddRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        items = service.add_bulk_candidates(
            monitor_profile_id=payload.monitor_profile_id,
            candidates=payload.candidates,
        )
        responses = map_videos_with_context(service, items)
        return VideoBulkAddResponse(items=responses, total=len(responses))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{video_id}/approve")
def approve_video(video_id: int, payload: VideoApproveRequest, db: Session = Depends(get_db_session)):
    service = TriageService(db)
    try:
        candidate = service.approve(video_id=video_id, approved=payload.approved)
        responses = map_videos_with_context(service, [candidate])
        return responses[0]
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{video_id}/assignee")
def update_video_assignee(
    video_id: int,
    payload: VideoAssigneeUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = TriageService(db)
    try:
        candidate = service.assign_video(
            video_id=video_id,
            assigned_user_id=payload.assigned_user_id,
            actor=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    responses = map_videos_with_context(service, [candidate], current_user_id=current_user.id)
    return responses[0]


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
    logger.info("api analyze request video_id=%s force_reanalyze=%s", video_id, payload.force_reanalyze)
    service = AnalysisService(db)
    try:
        result = service.analyze_video(
            video_id=video_id,
            force_reanalyze=payload.force_reanalyze,
            knowledge_base_id=payload.knowledge_base_id,
        )
        return map_analysis_response(result)
    except (GeminiConfigurationError, GeminiDependencyError) as error:
        logger.warning("api analyze GeminiNotReady video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=503, detail=f"GEMINI_NOT_READY: {error}") from error
    except GeminiProviderError as error:
        logger.warning("api analyze GeminiProviderError video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=503, detail=f"GEMINI_PROVIDER_ERROR: {error}") from error
    except GeminiResponseError as error:
        logger.warning("api analyze GeminiResponseError video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=503, detail=f"GEMINI_RESPONSE_ERROR: {error}") from error
    except TranscriptBlockedError as error:
        logger.warning("api analyze TranscriptBlocked video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=503, detail=f"TRANSCRIPT_BLOCKED: {error}") from error
    except TranscriptUnavailableError as error:
        logger.warning("api analyze TranscriptUnavailable video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=422, detail=f"TRANSCRIPT_UNAVAILABLE: {error}") from error
    except TranscriptProviderError as error:
        logger.warning("api analyze TranscriptProviderError video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=503, detail=f"TRANSCRIPT_PROVIDER_ERROR: {error}") from error
    except ValueError as error:
        logger.warning("api analyze ValueError video_id=%s error=%s", video_id, error)
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{video_id}/analysis", response_model=AnalysisResponse)
def get_latest_analysis(video_id: int, language: Optional[str] = Query(default=None), db: Session = Depends(get_db_session)):
    service = AnalysisService(db)
    try:
        normalized_language = service.normalize_analysis_language(language)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    result = service.analysis_repository.get_latest_for_video(
        video_candidate_id=video_id,
        language=normalized_language,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return map_analysis_response(result)

