import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.enums import AnalysisStatus, QueueState
from app.repositories.audit_repository import AuditRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.services.gemini_client import GeminiClient
from app.services.exceptions import (
    GeminiConfigurationError,
    GeminiDependencyError,
    GeminiProviderError,
    GeminiResponseError,
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptUnavailableError,
)
from app.services.transcript_service import TranscriptService
from app.utils.json_codec import encode_json

logger = logging.getLogger(__name__)


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
        request_id = uuid4().hex[:10]
        logger.info(
            "analysis requested request_id=%s video_id=%s force_reanalyze=%s version=%s model=%s",
            request_id,
            video_id,
            force_reanalyze,
            self.settings.analysis_version,
            self.settings.gemini_model_analysis,
        )
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
                logger.info(
                    "analysis cache hit request_id=%s video_id=%s result_id=%s version=%s",
                    request_id,
                    video_id,
                    existing.id,
                    self.settings.analysis_version,
                )
                self.audit_repository.record(
                    actor="system",
                    action="analysis_skipped_cached",
                    resource_type="video_candidate",
                    resource_id=str(video_id),
                    details=(
                        f"analysis_version={self.settings.analysis_version},"
                        f"request_id={request_id},cached_result_id={existing.id}"
                    ),
                )
                return existing

        self.gemini_client.ensure_ready()
        logger.info("analysis preflight ready request_id=%s video_id=%s", request_id, video_id)

        result = self.analysis_repository.create_queued(
            video_candidate_id=video_id,
            analysis_version=self.settings.analysis_version,
            model_name=self.settings.gemini_model_analysis,
        )

        captured_error = None
        error_code = "none"
        try:
            result.status = AnalysisStatus.PROCESSING
            self.analysis_repository.save(result)

            profile = self.monitor_repository.get(candidate.monitor_profile_id)
            brand_keywords = self.monitor_repository.unpack_keywords(profile) if profile else []
            preferred_languages = self._preferred_languages(candidate.language)
            logger.info(
                "analysis fetching transcript request_id=%s video_id=%s youtube_video_id=%s preferred_languages=%s",
                request_id,
                video_id,
                candidate.youtube_video_id,
                preferred_languages,
            )
            transcript = self.transcript_service.fetch_transcript(
                youtube_video_id=candidate.youtube_video_id,
                preferred_languages=preferred_languages,
            )
            logger.info(
                "analysis transcript ready request_id=%s video_id=%s chars=%s source_language=%s",
                request_id,
                video_id,
                len(transcript.full_text),
                transcript.source_language,
            )
            logger.info(
                "analysis invoking gemini request_id=%s video_id=%s model=%s",
                request_id,
                video_id,
                self.settings.gemini_model_analysis,
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
            captured_error = error
            error_code = self._error_code_for_exception(error)
            result.status = AnalysisStatus.FAILED
            result.error_message = str(error)
            logger.exception(
                "analysis failed request_id=%s video_id=%s version=%s error_code=%s error=%s",
                request_id,
                video_id,
                self.settings.analysis_version,
                error_code,
                error,
            )

        saved = self.analysis_repository.save(result)
        logger.info(
            "analysis persisted request_id=%s video_id=%s result_id=%s status=%s version=%s error_code=%s",
            request_id,
            video_id,
            saved.id,
            saved.status.value,
            self.settings.analysis_version,
            error_code,
        )
        self.audit_repository.record(
            actor="system",
            action="analysis_forced" if force_reanalyze else "analysis_run",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=(
                f"status={saved.status.value},version={self.settings.analysis_version},"
                f"error_code={error_code},request_id={request_id}"
            ),
        )
        if captured_error is not None:
            raise captured_error
        return saved

    def _preferred_languages(self, candidate_language: str):
        configured = [item.strip() for item in self.settings.transcript_preferred_languages.split(",") if item.strip()]
        ordered = []
        for item in [candidate_language, self.settings.default_language, *configured]:
            if item and item not in ordered:
                ordered.append(item)
        return ordered

    @staticmethod
    def _error_code_for_exception(error: Exception) -> str:
        if isinstance(error, (GeminiConfigurationError, GeminiDependencyError)):
            return "GEMINI_NOT_READY"
        if isinstance(error, GeminiProviderError):
            return "GEMINI_PROVIDER_ERROR"
        if isinstance(error, GeminiResponseError):
            return "GEMINI_RESPONSE_ERROR"
        if isinstance(error, TranscriptBlockedError):
            return "TRANSCRIPT_BLOCKED"
        if isinstance(error, TranscriptUnavailableError):
            return "TRANSCRIPT_UNAVAILABLE"
        if isinstance(error, TranscriptProviderError):
            return "TRANSCRIPT_PROVIDER_ERROR"
        return "ANALYSIS_ERROR"

