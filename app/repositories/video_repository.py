from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.enums import QueueState
from app.models.video_candidate import VideoCandidate
from app.utils.text import normalize_title, title_fingerprint


class VideoRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, video_id: int) -> Optional[VideoCandidate]:
        return self.session.get(VideoCandidate, video_id)

    def get_by_youtube_id(self, youtube_video_id: str) -> Optional[VideoCandidate]:
        return (
            self.session.query(VideoCandidate)
            .filter(VideoCandidate.youtube_video_id == youtube_video_id)
            .one_or_none()
        )

    def upsert_candidate(
        self,
        *,
        monitor_profile_id: int,
        youtube_video_id: str,
        video_url: str,
        title: str,
        channel_name: str,
        language: str,
        published_at,
        relevance_score: float,
        relevance_reason: str,
    ) -> VideoCandidate:
        existing = self.get_by_youtube_id(youtube_video_id)
        if existing:
            existing.video_url = video_url
            existing.title = title
            existing.normalized_title = normalize_title(title)
            existing.title_fingerprint = title_fingerprint(title)
            existing.channel_name = channel_name
            existing.language = language
            existing.published_at = published_at
            existing.relevance_score = relevance_score
            existing.relevance_reason = relevance_reason
            self.session.commit()
            self.session.refresh(existing)
            return existing

        candidate = VideoCandidate(
            monitor_profile_id=monitor_profile_id,
            youtube_video_id=youtube_video_id,
            video_url=video_url,
            title=title,
            normalized_title=normalize_title(title),
            title_fingerprint=title_fingerprint(title),
            channel_name=channel_name,
            language=language,
            published_at=published_at,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
        )
        self.session.add(candidate)
        self.session.commit()
        self.session.refresh(candidate)
        return candidate

    def update_queue_state(self, video_id: int, approved: bool) -> Optional[VideoCandidate]:
        candidate = self.get_by_id(video_id)
        if candidate is None:
            return None
        candidate.queue_state = QueueState.APPROVED if approved else QueueState.REJECTED
        self.session.commit()
        self.session.refresh(candidate)
        return candidate

    def delete(self, video_id: int) -> bool:
        candidate = self.get_by_id(video_id)
        if candidate is None:
            return False
        self.session.delete(candidate)
        self.session.commit()
        return True

    def list(
        self,
        *,
        monitor_profile_id: Optional[int] = None,
        queue_state: Optional[QueueState] = None,
        title_filter: Optional[str] = None,
    ) -> List[VideoCandidate]:
        query = self.session.query(VideoCandidate)
        if monitor_profile_id is not None:
            query = query.filter(VideoCandidate.monitor_profile_id == monitor_profile_id)
        if queue_state is not None:
            query = query.filter(VideoCandidate.queue_state == queue_state)
        if title_filter:
            query = query.filter(VideoCandidate.normalized_title.contains(normalize_title(title_filter)))
        return query.order_by(desc(VideoCandidate.published_at)).all()

