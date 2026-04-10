import json
import logging
import re
from typing import Any, List

from app.config import Settings
from app.models.enums import RiskLevel, Sentiment
from app.services.exceptions import (
    GeminiConfigurationError,
    GeminiDependencyError,
    GeminiProviderError,
    GeminiResponseError,
)
from app.services.agent_settings_service import AgentSettingsService
from app.services.types import AnalysisOutput, ChatOutput, CommentsAnalysisOutput

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.agent_settings_service = AgentSettingsService()

    def analyze_video(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_context: str = "",
    ) -> AnalysisOutput:
        self._ensure_runtime_ready()
        max_transcript_chars = max(1, self.settings.analysis_max_transcript_chars)
        transcript_for_prompt = transcript_text[:max_transcript_chars]
        hard_capped = len(transcript_for_prompt) < len(transcript_text)
        single_pass_threshold = max(1, self.settings.analysis_single_pass_max_estimated_tokens)
        agent_instructions = self._analysis_agent_instructions()
        single_pass_prompt = self._build_analysis_single_pass_prompt(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            transcript_text=transcript_for_prompt,
            agent_instructions=agent_instructions,
            knowledge_context=knowledge_context,
        )
        estimated_tokens = self._estimate_tokens_from_chars(total_chars=len(single_pass_prompt))
        route = "single_pass" if estimated_tokens <= single_pass_threshold else "chunk_reduce"
        logger.info(
            "gemini analysis route selected model=%s route=%s transcript_chars=%s capped_chars=%s estimated_tokens=%s threshold_tokens=%s hard_capped=%s",
            self.settings.gemini_model_analysis,
            route,
            len(transcript_text),
            len(transcript_for_prompt),
            estimated_tokens,
            single_pass_threshold,
            hard_capped,
        )

        if route == "single_pass":
            try:
                raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=single_pass_prompt)
                parsed = self._parse_json_payload(raw=raw, context="analysis single-pass")
                logger.info("gemini analysis single-pass completed model=%s", self.settings.gemini_model_analysis)
                return self._analysis_from_parsed(
                    parsed=parsed,
                    fallback_transcript=transcript_text,
                    target_output_language=target_output_language,
                )
            except GeminiProviderError as error:
                if not self._is_context_oversize_error(error):
                    raise
                logger.warning(
                    "gemini analysis single-pass oversize fallback model=%s estimated_tokens=%s",
                    self.settings.gemini_model_analysis,
                    estimated_tokens,
                )

        return self._analyze_with_chunk_reduce(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            transcript_for_prompt=transcript_for_prompt,
            fallback_transcript=transcript_text,
            knowledge_context=knowledge_context,
            agent_instructions=agent_instructions,
        )

    def ensure_ready(self) -> None:
        self._ensure_runtime_ready()

    def chat_about_video(self, *, context: str, question: str, language: str) -> ChatOutput:
        self._ensure_runtime_ready()
        logger.info(
            "gemini chat request model=%s context_chars=%s question_chars=%s",
            self.settings.gemini_model_chat,
            len(context),
            len(question),
        )
        prompt = self._build_chat_prompt(context=context, question=question, language=language)
        raw = self._generate_text(model_name=self.settings.gemini_model_chat, prompt=prompt)
        parsed = self._parse_json_payload(raw=raw, context="chat response")
        return self._chat_from_parsed(parsed=parsed)

    def analyze_comments(
        self,
        *,
        title: str,
        language: str,
        comments: List[str],
    ) -> CommentsAnalysisOutput:
        self._ensure_runtime_ready()
        cleaned = [text.strip() for text in comments if str(text).strip()]
        if not cleaned:
            return CommentsAnalysisOutput(summary="", highlights=[], lowlights=[])

        max_items = 800
        joined = "\n".join([f"- {item}" for item in cleaned[:max_items]])
        prompt = self._build_comments_sentiment_prompt(title=title, language=language, comments_bullets=joined)
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        parsed = self._parse_json_payload(raw=raw, context="comments sentiment")
        return self._comments_from_parsed(parsed=parsed)

    def translate_analysis_bundle(
        self,
        *,
        analysis_output: AnalysisOutput,
        comments_output: CommentsAnalysisOutput,
        target_output_language: str,
    ) -> tuple[AnalysisOutput, CommentsAnalysisOutput]:
        normalized_target = str(target_output_language or "").strip().lower()
        if normalized_target not in {"en", "zh-hans"}:
            return analysis_output, comments_output
        if normalized_target == "en":
            return analysis_output, comments_output

        translated_fields = self._translate_analysis_text_fields(
            target_output_language=normalized_target,
            summary_text=analysis_output.summary_text,
            translated_summary=analysis_output.translated_summary,
            summary_headline=analysis_output.summary_headline,
            summary_body=analysis_output.summary_body,
            business_impact=analysis_output.business_impact,
            insights=analysis_output.insights,
            praise_points=analysis_output.praise_points,
            criticism_points=analysis_output.criticism_points,
            action_recommendation=analysis_output.action_recommendation,
        )
        translated_comments = self._translate_comments_text_fields(
            target_output_language=normalized_target,
            summary=comments_output.summary,
            highlights=comments_output.highlights,
            lowlights=comments_output.lowlights,
        )

        translated_analysis = AnalysisOutput(
            transcript_text=analysis_output.transcript_text,
            summary_text=translated_fields.get("summary_text", analysis_output.summary_text),
            translated_summary=translated_fields.get("translated_summary", analysis_output.translated_summary),
            summary_headline=translated_fields.get("summary_headline", analysis_output.summary_headline),
            summary_body=translated_fields.get("summary_body", analysis_output.summary_body),
            business_impact=translated_fields.get("business_impact", analysis_output.business_impact),
            sentiment=analysis_output.sentiment,
            risk_level=analysis_output.risk_level,
            confidence_score=analysis_output.confidence_score,
            evidence=analysis_output.evidence,
            insights=translated_fields.get("insights", analysis_output.insights),
            praise_points=translated_fields.get("praise_points", analysis_output.praise_points),
            criticism_points=translated_fields.get("criticism_points", analysis_output.criticism_points),
            action_recommendation=translated_fields.get(
                "action_recommendation",
                analysis_output.action_recommendation,
            ),
        )
        translated_comments_output = CommentsAnalysisOutput(
            summary=translated_comments.get("summary", comments_output.summary),
            highlights=translated_comments.get("highlights", comments_output.highlights),
            lowlights=translated_comments.get("lowlights", comments_output.lowlights),
        )
        return translated_analysis, translated_comments_output

    def health_status(self, *, probe: bool = False) -> dict:
        api_key_configured = bool(self.settings.gemini_api_key.strip())
        sdk_available = self._sdk_available()
        status = {
            "ready": api_key_configured and sdk_available,
            "api_key_configured": api_key_configured,
            "sdk_available": sdk_available,
            "analysis_model": self.settings.gemini_model_analysis,
            "chat_model": self.settings.gemini_model_chat,
        }
        if not probe or not status["ready"]:
            return status

        try:
            probe_raw = self._generate_text(
                model_name=self.settings.gemini_model_chat,
                prompt='Return strict JSON: {"probe_ok": true, "note": "ready"}.',
            )
            parsed = self._parse_json_payload(raw=probe_raw, context="health probe")
            probe_ok = bool(parsed.get("probe_ok"))
            return {**status, "probe_ok": probe_ok}
        except Exception as error:  # noqa: BLE001
            return {**status, "probe_ok": False, "probe_error": str(error)}

    def _analyze_chunk(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        chunk_text: str,
        chunk_index: int,
        total_chunks: int,
        agent_instructions: str,
    ) -> dict:
        prompt = self._build_analysis_chunk_prompt(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            agent_instructions=agent_instructions,
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        logger.debug("gemini analysis chunk completed chunk=%s/%s", chunk_index, total_chunks)
        return self._parse_json_payload(raw=raw, context=f"analysis chunk {chunk_index}")

    def _analyze_with_chunk_reduce(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_for_prompt: str,
        fallback_transcript: str,
        knowledge_context: str,
        agent_instructions: str,
    ) -> AnalysisOutput:
        chunks = self._chunk_transcript(transcript_text=transcript_for_prompt)
        logger.info(
            "gemini analysis chunk-reduce prepared model=%s capped_chars=%s chunk_count=%s",
            self.settings.gemini_model_analysis,
            len(transcript_for_prompt),
            len(chunks),
        )
        chunk_analyses = [
            self._analyze_chunk(
                title=title,
                source_language=source_language,
                target_output_language=target_output_language,
                relevance_reason=relevance_reason,
                chunk_text=chunk_text,
                chunk_index=index + 1,
                total_chunks=len(chunks),
                agent_instructions=agent_instructions,
            )
            for index, chunk_text in enumerate(chunks)
        ]

        reduce_prompt = self._build_analysis_reduce_prompt(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            chunk_analyses=chunk_analyses,
            agent_instructions=agent_instructions,
            knowledge_context=knowledge_context,
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=reduce_prompt)
        parsed = self._parse_json_payload(raw=raw, context="analysis reducer")
        logger.info(
            "gemini analysis reducer completed model=%s chunk_count=%s",
            self.settings.gemini_model_analysis,
            len(chunks),
        )
        return self._analysis_from_parsed(
            parsed=parsed,
            fallback_transcript=fallback_transcript,
            target_output_language=target_output_language,
        )

    def _analysis_agent_instructions(self) -> str:
        try:
            return self.agent_settings_service.get_content()
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to load agent instructions; using defaults. error=%s", error)
            return self.agent_settings_service.default_content()

    def _estimate_tokens_from_chars(self, *, total_chars: int) -> int:
        chars_per_token = max(1, self.settings.analysis_estimated_chars_per_token)
        return max(1, (total_chars + chars_per_token - 1) // chars_per_token)

    def _generate_text(self, *, model_name: str, prompt: str) -> str:
        try:
            import google.generativeai as genai
        except ImportError as error:
            raise GeminiDependencyError("google-generativeai package is required to call Gemini.") from error

        try:
            genai.configure(api_key=self.settings.gemini_api_key)
            model = genai.GenerativeModel(model_name=model_name)
            logger.debug("gemini provider call start model=%s prompt_chars=%s", model_name, len(prompt))
            response = model.generate_content(prompt)
        except Exception as error:  # noqa: BLE001
            raise GeminiProviderError(f"Gemini request failed: {error}") from error

        response_text = getattr(response, "text", "") if response else ""
        if not response_text:
            raise GeminiResponseError("Gemini returned an empty response.")
        logger.debug("gemini provider call done model=%s response_chars=%s", model_name, len(response_text))
        return response_text.strip()

    def _ensure_runtime_ready(self) -> None:
        if not self.settings.gemini_api_key.strip():
            raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")
        if not self._sdk_available():
            raise GeminiDependencyError("google-generativeai package is required to call Gemini.")

    @staticmethod
    def _sdk_available() -> bool:
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return False
        return True

    def _chunk_transcript(self, *, transcript_text: str) -> List[str]:
        normalized_lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]
        if not normalized_lines:
            raise GeminiResponseError("Transcript text is empty; cannot run analysis.")

        max_chars = max(1000, self.settings.analysis_chunk_chars)
        overlap_chars = max(0, self.settings.analysis_chunk_overlap_chars)
        max_chunks = max(1, self.settings.analysis_max_chunks)

        chunks: List[str] = []
        current_lines: List[str] = []
        current_chars = 0

        for line in normalized_lines:
            prospective = current_chars + len(line) + (1 if current_lines else 0)
            if current_lines and prospective > max_chars:
                chunks = [*chunks, "\n".join(current_lines)]
                if len(chunks) >= max_chunks:
                    return chunks

                overlap_lines = self._take_overlap_lines(lines=current_lines, overlap_chars=overlap_chars)
                current_lines = [*overlap_lines, line]
                current_chars = len("\n".join(current_lines))
                continue

            current_lines = [*current_lines, line]
            current_chars = prospective

        if current_lines and len(chunks) < max_chunks:
            chunks = [*chunks, "\n".join(current_lines)]
        return chunks

    @staticmethod
    def _take_overlap_lines(*, lines: List[str], overlap_chars: int) -> List[str]:
        if overlap_chars <= 0:
            return []

        selected: List[str] = []
        total_chars = 0
        for line in reversed(lines):
            additional = len(line) + (1 if selected else 0)
            if selected and (total_chars + additional) > overlap_chars:
                break
            selected = [line, *selected]
            total_chars = total_chars + additional
        return selected

    @staticmethod
    def _parse_json_payload(*, raw: str, context: str) -> dict:
        normalized = raw.strip()
        if normalized.startswith("```"):
            normalized = GeminiClient._extract_fenced_payload(normalized)

        start = normalized.find("{")
        end = normalized.rfind("}")
        if start < 0 or end < 0 or end < start:
            raise GeminiResponseError(f"Gemini {context} output is not valid JSON.")

        candidate = normalized[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as error:
            raise GeminiResponseError(f"Gemini {context} output JSON parse failed: {error}") from error

        if not isinstance(parsed, dict):
            raise GeminiResponseError(f"Gemini {context} output must be a JSON object.")
        return parsed

    @staticmethod
    def _extract_fenced_payload(raw: str) -> str:
        parts = [part.strip() for part in raw.split("```") if part.strip()]
        if not parts:
            return raw

        first = parts[0]
        if first.lower().startswith("json"):
            return first[4:].strip()
        return first

    def _analysis_from_parsed(
        self, *, parsed: dict, fallback_transcript: str, target_output_language: str
    ) -> AnalysisOutput:
        summary_text = str(parsed.get("summary_text", "")).strip()
        if not summary_text:
            raise GeminiResponseError("Gemini analysis output is missing summary_text.")

        translated_summary = str(parsed.get("translated_summary", "")).strip() or summary_text
        summary_headline = str(parsed.get("summary_headline", "")).strip()
        summary_body = str(parsed.get("summary_body", "")).strip()
        business_impact = str(parsed.get("business_impact", "")).strip()
        sentiment = GeminiClient._safe_sentiment(parsed.get("sentiment"))
        risk_level = GeminiClient._safe_risk_level(parsed.get("risk_level"))
        confidence_score = GeminiClient._safe_confidence(parsed.get("confidence_score"), fallback=0.0)
        evidence = GeminiClient._normalize_evidence(parsed.get("evidence"))
        insights = GeminiClient._normalize_insights(parsed.get("insights"))
        praise_points = GeminiClient._normalize_point_list(parsed.get("praise_points"))
        criticism_points = GeminiClient._normalize_point_list(parsed.get("criticism_points"))
        action_recommendation = GeminiClient._normalize_action_recommendation(parsed.get("action_recommendation"))

        normalized_target = str(target_output_language or "").strip().lower()
        text_bundle = "\n".join([summary_text, summary_headline, summary_body, business_impact])
        if self._is_output_language_mismatch(text=text_bundle, target_output_language=normalized_target):
            translated_fields = self._translate_analysis_text_fields(
                target_output_language=normalized_target,
                summary_text=summary_text,
                translated_summary=translated_summary,
                summary_headline=summary_headline,
                summary_body=summary_body,
                business_impact=business_impact,
                insights=insights,
                praise_points=praise_points,
                criticism_points=criticism_points,
                action_recommendation=action_recommendation,
            )
            summary_text = translated_fields.get("summary_text", summary_text)
            translated_summary = translated_fields.get("translated_summary", translated_summary)
            summary_headline = translated_fields.get("summary_headline", summary_headline)
            summary_body = translated_fields.get("summary_body", summary_body)
            business_impact = translated_fields.get("business_impact", business_impact)
            insights = translated_fields.get("insights", insights)
            praise_points = translated_fields.get("praise_points", praise_points)
            criticism_points = translated_fields.get("criticism_points", criticism_points)
            action_recommendation = translated_fields.get("action_recommendation", action_recommendation)

        return AnalysisOutput(
            transcript_text=fallback_transcript,
            summary_text=summary_text,
            translated_summary=translated_summary,
            summary_headline=summary_headline,
            summary_body=summary_body,
            business_impact=business_impact,
            sentiment=sentiment,
            risk_level=risk_level,
            confidence_score=confidence_score,
            evidence=evidence,
            insights=insights,
            praise_points=praise_points,
            criticism_points=criticism_points,
            action_recommendation=action_recommendation,
        )

    def _translate_analysis_text_fields(
        self,
        *,
        target_output_language: str,
        summary_text: str,
        translated_summary: str,
        summary_headline: str,
        summary_body: str,
        business_impact: str,
        insights: List[str],
        praise_points: List[str],
        criticism_points: List[str],
        action_recommendation: str,
    ) -> dict:
        if target_output_language not in {"en", "zh-hans"}:
            return {}
        language_name = "English" if target_output_language == "en" else "Simplified Chinese"
        payload = {
            "summary_text": summary_text,
            "translated_summary": translated_summary,
            "summary_headline": summary_headline,
            "summary_body": summary_body,
            "business_impact": business_impact,
            "insights": insights,
            "praise_points": praise_points,
            "criticism_points": criticism_points,
            "action_recommendation": action_recommendation,
        }
        prompt = (
            "Translate and normalize the following analysis text fields.\n"
            "Return strict JSON with the exact same keys and value shapes.\n"
            f"All text values must be in {language_name}.\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}\n"
        )
        try:
            raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
            parsed = self._parse_json_payload(raw=raw, context="analysis language normalization")
            return {
                "summary_text": str(parsed.get("summary_text", summary_text)).strip() or summary_text,
                "translated_summary": str(parsed.get("translated_summary", translated_summary)).strip()
                or translated_summary,
                "summary_headline": str(parsed.get("summary_headline", summary_headline)).strip() or summary_headline,
                "summary_body": str(parsed.get("summary_body", summary_body)).strip() or summary_body,
                "business_impact": str(parsed.get("business_impact", business_impact)).strip() or business_impact,
                "insights": self._normalize_insights(parsed.get("insights")) or insights,
                "praise_points": self._normalize_point_list(parsed.get("praise_points")) or praise_points,
                "criticism_points": self._normalize_point_list(parsed.get("criticism_points")) or criticism_points,
                "action_recommendation": self._normalize_action_recommendation(
                    parsed.get("action_recommendation")
                )
                or action_recommendation,
            }
        except Exception as error:  # noqa: BLE001
            logger.warning("analysis language normalization failed: %s", error)
            return {}

    def _translate_comments_text_fields(
        self,
        *,
        target_output_language: str,
        summary: str,
        highlights: List[str],
        lowlights: List[str],
    ) -> dict:
        if target_output_language not in {"en", "zh-hans"}:
            return {}
        language_name = "English" if target_output_language == "en" else "Simplified Chinese"
        payload = {
            "summary": summary,
            "highlights": highlights,
            "lowlights": lowlights,
        }
        prompt = (
            "Translate and normalize the following comments-analysis fields.\n"
            "Return strict JSON with the exact same keys and value shapes.\n"
            f"All text values must be in {language_name}.\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}\n"
        )
        try:
            raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
            parsed = self._parse_json_payload(raw=raw, context="comments language normalization")
            return {
                "summary": str(parsed.get("summary", summary)).strip() or summary,
                "highlights": self._normalize_point_list(parsed.get("highlights")) or highlights,
                "lowlights": self._normalize_point_list(parsed.get("lowlights")) or lowlights,
            }
        except Exception as error:  # noqa: BLE001
            logger.warning("comments language normalization failed: %s", error)
            return {}

    @staticmethod
    def _is_output_language_mismatch(*, text: str, target_output_language: str) -> bool:
        if not text.strip():
            return False
        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        if target_output_language == "zh-hans":
            return cjk_count < 3
        if target_output_language == "en":
            return cjk_count >= 3
        return False

    @staticmethod
    def _safe_sentiment(value: Any) -> Sentiment:
        try:
            return Sentiment(str(value).lower())
        except ValueError:
            return Sentiment.NEUTRAL

    @staticmethod
    def _safe_risk_level(value: Any) -> RiskLevel:
        try:
            return RiskLevel(str(value).lower())
        except ValueError:
            return RiskLevel.MEDIUM

    @staticmethod
    def _safe_confidence(value: Any, *, fallback: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return fallback
        if confidence < 0:
            return 0.0
        if confidence > 1:
            return 1.0
        return confidence

    @staticmethod
    def _normalize_evidence(value: Any) -> List[dict]:
        if not isinstance(value, list):
            return []

        normalized: List[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            timestamp = str(item.get("timestamp", "")).strip() or "00:00"
            quote = str(item.get("quote", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if not quote:
                continue
            normalized = [*normalized, {"timestamp": timestamp, "quote": quote, "reason": reason}]
        return normalized

    @staticmethod
    def _normalize_insights(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [item for item in [str(raw).strip() for raw in value] if item]

    @staticmethod
    def _normalize_point_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        cleaned = [item for item in [str(raw).strip() for raw in value] if item]
        return cleaned[:5]

    @staticmethod
    def _normalize_action_recommendation(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _chat_from_parsed(*, parsed: dict) -> ChatOutput:
        content = str(parsed.get("content", "")).strip()
        if not content:
            raise GeminiResponseError("Gemini chat output is missing content.")

        citations = GeminiClient._normalize_citations(parsed.get("citations"))
        confidence_score = GeminiClient._safe_confidence(parsed.get("confidence_score"), fallback=0.0)
        insufficient_evidence = bool(parsed.get("insufficient_evidence", confidence_score < 0.5))
        return ChatOutput(
            content=content,
            citations=citations,
            confidence_score=confidence_score,
            insufficient_evidence=insufficient_evidence,
        )

    @staticmethod
    def _comments_from_parsed(*, parsed: dict) -> CommentsAnalysisOutput:
        summary = str(parsed.get("summary", "")).strip()
        highlights = GeminiClient._normalize_point_list(parsed.get("highlights"))[:3]
        lowlights = GeminiClient._normalize_point_list(parsed.get("lowlights"))[:3]
        return CommentsAnalysisOutput(summary=summary, highlights=highlights, lowlights=lowlights)

    @staticmethod
    def _normalize_citations(value: Any) -> List[dict]:
        if not isinstance(value, list):
            return []

        citations: List[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            timestamp = str(item.get("timestamp", "")).strip() or "00:00"
            quote = str(item.get("quote", "")).strip()
            if not quote:
                continue
            citations = [*citations, {"timestamp": timestamp, "quote": quote}]
        return citations

    @staticmethod
    def _is_context_oversize_error(error: Exception) -> bool:
        error_text = str(error).lower()
        strict_markers = (
            "context",
            "maximum context length",
            "token limit",
            "too many tokens",
            "too large",
            "too long",
            "input token count",
        )
        if any(marker in error_text for marker in strict_markers):
            return True
        return "exceeds" in error_text and ("token" in error_text or "context" in error_text)

    @staticmethod
    def _build_analysis_single_pass_prompt(
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_text: str,
        agent_instructions: str,
        knowledge_context: str,
    ) -> str:
        return (
            "You are analyzing an influencer video transcript for marketing risk monitoring.\n"
            "Follow these AGENTS.md instructions for evaluation style and content priorities:\n"
            f"{agent_instructions}\n"
            "Return strict JSON with keys: summary_text, translated_summary, summary_headline, summary_body, "
            "business_impact, sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "action_recommendation as one short actionable string.\n"
            f"All textual outputs MUST be written in: {target_output_language}.\n"
            "Do not invent evidence. Use only evidence that appears in the transcript for summary, points, and recommendation.\n"
            "Knowledge base context (if provided) can be used to verify product facts, but transcript evidence is still required for claims about this video.\n"
            f"Video title: {title}\n"
            f"Source transcript language: {source_language}\n"
            f"Relevance reason: {relevance_reason}\n"
            f"Knowledge base context:\n{knowledge_context}\n"
            f"Transcript:\n{transcript_text}\n"
        )

    @staticmethod
    def _build_analysis_chunk_prompt(
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        chunk_text: str,
        chunk_index: int,
        total_chunks: int,
        agent_instructions: str,
    ) -> str:
        return (
            "You are analyzing influencer video transcript chunks for marketing risk monitoring.\n"
            "Follow these AGENTS.md instructions for evaluation style and content priorities:\n"
            f"{agent_instructions}\n"
            "Return strict JSON with keys: summary_text, translated_summary, summary_headline, summary_body, "
            "business_impact, sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "action_recommendation as one short actionable string.\n"
            f"All textual outputs MUST be written in: {target_output_language}.\n"
            f"Video title: {title}\n"
            f"Source transcript language: {source_language}\n"
            f"Relevance reason: {relevance_reason}\n"
            f"Chunk: {chunk_index} of {total_chunks}\n"
            "Focus only on this chunk and cite direct transcript snippets. Do not invent claims beyond transcript evidence.\n"
            f"Transcript chunk:\n{chunk_text}\n"
        )

    @staticmethod
    def _build_analysis_reduce_prompt(
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        chunk_analyses: List[dict],
        agent_instructions: str,
        knowledge_context: str,
    ) -> str:
        chunk_json = json.dumps(chunk_analyses, ensure_ascii=True)
        return (
            "You are merging chunk-level transcript analyses into a final decision for marketing risk monitoring.\n"
            "Follow these AGENTS.md instructions for evaluation style and content priorities:\n"
            f"{agent_instructions}\n"
            "Return strict JSON with keys: summary_text, translated_summary, summary_headline, summary_body, "
            "business_impact, sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "action_recommendation as one short actionable string.\n"
            f"All textual outputs MUST be written in: {target_output_language}.\n"
            "Do not invent evidence. Use only evidence that appears in chunk analyses for summary, points, and recommendation.\n"
            "Knowledge base context (if provided) can be used to verify product facts, but transcript evidence is still required for claims about this video.\n"
            f"Video title: {title}\n"
            f"Source transcript language: {source_language}\n"
            f"Relevance reason: {relevance_reason}\n"
            f"Knowledge base context:\n{knowledge_context}\n"
            f"Chunk analyses JSON:\n{chunk_json}\n"
        )

    @staticmethod
    def _build_chat_prompt(*, context: str, question: str, language: str) -> str:
        return (
            "You are a grounded assistant for marketing review.\n"
            "Only answer using provided context. If insufficient evidence, say so.\n"
            "Return strict JSON with keys: content, citations, confidence_score, insufficient_evidence.\n"
            "Rules: confidence_score in [0,1], citations as list of {timestamp, quote}.\n"
            f"Preferred answer language: {language}\n"
            f"Context:\n{context}\n"
            f"Question: {question}\n"
        )

    @staticmethod
    def _build_comments_sentiment_prompt(*, title: str, language: str, comments_bullets: str) -> str:
        return (
            "You are summarizing user sentiment from YouTube comments for a product video.\n"
            "Return strict JSON with keys: summary, highlights, lowlights.\n"
            "Rules:\n"
            "- summary must be 2 to 3 concise sentences.\n"
            "- highlights is a list of up to 3 positive points users mentioned.\n"
            "- lowlights is a list of up to 3 negative points users mentioned.\n"
            "- If no positive points are present, return highlights as [].\n"
            "- If no negative points are present, return lowlights as [].\n"
            "- Do not invent claims that are not in the comments.\n"
            f"Preferred answer language: {language}\n"
            f"Video title: {title}\n"
            f"Comments:\n{comments_bullets}\n"
        )

