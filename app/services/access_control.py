from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.analysis_batch import AnalysisBatch
from app.models.incident import Alert, Incident
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate


class AccessControlService:
    def __init__(self, session: Session):
        self.session = session

    def require_profile_owner(self, *, monitor_profile_id: int, user_id: str) -> MonitorProfile:
        profile = (
            self.session.query(MonitorProfile)
            .filter(MonitorProfile.id == monitor_profile_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .one_or_none()
        )
        if profile is None:
            raise ValueError("Monitor profile not found.")
        return profile

    def require_video_owner(self, *, video_id: int, user_id: str) -> VideoCandidate:
        video = (
            self.session.query(VideoCandidate)
            .join(MonitorProfile, MonitorProfile.id == VideoCandidate.monitor_profile_id)
            .filter(VideoCandidate.id == video_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .one_or_none()
        )
        if video is None:
            raise ValueError("Video not found.")
        return video

    def require_knowledge_base_owner(self, *, knowledge_base_id: int, user_id: str) -> KnowledgeBase:
        model = (
            self.session.query(KnowledgeBase)
            .join(MonitorProfile, MonitorProfile.id == KnowledgeBase.monitor_profile_id)
            .filter(KnowledgeBase.id == knowledge_base_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .one_or_none()
        )
        if model is None:
            raise ValueError("Knowledge base not found.")
        return model

    def require_knowledge_source_owner(self, *, source_id: int, user_id: str) -> KnowledgeSource:
        model = (
            self.session.query(KnowledgeSource)
            .join(MonitorProfile, MonitorProfile.id == KnowledgeSource.monitor_profile_id)
            .filter(KnowledgeSource.id == source_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .one_or_none()
        )
        if model is None:
            raise ValueError("Knowledge source not found.")
        return model

    def require_batch_owner(self, *, batch_id: int, user_id: str) -> AnalysisBatch:
        batch = self.session.get(AnalysisBatch, batch_id)
        if batch is None:
            raise ValueError("Analysis batch not found.")
        if batch.monitor_profile_id is None:
            if batch.created_by != user_id:
                raise ValueError("Analysis batch not found.")
            return batch
        self.require_profile_owner(monitor_profile_id=batch.monitor_profile_id, user_id=user_id)
        return batch

    def owned_profile_ids(self, *, user_id: str) -> List[int]:
        rows = (
            self.session.query(MonitorProfile.id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .all()
        )
        return [int(row[0]) for row in rows]

    def alert_query_for_user(self, *, user_id: str):
        return (
            self.session.query(Alert)
            .join(Incident, Incident.id == Alert.incident_id)
            .join(VideoCandidate, VideoCandidate.id == Incident.video_candidate_id)
            .join(MonitorProfile, MonitorProfile.id == VideoCandidate.monitor_profile_id)
            .filter(MonitorProfile.owner_user_id == user_id)
        )

    def user_owns_profile(self, *, monitor_profile_id: Optional[int], user_id: str) -> bool:
        if monitor_profile_id is None:
            return True
        return (
            self.session.query(MonitorProfile.id)
            .filter(MonitorProfile.id == monitor_profile_id)
            .filter(MonitorProfile.owner_user_id == user_id)
            .first()
            is not None
        )
