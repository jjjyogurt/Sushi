from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.api.mappers import map_video_response
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.video import VideoListResponse
from app.services.triage_service import TriageService
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=VideoListResponse)
def list_watchlist(current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db_session)):
    watchlist_service = WatchlistService(db)
    triage_service = TriageService(db)
    videos = watchlist_service.list_videos_for_user(user_id=current_user.id)
    profile_names = triage_service.get_monitor_profile_names_for_videos(videos)
    sentiment_labels = triage_service.get_sentiment_labels_for_videos(videos)
    analysis_statuses = triage_service.get_analysis_statuses_for_videos(videos)
    responses = [
        map_video_response(
            item,
            monitor_profile_name=profile_names.get(item.monitor_profile_id),
            sentiment_label=sentiment_labels.get(item.id),
            latest_analysis_status=analysis_statuses.get(item.id),
            is_bookmarked=True,
        )
        for item in videos
    ]
    return VideoListResponse(items=responses, total=len(responses))


@router.post("/videos/{video_id}")
def add_watchlist_video(video_id: int, current_user: AppUser = Depends(get_current_user), db: Session = Depends(get_db_session)):
    watchlist_service = WatchlistService(db)
    try:
        watchlist_service.add(user_id=current_user.id, video_id=video_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"status": "success", "bookmarked": True}


@router.delete("/videos/{video_id}")
def remove_watchlist_video(
    video_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    watchlist_service = WatchlistService(db)
    watchlist_service.remove(user_id=current_user.id, video_id=video_id)
    return {"status": "success", "bookmarked": False}
