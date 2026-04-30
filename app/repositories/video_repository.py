from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.video_watchlist_entry import VideoWatchlistEntry
from app.models.analysis_batch import AnalysisBatchItem
from app.models.analysis_result import AnalysisResult
from app.models.chat import ChatMessage, ChatSession
from app.models.enums import QueueState
from app.models.incident import Alert, Incident
from app.models.video_candidate import VideoCandidate
from app.models.video_comment import VideoComment
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
        incident_id_query = self.session.query(Incident.id).filter(Incident.video_candidate_id == video_id)
        chat_session_id_query = self.session.query(ChatSession.id).filter(ChatSession.video_candidate_id == video_id)
        self.session.query(Alert).filter(Alert.incident_id.in_(incident_id_query)).delete(synchronize_session=False)
        self.session.query(Incident).filter(Incident.video_candidate_id == video_id).delete(synchronize_session=False)
        self.session.query(ChatMessage).filter(
            ChatMessage.chat_session_id.in_(chat_session_id_query)
        ).delete(synchronize_session=False)
        self.session.query(ChatSession).filter(ChatSession.video_candidate_id == video_id).delete(synchronize_session=False)
        self.session.query(VideoWatchlistEntry).filter(
            VideoWatchlistEntry.video_candidate_id == video_id
        ).delete(synchronize_session=False)
        self.session.query(VideoComment).filter(VideoComment.video_candidate_id == video_id).delete(synchronize_session=False)
        self.session.query(AnalysisResult).filter(AnalysisResult.video_candidate_id == video_id).delete(
            synchronize_session=False
        )
        self.session.query(AnalysisBatchItem).filter(AnalysisBatchItem.video_id == video_id).delete(
            synchronize_session=False
        )
        self.session.delete(candidate)
        self.session.commit()
        return True

    def assign_user(self, *, video_id: int, assigned_user_id: Optional[str], actor: str) -> Optional[VideoCandidate]:
        from datetime import datetime, timezone

        candidate = self.get_by_id(video_id)
        if candidate is None:
            return None
        normalized_user = (assigned_user_id or "").strip()
        candidate.assigned_user_id = normalized_user
        candidate.assigned_by = actor if normalized_user else ""
        candidate.assigned_at = datetime.now(timezone.utc) if normalized_user else None
        self.session.commit()
        self.session.refresh(candidate)
        return candidate

    def list(
        self,
        *,
        monitor_profile_id: Optional[int] = None,
        queue_state: Optional[QueueState] = None,
        risk_level: Optional[str] = None,
        sentiment: Optional[str] = None,
        title_query: Optional[str] = None,
    ) -> List[VideoCandidate]:
        from app.models.analysis_result import AnalysisResult
        from sqlalchemy import and_, func

        # Subquery for the latest analysis timestamp per video.
        latest_analysis_subquery = (
            self.session.query(
                AnalysisResult.video_candidate_id,
                func.max(AnalysisResult.created_at).label("max_created_at"),
            )
            .filter(AnalysisResult.language == "en")
            .group_by(AnalysisResult.video_candidate_id)
            .subquery()
        )

        query = self.session.query(VideoCandidate)

        if risk_level or sentiment:
            query = query.join(
                latest_analysis_subquery,
                latest_analysis_subquery.c.video_candidate_id == VideoCandidate.id,
            ).join(
                AnalysisResult,
                and_(
                    AnalysisResult.video_candidate_id == latest_analysis_subquery.c.video_candidate_id,
                    AnalysisResult.created_at == latest_analysis_subquery.c.max_created_at,
                    AnalysisResult.language == "en",
                ),
            )
            if risk_level:
                query = query.filter(AnalysisResult.risk_level == risk_level.upper())
            if sentiment:
                query = query.filter(AnalysisResult.sentiment == sentiment.upper())

        if monitor_profile_id is not None:
            query = query.filter(VideoCandidate.monitor_profile_id == monitor_profile_id)
        if queue_state is not None:
            query = query.filter(VideoCandidate.queue_state == queue_state)
        if title_query:
            normalized_query = normalize_title(title_query)
            if normalized_query:
                query = query.filter(VideoCandidate.normalized_title.contains(normalized_query))

        return query.order_by(desc(VideoCandidate.published_at)).all()
