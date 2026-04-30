from typing import Dict, List, Optional

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, analysis_id: int) -> Optional[AnalysisResult]:
        return self.session.get(AnalysisResult, analysis_id)

    def get_latest_for_video(self, video_candidate_id: int, *, language: str = "en") -> Optional[AnalysisResult]:
        return (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.language == language)
            .order_by(desc(AnalysisResult.created_at))
            .first()
        )

    def get_completed_by_version(
        self, *, video_candidate_id: int, analysis_version: str, language: str
    ) -> Optional[AnalysisResult]:
        return (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.analysis_version == analysis_version)
            .filter(AnalysisResult.language == language)
            .filter(AnalysisResult.status == AnalysisStatus.COMPLETED)
            .order_by(desc(AnalysisResult.created_at))
            .first()
        )

    def get_latest_completed_for_video(
        self, *, video_candidate_id: int, language: str
    ) -> Optional[AnalysisResult]:
        return (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.language == language)
            .filter(AnalysisResult.status == AnalysisStatus.COMPLETED)
            .order_by(desc(AnalysisResult.created_at))
            .first()
        )

    def get_latest_sentiment_by_video_ids(self, video_ids: List[int], *, language: str = "en") -> Dict[int, str]:
        if not video_ids:
            return {}

        latest_subquery = (
            self.session.query(
                AnalysisResult.video_candidate_id.label("video_candidate_id"),
                func.max(AnalysisResult.created_at).label("latest_created_at"),
            )
            .filter(AnalysisResult.video_candidate_id.in_(video_ids))
            .filter(AnalysisResult.language == language)
            .group_by(AnalysisResult.video_candidate_id)
            .subquery()
        )

        latest_rows = (
            self.session.query(AnalysisResult.video_candidate_id, AnalysisResult.sentiment)
            .join(
                latest_subquery,
                and_(
                    AnalysisResult.video_candidate_id == latest_subquery.c.video_candidate_id,
                    AnalysisResult.created_at == latest_subquery.c.latest_created_at,
                ),
            )
            .all()
        )
        return {video_id: sentiment.value for video_id, sentiment in latest_rows if sentiment is not None}

    def get_latest_status_by_video_ids(self, video_ids: List[int], *, language: str = "en") -> Dict[int, str]:
        if not video_ids:
            return {}

        latest_subquery = (
            self.session.query(
                AnalysisResult.video_candidate_id.label("video_candidate_id"),
                func.max(AnalysisResult.created_at).label("latest_created_at"),
            )
            .filter(AnalysisResult.video_candidate_id.in_(video_ids))
            .filter(AnalysisResult.language == language)
            .group_by(AnalysisResult.video_candidate_id)
            .subquery()
        )

        latest_rows = (
            self.session.query(AnalysisResult.video_candidate_id, AnalysisResult.status)
            .join(
                latest_subquery,
                and_(
                    AnalysisResult.video_candidate_id == latest_subquery.c.video_candidate_id,
                    AnalysisResult.created_at == latest_subquery.c.latest_created_at,
                ),
            )
            .all()
        )
        return {video_id: status.value for video_id, status in latest_rows if status is not None}

    def create_queued(
        self,
        *,
        video_candidate_id: int,
        analysis_version: str,
        model_name: str,
        language: str,
    ) -> AnalysisResult:
        existing = (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.analysis_version == analysis_version)
            .filter(AnalysisResult.language == language)
            .one_or_none()
        )
        if existing:
            existing.model_name = model_name
            self._reset_result_payload(existing)
            existing.status = AnalysisStatus.QUEUED
            self.session.commit()
            self.session.refresh(existing)
            return existing

        result = AnalysisResult(
            video_candidate_id=video_candidate_id,
            analysis_version=analysis_version,
            language=language,
            model_name=model_name,
            status=AnalysisStatus.QUEUED,
        )
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def save(self, result: AnalysisResult) -> AnalysisResult:
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    @staticmethod
    def _reset_result_payload(result: AnalysisResult) -> None:
        result.transcript_text = ""
        result.summary_text = ""
        result.translated_summary = ""
        result.summary_headline = ""
        result.summary_body = ""
        result.comment_summary_text = ""
        result.comment_highlights_json = "[]"
        result.comment_lowlights_json = "[]"
        result.sentiment = Sentiment.NEUTRAL
        result.risk_level = RiskLevel.LOW
        result.confidence_score = "0.0"
        result.error_message = ""
        result.evidence_json = "[]"
        result.insights_json = "{}"
