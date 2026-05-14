from sqlalchemy.orm import Session

from app.repositories.audit_repository import AuditRepository
from app.repositories.video_repository import VideoRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.access_control import AccessControlService


class WatchlistService:
    def __init__(self, session: Session):
        self.session = session
        self.audit_repository = AuditRepository(session)
        self.video_repository = VideoRepository(session)
        self.watchlist_repository = WatchlistRepository(session)
        self.access_control = AccessControlService(session)

    def list_videos_for_user(self, *, user_id: str):
        return self.watchlist_repository.list_videos_for_user(user_id=user_id)

    def add(self, *, user_id: str, video_id: int):
        self.access_control.require_video_owner(video_id=video_id, user_id=user_id)
        created = self.watchlist_repository.add(user_id=user_id, video_candidate_id=video_id)
        self.audit_repository.record(
            actor=user_id,
            action="watchlist_add",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"created={created}",
        )
        return created

    def remove(self, *, user_id: str, video_id: int):
        deleted = self.watchlist_repository.remove(user_id=user_id, video_candidate_id=video_id)
        self.audit_repository.record(
            actor=user_id,
            action="watchlist_remove",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"deleted={deleted}",
        )
        return deleted
