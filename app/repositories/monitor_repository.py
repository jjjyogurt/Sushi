from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.chat import ChatMessage, ChatSession
from app.models.incident import Alert, Incident
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_snapshot import KnowledgeSnapshot
from app.models.knowledge_source import KnowledgeSource
from app.models.monitor_profile import MonitorProfile
from app.models.project_insight_report import ProjectInsightReport
from app.models.video_candidate import VideoCandidate
from app.models.video_comment import VideoComment
from app.models.video_watchlist_entry import VideoWatchlistEntry
from app.schemas.monitor import MonitorProfileCreate, MonitorProfileUpdate
from app.utils.json_codec import decode_json, encode_json


class MonitorRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: MonitorProfileCreate) -> MonitorProfile:
        profile = MonitorProfile(
            name=payload.name,
            brand_keywords=encode_json(payload.brand_keywords),
            markets=encode_json(payload.markets),
            languages=encode_json(payload.languages),
            key_products=encode_json(payload.key_products),
            alert_sensitivity=payload.alert_sensitivity,
        )
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def update(self, profile_id: int, payload: MonitorProfileUpdate) -> Optional[MonitorProfile]:
        profile = self.get(profile_id)
        if profile is None:
            return None
        profile.name = payload.name
        profile.brand_keywords = encode_json(payload.brand_keywords)
        profile.markets = encode_json(payload.markets)
        profile.languages = encode_json(payload.languages)
        profile.key_products = encode_json(payload.key_products)
        profile.alert_sensitivity = payload.alert_sensitivity
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get(self, profile_id: int) -> Optional[MonitorProfile]:
        return self.session.get(MonitorProfile, profile_id)

    def list_all(self) -> List[MonitorProfile]:
        return self.session.query(MonitorProfile).order_by(MonitorProfile.created_at.desc()).all()

    def list_by_ids(self, profile_ids: List[int]) -> List[MonitorProfile]:
        if not profile_ids:
            return []
        return self.session.query(MonitorProfile).filter(MonitorProfile.id.in_(profile_ids)).all()

    def delete(self, profile_id: int) -> bool:
        profile = self.get(profile_id)
        if profile:
            video_id_rows = (
                self.session.query(VideoCandidate.id)
                .filter(VideoCandidate.monitor_profile_id == profile_id)
                .all()
            )
            video_ids = [int(item.id) for item in video_id_rows]
            if video_ids:
                incident_id_query = self.session.query(Incident.id).filter(Incident.video_candidate_id.in_(video_ids))
                chat_session_id_query = self.session.query(ChatSession.id).filter(ChatSession.video_candidate_id.in_(video_ids))

                self.session.query(Alert).filter(
                    Alert.incident_id.in_(incident_id_query)
                ).delete(synchronize_session=False)
                self.session.query(Incident).filter(
                    Incident.video_candidate_id.in_(video_ids)
                ).delete(synchronize_session=False)
                self.session.query(ChatMessage).filter(
                    ChatMessage.chat_session_id.in_(chat_session_id_query)
                ).delete(synchronize_session=False)
                self.session.query(ChatSession).filter(
                    ChatSession.video_candidate_id.in_(video_ids)
                ).delete(synchronize_session=False)
                self.session.query(VideoWatchlistEntry).filter(
                    VideoWatchlistEntry.video_candidate_id.in_(video_ids)
                ).delete(synchronize_session=False)
                self.session.query(VideoComment).filter(
                    VideoComment.video_candidate_id.in_(video_ids)
                ).delete(synchronize_session=False)
                self.session.query(AnalysisResult).filter(
                    AnalysisResult.video_candidate_id.in_(video_ids)
                ).delete(synchronize_session=False)
                self.session.query(VideoCandidate).filter(
                    VideoCandidate.id.in_(video_ids)
                ).delete(synchronize_session=False)
            self.session.query(ProjectInsightReport).filter(
                ProjectInsightReport.monitor_profile_id == profile_id
            ).delete(synchronize_session=False)

            knowledge_base_ids = [
                item.id
                for item in self.session.query(KnowledgeBase.id).filter(KnowledgeBase.monitor_profile_id == profile_id).all()
            ]
            if knowledge_base_ids:
                self.session.query(KnowledgeChunk).filter(
                    KnowledgeChunk.monitor_profile_id == profile_id
                ).delete(synchronize_session=False)
                self.session.query(KnowledgeSnapshot).filter(
                    KnowledgeSnapshot.monitor_profile_id == profile_id
                ).delete(synchronize_session=False)
                self.session.query(KnowledgeSource).filter(
                    KnowledgeSource.monitor_profile_id == profile_id
                ).delete(synchronize_session=False)
                self.session.query(KnowledgeBase).filter(
                    KnowledgeBase.monitor_profile_id == profile_id
                ).delete(synchronize_session=False)
            self.session.delete(profile)
            self.session.commit()
            return True
        return False

    @staticmethod
    def unpack_keywords(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.brand_keywords, [])

    @staticmethod
    def unpack_markets(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.markets, [])

    @staticmethod
    def unpack_languages(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.languages, [])

    @staticmethod
    def unpack_key_products(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.key_products, [])

