from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, analysis_id: int) -> Optional[AnalysisResult]:
        return self.session.get(AnalysisResult, analysis_id)

    def get_latest_for_video(self, video_candidate_id: int) -> Optional[AnalysisResult]:
        return (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .order_by(desc(AnalysisResult.created_at))
            .first()
        )

    def get_completed_by_version(
        self, *, video_candidate_id: int, analysis_version: str
    ) -> Optional[AnalysisResult]:
        return (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.analysis_version == analysis_version)
            .filter(AnalysisResult.status == AnalysisStatus.COMPLETED)
            .order_by(desc(AnalysisResult.created_at))
            .first()
        )

    def create_queued(self, *, video_candidate_id: int, analysis_version: str, model_name: str) -> AnalysisResult:
        existing = (
            self.session.query(AnalysisResult)
            .filter(AnalysisResult.video_candidate_id == video_candidate_id)
            .filter(AnalysisResult.analysis_version == analysis_version)
            .one_or_none()
        )
        if existing:
            existing.model_name = model_name
            existing.status = AnalysisStatus.QUEUED
            existing.error_message = ""
            existing.evidence_json = "[]"
            existing.insights_json = "[]"
            self.session.commit()
            self.session.refresh(existing)
            return existing

        result = AnalysisResult(
            video_candidate_id=video_candidate_id,
            analysis_version=analysis_version,
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

