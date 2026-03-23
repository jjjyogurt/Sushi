from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.enums import AnalysisStatus, QueueState
from app.repositories.audit_repository import AuditRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.services.gemini_client import GeminiClient
from app.services.transcript_service import TranscriptService
from app.utils.json_codec import encode_json


class AnalysisService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.audit_repository = AuditRepository(session)
        self.analysis_repository = AnalysisRepository(session)
        self.video_repository = VideoRepository(session)
        self.monitor_repository = MonitorRepository(session)
        self.gemini_client = GeminiClient(self.settings)
        self.transcript_service = TranscriptService()

    def analyze_video(self, *, video_id: int, force_reanalyze: bool = False):
        candidate = self.video_repository.get_by_id(video_id)
        if candidate is None:
            raise ValueError("Video not found.")
        if candidate.queue_state != QueueState.APPROVED:
            raise ValueError("Video must be approved before analysis.")

        if not force_reanalyze:
            existing = self.analysis_repository.get_completed_by_version(
                video_candidate_id=video_id,
                analysis_version=self.settings.analysis_version,
            )
            if existing:
                self.audit_repository.record(
                    actor="system",
                    action="analysis_skipped_cached",
                    resource_type="video_candidate",
                    resource_id=str(video_id),
                    details=f"analysis_version={self.settings.analysis_version}",
                )
                return existing

        result = self.analysis_repository.create_queued(
            video_candidate_id=video_id,
            analysis_version=self.settings.analysis_version,
            model_name=self.settings.gemini_model_analysis,
        )

        try:
            result.status = AnalysisStatus.PROCESSING
            self.analysis_repository.save(result)

            profile = self.monitor_repository.get(candidate.monitor_profile_id)
            brand_keywords = self.monitor_repository.unpack_keywords(profile) if profile else []
            preferred_languages = self._preferred_languages(candidate.language)
            transcript = self.transcript_service.fetch_transcript(
                youtube_video_id=candidate.youtube_video_id,
                preferred_languages=preferred_languages,
            )
            output = self.gemini_client.analyze_video(
                title=candidate.title,
                language=candidate.language,
                relevance_reason=candidate.relevance_reason,
                brand_keywords=brand_keywords,
                transcript_text=transcript.full_text,
            )

            result.transcript_text = transcript.full_text
            result.summary_text = output.summary_text
            result.translated_summary = output.translated_summary
            result.sentiment = output.sentiment
            result.risk_level = output.risk_level
            result.confidence_score = f"{output.confidence_score:.2f}"
            result.evidence_json = encode_json(output.evidence)
            result.insights_json = encode_json(output.insights)
            result.status = AnalysisStatus.COMPLETED
            result.error_message = ""
        except Exception as error:  # noqa: BLE001
            result.status = AnalysisStatus.FAILED
            result.error_message = str(error)

        saved = self.analysis_repository.save(result)
        self.audit_repository.record(
            actor="system",
            action="analysis_forced" if force_reanalyze else "analysis_run",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"status={saved.status.value},version={self.settings.analysis_version}",
        )
        return saved

    def _preferred_languages(self, candidate_language: str):
        configured = [item.strip() for item in self.settings.transcript_preferred_languages.split(",") if item.strip()]
        ordered = []
        for item in [candidate_language, self.settings.default_language, *configured]:
            if item and item not in ordered:
                ordered.append(item)
        return ordered

