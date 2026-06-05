import logging
from dataclasses import dataclass
from uuid import uuid4
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.repositories.audit_repository import AuditRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.video_comment_repository import VideoCommentRepository
from app.repositories.video_repository import VideoRepository
from app.services.agent_settings_service import AgentSettingsService
from app.services.gemini_client import GeminiClient
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.exceptions import (
    GeminiConfigurationError,
    GeminiDependencyError,
    GeminiProviderError,
    GeminiResponseError,
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptTranslationError,
    TranscriptUnavailableError,
)
from app.services.transcript_service import TranscriptService
from app.services.youtube_comments_service import YouTubeCommentsService
from app.utils.json_codec import decode_json, encode_json
from app.services.types import AnalysisOutput, CommentsAnalysisOutput

logger = logging.getLogger(__name__)
DEFAULT_ANALYSIS_LANGUAGE = "en"
SUPPORTED_ANALYSIS_LANGUAGES = ("en", "zh-Hans")
TRANSCRIPT_STATUS_AVAILABLE = "available"
TRANSCRIPT_STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TranscriptVariant:
    text: str
    language: str
    source_language: str
    is_translated: bool
    translation_model: str


class AnalysisService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.audit_repository = AuditRepository(session)
        self.analysis_repository = AnalysisRepository(session)
        self.video_repository = VideoRepository(session)
        self.video_comment_repository = VideoCommentRepository(session)
        self.gemini_client = GeminiClient(self.settings)
        self.knowledge_retrieval_service = KnowledgeRetrievalService(session)
        self.transcript_service = TranscriptService()
        self.youtube_comments_service = YouTubeCommentsService()

    def analyze_video(self, *, video_id: int, force_reanalyze: bool = False, knowledge_base_id: Optional[int] = None):
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
        owner_user_id = candidate.monitor_profile.owner_user_id if candidate.monitor_profile else ""
        agent_settings = AgentSettingsService(self.session).get_resolved(user_id=owner_user_id)
        target_languages = self.supported_analysis_languages()
        previous_completed_current_version_by_language: Dict[str, AnalysisResult] = {}
        previous_completed_any_version_by_language: Dict[str, AnalysisResult] = {}
        for language in target_languages:
            existing_current_version = self.analysis_repository.get_completed_by_version(
                video_candidate_id=video_id,
                analysis_version=self.settings.analysis_version,
                language=language,
                agent_settings_hash=agent_settings.settings_hash,
            )
            if existing_current_version:
                previous_completed_current_version_by_language = {
                    **previous_completed_current_version_by_language,
                    language: existing_current_version,
                }
            existing_any_version = self.analysis_repository.get_latest_completed_for_video(
                video_candidate_id=video_id,
                language=language,
            )
            if existing_any_version:
                previous_completed_any_version_by_language = {
                    **previous_completed_any_version_by_language,
                    language: existing_any_version,
                }

        if not force_reanalyze:
            existing_by_language = {}
            for language in target_languages:
                existing = previous_completed_current_version_by_language.get(language)
                if existing:
                    existing_by_language = {
                        **existing_by_language,
                        language: existing,
                    }
            if len(existing_by_language) == len(target_languages):
                logger.info(
                    "analysis cache hit request_id=%s video_id=%s result_ids=%s version=%s",
                    request_id,
                    video_id,
                    {language: result.id for language, result in existing_by_language.items()},
                    self.settings.analysis_version,
                )
                self.audit_repository.record(
                    actor="system",
                    action="analysis_skipped_cached",
                    resource_type="video_candidate",
                    resource_id=str(video_id),
                    details=(
                        f"analysis_version={self.settings.analysis_version},"
                        f"agent_settings_hash={agent_settings.settings_hash},"
                        f"request_id={request_id},cached_result_id={existing_by_language[DEFAULT_ANALYSIS_LANGUAGE].id}"
                    ),
                )
                return existing_by_language[DEFAULT_ANALYSIS_LANGUAGE]

        self.gemini_client.ensure_ready()
        logger.info("analysis preflight ready request_id=%s video_id=%s", request_id, video_id)

        results_by_language: Dict[str, AnalysisResult] = {}
        for language in target_languages:
            queued_result = self.analysis_repository.create_queued(
                video_candidate_id=video_id,
                analysis_version=self.settings.analysis_version,
                model_name=self.settings.gemini_model_analysis,
                language=language,
                agent_settings_hash=agent_settings.settings_hash,
            )
            queued_result.status = AnalysisStatus.PROCESSING
            results_by_language = {
                **results_by_language,
                language: self.analysis_repository.save(queued_result),
            }

        captured_errors: Dict[str, Exception] = {}
        error_codes: Dict[str, str] = {}
        transcript_translation_bundle: Optional[Dict[str, str]] = None
        transcript_translation_error: Optional[TranscriptTranslationError] = None

        preferred_languages = self._preferred_languages(candidate.language)
        logger.info(
            "analysis fetching transcript request_id=%s video_id=%s youtube_video_id=%s preferred_languages=%s",
            request_id,
            video_id,
            candidate.youtube_video_id,
            preferred_languages,
        )
        try:
            transcript = self.transcript_service.fetch_transcript(
                youtube_video_id=candidate.youtube_video_id,
                preferred_languages=preferred_languages,
            )
        except Exception as error:  # noqa: BLE001
            error_code = self._error_code_for_exception(error)
            for language in target_languages:
                result = results_by_language[language]
                self._apply_failed_result_payload(result=result, error=error)
                saved = self.analysis_repository.save(result)
                results_by_language = {
                    **results_by_language,
                    language: saved,
                }
                error_codes = {
                    **error_codes,
                    language: error_code,
                }
                captured_errors = {
                    **captured_errors,
                    language: error,
                }
            logger.exception(
                "analysis transcript failed request_id=%s video_id=%s version=%s error_code=%s error=%s",
                request_id,
                video_id,
                self.settings.analysis_version,
                error_code,
                error,
            )
            raise
        logger.info(
            "analysis transcript ready request_id=%s video_id=%s chars=%s source_language=%s",
            request_id,
            video_id,
            len(transcript.full_text),
            transcript.source_language,
        )
        comments_texts = self._refresh_video_comments(
            video_id=video_id,
            youtube_video_id=candidate.youtube_video_id,
            request_id=request_id,
        )
        knowledge_context = self._resolve_knowledge_context(
            monitor_profile_id=candidate.monitor_profile_id,
            title=candidate.title,
            relevance_reason=candidate.relevance_reason,
            transcript_text=transcript.full_text,
            knowledge_base_id=knowledge_base_id,
        )

        english_result = results_by_language[DEFAULT_ANALYSIS_LANGUAGE]
        try:
            logger.info(
                "analysis invoking gemini request_id=%s video_id=%s model=%s language=%s",
                request_id,
                video_id,
                self.settings.gemini_model_analysis,
                DEFAULT_ANALYSIS_LANGUAGE,
            )
            english_output = self.gemini_client.analyze_video(
                title=candidate.title,
                source_language=transcript.source_language,
                target_output_language=DEFAULT_ANALYSIS_LANGUAGE,
                relevance_reason=candidate.relevance_reason,
                transcript_text=transcript.full_text,
                knowledge_context=knowledge_context,
                agent_instructions=agent_settings.content,
            )
            english_comments = self.gemini_client.analyze_comments(
                title=candidate.title,
                language=DEFAULT_ANALYSIS_LANGUAGE,
                comments=comments_texts,
            )
            translation_targets = self._transcript_translation_targets(
                source_language=transcript.source_language,
                target_languages=target_languages,
            )
            if translation_targets:
                try:
                    transcript_translation_bundle = self.gemini_client.translate_transcript_bundle(
                        transcript_text=transcript.full_text,
                        source_language=(
                            self.normalize_transcript_language(transcript.source_language)
                            or transcript.source_language
                        ),
                    )
                except Exception as error:  # noqa: BLE001
                    transcript_translation_error = self._transcript_translation_error(
                        error=error,
                        source_language=transcript.source_language,
                        target_language=", ".join(translation_targets),
                    )
                    logger.exception(
                        "analysis optional transcript translation failed request_id=%s video_id=%s version=%s source_language=%s target_language=%s error=%s",
                        request_id,
                        video_id,
                        self.settings.analysis_version,
                        transcript.source_language,
                        ", ".join(translation_targets),
                        transcript_translation_error,
                    )
            english_transcript, english_transcript_error = self._build_transcript_variant_or_error(
                transcript_text=transcript.full_text,
                source_language=transcript.source_language,
                target_language=DEFAULT_ANALYSIS_LANGUAGE,
                translation_bundle=transcript_translation_bundle,
                translation_error=transcript_translation_error,
            )
            transcript_variant = english_transcript or self._unavailable_transcript_variant(
                source_language=transcript.source_language,
                target_language=DEFAULT_ANALYSIS_LANGUAGE,
            )
            self._apply_success_result_payload(
                result=english_result,
                transcript_text=english_transcript.text if english_transcript else "",
                transcript_variant=transcript_variant,
                output=english_output,
                comments_analysis=english_comments,
            )
            if english_transcript_error is not None:
                self._apply_unavailable_transcript_payload(
                    result=english_result,
                    transcript_variant=transcript_variant,
                    error=english_transcript_error,
                )
            error_codes = {
                **error_codes,
                DEFAULT_ANALYSIS_LANGUAGE: (
                    self._error_code_for_exception(english_transcript_error)
                    if english_transcript_error is not None
                    else "none"
                ),
            }
        except Exception as error:  # noqa: BLE001
            error_code = self._error_code_for_exception(error)
            fallback_candidate = previous_completed_any_version_by_language.get(DEFAULT_ANALYSIS_LANGUAGE)
            if self._is_location_restricted_error(error) and fallback_candidate is not None:
                self._copy_analysis_payload(source=fallback_candidate, target=english_result)
                english_result.status = AnalysisStatus.COMPLETED
                english_result.error_message = ""
                error_code = "GEMINI_LOCATION_RESTRICTED_FALLBACK"
                logger.warning(
                    "analysis location restricted; reused previous result request_id=%s video_id=%s language=%s fallback_result_id=%s",
                    request_id,
                    video_id,
                    DEFAULT_ANALYSIS_LANGUAGE,
                    fallback_candidate.id,
                )
            else:
                captured_errors = {
                    **captured_errors,
                    DEFAULT_ANALYSIS_LANGUAGE: error,
                }
                self._apply_failed_result_payload(result=english_result, error=error)
                logger.exception(
                    "analysis failed request_id=%s video_id=%s version=%s language=%s error_code=%s error=%s",
                    request_id,
                    video_id,
                    self.settings.analysis_version,
                    DEFAULT_ANALYSIS_LANGUAGE,
                    error_code,
                    error,
                )
            error_codes = {
                **error_codes,
                DEFAULT_ANALYSIS_LANGUAGE: error_code,
            }

        saved_english = self.analysis_repository.save(english_result)
        results_by_language = {
            **results_by_language,
            DEFAULT_ANALYSIS_LANGUAGE: saved_english,
        }
        logger.info(
            "analysis persisted request_id=%s video_id=%s result_id=%s status=%s version=%s language=%s error_code=%s",
            request_id,
            video_id,
            saved_english.id,
            saved_english.status.value,
            self.settings.analysis_version,
            DEFAULT_ANALYSIS_LANGUAGE,
            error_codes.get(DEFAULT_ANALYSIS_LANGUAGE, "none"),
        )

        zh_language = "zh-Hans"
        zh_result = results_by_language[zh_language]
        if saved_english.status == AnalysisStatus.COMPLETED:
            zh_transcript, zh_transcript_error = self._build_transcript_variant_or_error(
                transcript_text=transcript.full_text,
                source_language=transcript.source_language,
                target_language=zh_language,
                translation_bundle=transcript_translation_bundle,
                translation_error=transcript_translation_error,
            )

            try:
                english_analysis_output = self._analysis_output_from_result(saved_english)
                english_comments_output = self._comments_output_from_result(saved_english)
                zh_output, zh_comments = self.gemini_client.translate_analysis_bundle(
                    analysis_output=english_analysis_output,
                    comments_output=english_comments_output,
                    target_output_language=zh_language,
                )
                transcript_variant = zh_transcript or self._unavailable_transcript_variant(
                    source_language=transcript.source_language,
                    target_language=zh_language,
                )
                self._apply_success_result_payload(
                    result=zh_result,
                    transcript_text=zh_transcript.text if zh_transcript else "",
                    transcript_variant=transcript_variant,
                    output=zh_output,
                    comments_analysis=zh_comments,
                )
                if zh_transcript_error is not None:
                    self._apply_unavailable_transcript_payload(
                        result=zh_result,
                        transcript_variant=transcript_variant,
                        error=zh_transcript_error,
                    )
                error_codes = {
                    **error_codes,
                    zh_language: (
                        self._error_code_for_exception(zh_transcript_error)
                        if zh_transcript_error is not None
                        else "none"
                    ),
                }
            except Exception as error:  # noqa: BLE001
                zh_error = error
                error_code = self._error_code_for_exception(zh_error)
                fallback_candidate = previous_completed_any_version_by_language.get(zh_language)
                if (
                    not isinstance(zh_error, TranscriptTranslationError)
                    and self._is_location_restricted_error(error)
                    and fallback_candidate is not None
                ):
                    self._copy_analysis_payload(source=fallback_candidate, target=zh_result)
                    zh_result.status = AnalysisStatus.COMPLETED
                    zh_result.error_message = ""
                    error_code = "GEMINI_LOCATION_RESTRICTED_FALLBACK"
                else:
                    captured_errors = {
                        **captured_errors,
                        zh_language: zh_error,
                    }
                    self._apply_failed_result_payload(result=zh_result, error=zh_error)
                    logger.exception(
                        "analysis translation failed request_id=%s video_id=%s version=%s language=%s error_code=%s error=%s",
                        request_id,
                        video_id,
                        self.settings.analysis_version,
                        zh_language,
                        error_code,
                        zh_error,
                    )
                error_codes = {
                    **error_codes,
                    zh_language: error_code,
                }
        else:
            self._apply_failed_result_payload(
                result=zh_result,
                error=RuntimeError("English analysis unavailable; skipped translation."),
            )
            error_codes = {
                **error_codes,
                zh_language: "UPSTREAM_ENGLISH_FAILED",
            }

        saved_zh = self.analysis_repository.save(zh_result)
        results_by_language = {
            **results_by_language,
            zh_language: saved_zh,
        }
        logger.info(
            "analysis persisted request_id=%s video_id=%s result_id=%s status=%s version=%s language=%s error_code=%s",
            request_id,
            video_id,
            saved_zh.id,
            saved_zh.status.value,
            self.settings.analysis_version,
            zh_language,
            error_codes.get(zh_language, "none"),
        )

        status_by_language = {
            language: result.status.value for language, result in results_by_language.items()
        }
        error_codes_text = ",".join(
            [f"{language}:{error_codes.get(language, 'none')}" for language in target_languages]
        )
        status_text = ",".join([f"{language}:{status_by_language.get(language, 'unknown')}" for language in target_languages])
        self.audit_repository.record(
            actor="system",
            action="analysis_forced" if force_reanalyze else "analysis_run",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=(
                f"status={status_text},version={self.settings.analysis_version},"
                f"agent_settings_hash={agent_settings.settings_hash},"
                f"error_code={error_codes_text},request_id={request_id}"
            ),
        )

        default_result = results_by_language.get(DEFAULT_ANALYSIS_LANGUAGE)
        if default_result and default_result.status == AnalysisStatus.COMPLETED:
            return default_result

        if DEFAULT_ANALYSIS_LANGUAGE in captured_errors:
            raise captured_errors[DEFAULT_ANALYSIS_LANGUAGE]
        if captured_errors:
            first_error = next(iter(captured_errors.values()))
            raise first_error
        if default_result:
            return default_result
        raise ValueError("Analysis result unavailable.")

    @staticmethod
    def supported_analysis_languages():
        return SUPPORTED_ANALYSIS_LANGUAGES

    @staticmethod
    def normalize_analysis_language(language: Optional[str]) -> str:
        if language is None:
            return DEFAULT_ANALYSIS_LANGUAGE
        normalized = str(language).strip()
        if not normalized:
            return DEFAULT_ANALYSIS_LANGUAGE
        if normalized.lower() == "en":
            return "en"
        if normalized.lower() in {"zh-hans", "zh", "zh-cn", "zh_cn"}:
            return "zh-Hans"
        raise ValueError("Unsupported analysis language. Allowed: en, zh-Hans.")

    @staticmethod
    def normalize_transcript_language(language: Optional[str]) -> str:
        normalized = str(language or "").strip()
        if not normalized:
            return ""
        lowered = normalized.lower().replace("_", "-")
        if lowered in {"en", "eng"} or lowered.startswith("en-"):
            return "en"
        if lowered in {"zh", "zh-hans", "zh-cn", "cmn", "chinese"} or lowered.startswith("zh-"):
            return "zh-Hans"
        return lowered

    def _transcript_translation_targets(self, *, source_language: str, target_languages: tuple[str, ...]) -> tuple[str, ...]:
        normalized_source = self.normalize_transcript_language(source_language)
        targets = []
        for language in target_languages:
            normalized_target = self.normalize_analysis_language(language)
            if normalized_target != normalized_source:
                targets = [*targets, normalized_target]
        return tuple(targets)

    def _build_transcript_variant_or_error(
        self,
        *,
        transcript_text: str,
        source_language: str,
        target_language: str,
        translation_bundle: Optional[Dict[str, str]],
        translation_error: Optional[Exception],
    ) -> Tuple[Optional[TranscriptVariant], Optional[TranscriptTranslationError]]:
        normalized_source = self.normalize_transcript_language(source_language)
        normalized_target = self.normalize_analysis_language(target_language)
        if normalized_source == normalized_target:
            return (
                TranscriptVariant(
                    text=transcript_text,
                    language=normalized_target,
                    source_language=normalized_source,
                    is_translated=False,
                    translation_model="",
                ),
                None,
            )
        if translation_error is not None:
            return (
                None,
                self._transcript_translation_error(
                    error=translation_error,
                    source_language=normalized_source or source_language,
                    target_language=normalized_target,
                ),
            )
        try:
            return (
                self._build_transcript_variant(
                    transcript_text=transcript_text,
                    source_language=source_language,
                    target_language=target_language,
                    translation_bundle=translation_bundle,
                ),
                None,
            )
        except Exception as error:  # noqa: BLE001
            return (
                None,
                self._transcript_translation_error(
                    error=error,
                    source_language=normalized_source or source_language,
                    target_language=normalized_target,
                ),
            )

    def _build_transcript_variant(
        self,
        *,
        transcript_text: str,
        source_language: str,
        target_language: str,
        translation_bundle: Optional[Dict[str, str]] = None,
    ) -> TranscriptVariant:
        normalized_source = self.normalize_transcript_language(source_language)
        normalized_target = self.normalize_analysis_language(target_language)
        if normalized_source == normalized_target:
            return TranscriptVariant(
                text=transcript_text,
                language=normalized_target,
                source_language=normalized_source,
                is_translated=False,
                translation_model="",
            )
        try:
            if translation_bundle is None:
                raise GeminiResponseError("Transcript translation bundle was not generated.")
            translated = str(translation_bundle.get(normalized_target) or "").strip()
            if not translated:
                raise GeminiResponseError(f"Transcript translation bundle missing {normalized_target}.")
        except Exception as error:  # noqa: BLE001
            raise self._transcript_translation_error(
                error=error,
                source_language=normalized_source or source_language,
                target_language=normalized_target,
            ) from error
        return TranscriptVariant(
            text=translated,
            language=normalized_target,
            source_language=normalized_source,
            is_translated=True,
            translation_model=self.settings.gemini_model_analysis,
        )

    def _unavailable_transcript_variant(
        self,
        *,
        source_language: str,
        target_language: str,
    ) -> TranscriptVariant:
        normalized_source = self.normalize_transcript_language(source_language)
        normalized_target = self.normalize_analysis_language(target_language)
        is_translated = normalized_source != normalized_target
        return TranscriptVariant(
            text="",
            language=normalized_target,
            source_language=normalized_source,
            is_translated=is_translated,
            translation_model=self.settings.gemini_model_analysis if is_translated else "",
        )

    @staticmethod
    def _transcript_translation_error(
        *,
        error: Exception,
        source_language: str,
        target_language: str,
    ) -> TranscriptTranslationError:
        if isinstance(error, TranscriptTranslationError):
            return error
        return TranscriptTranslationError(
            "TRANSCRIPT_TRANSLATION_FAILED: "
            f"Could not translate transcript from {source_language or 'unknown'} to {target_language}: {error}"
        )

    @staticmethod
    def _apply_failed_result_payload(*, result, error: Exception) -> None:
        # Keep failed reruns clean so stale data from prior runs never appears.
        result.transcript_text = ""
        result.transcript_language = ""
        result.transcript_source_language = ""
        result.transcript_is_translated = False
        result.transcript_translation_model = ""
        result.transcript_status = ""
        result.transcript_error_message = ""
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
        result.evidence_json = "[]"
        result.insights_json = "{}"
        result.status = AnalysisStatus.FAILED
        result.error_message = str(error)

    @staticmethod
    def _apply_success_result_payload(
        *,
        result,
        transcript_text: str,
        output: AnalysisOutput,
        comments_analysis: CommentsAnalysisOutput,
        transcript_variant: Optional[TranscriptVariant] = None,
    ) -> None:
        result.transcript_text = transcript_text
        result.transcript_language = transcript_variant.language if transcript_variant else ""
        result.transcript_source_language = transcript_variant.source_language if transcript_variant else ""
        result.transcript_is_translated = transcript_variant.is_translated if transcript_variant else False
        result.transcript_translation_model = transcript_variant.translation_model if transcript_variant else ""
        result.transcript_status = TRANSCRIPT_STATUS_AVAILABLE if transcript_text.strip() else ""
        result.transcript_error_message = ""
        result.summary_text = output.summary_text
        result.translated_summary = output.translated_summary
        result.summary_headline = output.summary_headline
        result.summary_body = output.summary_body
        result.comment_summary_text = comments_analysis.summary
        result.comment_highlights_json = encode_json(comments_analysis.highlights)
        result.comment_lowlights_json = encode_json(comments_analysis.lowlights)
        result.sentiment = output.sentiment
        result.risk_level = output.risk_level
        result.confidence_score = f"{output.confidence_score:.2f}"
        result.evidence_json = encode_json(output.evidence)
        result.insights_json = encode_json(
            {
                "insights": output.insights,
                "praise_points": output.praise_points,
                "criticism_points": output.criticism_points,
                "audience_profiles": output.audience_profiles,
                "usage_scenarios": output.usage_scenarios,
                "action_recommendation": output.action_recommendation,
            }
        )
        result.status = AnalysisStatus.COMPLETED
        result.error_message = ""

    @staticmethod
    def _apply_unavailable_transcript_payload(
        *,
        result,
        transcript_variant: TranscriptVariant,
        error: Exception,
    ) -> None:
        result.transcript_text = ""
        result.transcript_language = transcript_variant.language
        result.transcript_source_language = transcript_variant.source_language
        result.transcript_is_translated = transcript_variant.is_translated
        result.transcript_translation_model = transcript_variant.translation_model
        result.transcript_status = TRANSCRIPT_STATUS_UNAVAILABLE
        result.transcript_error_message = str(error)

    @staticmethod
    def _analysis_output_from_result(result: AnalysisResult) -> AnalysisOutput:
        insights_payload = decode_json(result.insights_json, {})
        insights = []
        praise_points = []
        criticism_points = []
        audience_profiles = []
        usage_scenarios = []
        action_recommendation = ""
        if isinstance(insights_payload, dict):
            raw_insights = insights_payload.get("insights", [])
            raw_praise = insights_payload.get("praise_points", [])
            raw_criticism = insights_payload.get("criticism_points", [])
            raw_audience_profiles = insights_payload.get("audience_profiles", [])
            raw_usage_scenarios = insights_payload.get("usage_scenarios", [])
            insights = [str(item).strip() for item in raw_insights if str(item).strip()] if isinstance(raw_insights, list) else []
            praise_points = [str(item).strip() for item in raw_praise if str(item).strip()] if isinstance(raw_praise, list) else []
            criticism_points = (
                [str(item).strip() for item in raw_criticism if str(item).strip()]
                if isinstance(raw_criticism, list)
                else []
            )
            audience_profiles = AnalysisService._normalize_audience_profiles(raw_audience_profiles)
            usage_scenarios = AnalysisService._normalize_usage_scenarios(raw_usage_scenarios)
            action_recommendation = str(insights_payload.get("action_recommendation", "")).strip()
        return AnalysisOutput(
            transcript_text=result.transcript_text,
            summary_text=result.summary_text,
            translated_summary=result.translated_summary,
            summary_headline=result.summary_headline,
            summary_body=result.summary_body,
            sentiment=result.sentiment,
            risk_level=result.risk_level,
            confidence_score=float(result.confidence_score or "0"),
            evidence=decode_json(result.evidence_json, []),
            insights=insights,
            praise_points=praise_points,
            criticism_points=criticism_points,
            audience_profiles=audience_profiles,
            usage_scenarios=usage_scenarios,
            action_recommendation=action_recommendation,
        )

    @staticmethod
    def _comments_output_from_result(result: AnalysisResult) -> CommentsAnalysisOutput:
        highlights = decode_json(result.comment_highlights_json, [])
        lowlights = decode_json(result.comment_lowlights_json, [])
        return CommentsAnalysisOutput(
            summary=result.comment_summary_text,
            highlights=AnalysisService._normalize_comment_points(highlights),
            lowlights=AnalysisService._normalize_comment_points(lowlights),
        )

    @staticmethod
    def _copy_analysis_payload(*, source: AnalysisResult, target: AnalysisResult) -> None:
        target.transcript_text = source.transcript_text
        target.transcript_language = source.transcript_language
        target.transcript_source_language = source.transcript_source_language
        target.transcript_is_translated = source.transcript_is_translated
        target.transcript_translation_model = source.transcript_translation_model
        target.transcript_status = source.transcript_status
        target.transcript_error_message = source.transcript_error_message
        target.summary_text = source.summary_text
        target.translated_summary = source.translated_summary
        target.summary_headline = source.summary_headline
        target.summary_body = source.summary_body
        target.comment_summary_text = source.comment_summary_text
        target.comment_highlights_json = source.comment_highlights_json
        target.comment_lowlights_json = source.comment_lowlights_json
        target.sentiment = source.sentiment
        target.risk_level = source.risk_level
        target.confidence_score = source.confidence_score
        target.evidence_json = source.evidence_json
        target.insights_json = source.insights_json

    @staticmethod
    def _normalize_comment_points(raw_points):
        if not isinstance(raw_points, list):
            return []
        normalized = []
        for item in raw_points:
            if isinstance(item, dict):
                point = str(item.get("point", "")).strip()
                quote = str(item.get("quote", "")).strip()
                if not point and quote:
                    point = quote
                if not point:
                    continue
                normalized = [*normalized, {"point": point, "quote": quote}]
                continue
            fallback_point = str(item).strip()
            if fallback_point:
                normalized = [*normalized, {"point": fallback_point, "quote": ""}]
        return normalized[:3]

    @staticmethod
    def _normalize_audience_profiles(raw_profiles):
        if not isinstance(raw_profiles, list):
            return []
        normalized = []
        for item in raw_profiles:
            if not isinstance(item, dict):
                continue
            profile_type = str(item.get("type") or "").strip()
            description = str(item.get("description") or "").strip()
            if profile_type and description:
                normalized = [*normalized, {"type": profile_type, "description": description}]
        return normalized[:3]

    @staticmethod
    def _normalize_usage_scenarios(raw_scenarios):
        if not isinstance(raw_scenarios, list):
            return []
        cleaned = [item for item in [str(raw).strip() for raw in raw_scenarios] if item]
        return cleaned[:4]

    @staticmethod
    def _is_location_restricted_error(error: Exception) -> bool:
        message = str(error or "").lower()
        return "user location is not supported" in message

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
        if isinstance(error, TranscriptTranslationError):
            return "TRANSCRIPT_TRANSLATION_FAILED"
        return "ANALYSIS_ERROR"

    def _resolve_knowledge_context(
        self,
        *,
        monitor_profile_id: int,
        title: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_base_id: Optional[int],
    ) -> str:
        query_text = "\n".join([title, relevance_reason, transcript_text[:1200]])
        try:
            return self.knowledge_retrieval_service.build_knowledge_context(
                monitor_profile_id=monitor_profile_id,
                query_text=query_text,
                knowledge_base_id=knowledge_base_id,
                max_chunks=8,
                max_chars=7000,
            )
        except ValueError:
            return ""

    def _refresh_video_comments(self, *, video_id: int, youtube_video_id: str, request_id: str):
        try:
            comments = self.youtube_comments_service.fetch_all_comments(youtube_video_id=youtube_video_id)
            stored_count = self.video_comment_repository.replace_for_video(video_candidate_id=video_id, comments=comments)
            logger.info(
                "analysis comments synced request_id=%s video_id=%s youtube_video_id=%s fetched=%s",
                request_id,
                video_id,
                youtube_video_id,
                stored_count,
            )
        except Exception as error:  # noqa: BLE001
            self.session.rollback()
            logger.warning(
                "analysis comments sync failed request_id=%s video_id=%s youtube_video_id=%s error=%s",
                request_id,
                video_id,
                youtube_video_id,
                error,
            )
        try:
            return self.video_comment_repository.list_texts_for_video(video_candidate_id=video_id, max_items=5000)
        except Exception as error:  # noqa: BLE001
            self.session.rollback()
            logger.warning(
                "analysis comments read failed request_id=%s video_id=%s youtube_video_id=%s error=%s",
                request_id,
                video_id,
                youtube_video_id,
                error,
            )
            return []
