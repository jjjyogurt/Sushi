from typing import List, Set

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.video_candidate import VideoCandidate
from app.models.video_watchlist_entry import VideoWatchlistEntry
from app.models.monitor_profile import MonitorProfile


class WatchlistRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_videos_for_user(self, *, user_id: str) -> List[VideoCandidate]:
        return (
            self.session.query(VideoCandidate)
            .join(VideoWatchlistEntry, VideoWatchlistEntry.video_candidate_id == VideoCandidate.id)
            .join(MonitorProfile, MonitorProfile.id == VideoCandidate.monitor_profile_id)
            .filter(VideoWatchlistEntry.user_id == user_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .order_by(desc(VideoWatchlistEntry.created_at))
            .all()
        )

    def list_bookmarked_video_ids(self, *, user_id: str, video_ids: List[int]) -> Set[int]:
        if not video_ids:
            return set()
        rows = (
            self.session.query(VideoWatchlistEntry.video_candidate_id)
            .filter(
                VideoWatchlistEntry.user_id == user_id,
                VideoWatchlistEntry.video_candidate_id.in_(video_ids),
            )
            .all()
        )
        return {video_id for (video_id,) in rows}

    def add(self, *, user_id: str, video_candidate_id: int) -> bool:
        existing = (
            self.session.query(VideoWatchlistEntry)
            .filter(
                VideoWatchlistEntry.user_id == user_id,
                VideoWatchlistEntry.video_candidate_id == video_candidate_id,
            )
            .one_or_none()
        )
        if existing is not None:
            return False
        entry = VideoWatchlistEntry(
            user_id=user_id,
            video_candidate_id=video_candidate_id,
        )
        self.session.add(entry)
        self.session.commit()
        return True

    def remove(self, *, user_id: str, video_candidate_id: int) -> bool:
        existing = (
            self.session.query(VideoWatchlistEntry)
            .filter(
                VideoWatchlistEntry.user_id == user_id,
                VideoWatchlistEntry.video_candidate_id == video_candidate_id,
            )
            .one_or_none()
        )
        if existing is None:
            return False
        self.session.delete(existing)
        self.session.commit()
        return True
