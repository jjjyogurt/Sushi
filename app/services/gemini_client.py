import json
import logging
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
from app.services.types import AnalysisOutput, ChatOutput

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.agent_settings_service = AgentSettingsService()

    def analyze_video(
        self,
        *,
        title: str,
        language: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_context: str = "",
    ) -> AnalysisOutput:
        self._ensure_runtime_ready()
        transcript_for_prompt = transcript_text[: self.settings.analysis_max_transcript_chars]
        chunks = self._chunk_transcript(transcript_text=transcript_for_prompt)
        logger.info(
            "gemini analysis prepared model=%s transcript_chars=%s capped_chars=%s chunk_count=%s",
            self.settings.gemini_model_analysis,
            len(transcript_text),
            len(transcript_for_prompt),
            len(chunks),
        )
        agent_instructions = self._analysis_agent_instructions()
        chunk_analyses = [
            self._analyze_chunk(
                title=title,
                language=language,
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
            language=language,
            relevance_reason=relevance_reason,
            chunk_analyses=chunk_analyses,
            agent_instructions=agent_instructions,
            knowledge_context=knowledge_context,
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=reduce_prompt)
        parsed = self._parse_json_payload(raw=raw, context="analysis reducer")
        logger.info("gemini analysis reducer completed model=%s", self.settings.gemini_model_analysis)
        return self._analysis_from_parsed(parsed=parsed, fallback_transcript=transcript_text)

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
        language: str,
        relevance_reason: str,
        chunk_text: str,
        chunk_index: int,
        total_chunks: int,
        agent_instructions: str,
    ) -> dict:
        prompt = self._build_analysis_chunk_prompt(
            title=title,
            language=language,
            relevance_reason=relevance_reason,
            chunk_text=chunk_text,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            agent_instructions=agent_instructions,
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        logger.debug("gemini analysis chunk completed chunk=%s/%s", chunk_index, total_chunks)
        return self._parse_json_payload(raw=raw, context=f"analysis chunk {chunk_index}")

    def _analysis_agent_instructions(self) -> str:
        try:
            return self.agent_settings_service.get_content()
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to load agent instructions; using defaults. error=%s", error)
            return self.agent_settings_service.default_content()

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

    @staticmethod
    def _analysis_from_parsed(*, parsed: dict, fallback_transcript: str) -> AnalysisOutput:
        summary_text = str(parsed.get("summary_text", "")).strip()
        if not summary_text:
            raise GeminiResponseError("Gemini analysis output is missing summary_text.")

        translated_summary = str(parsed.get("translated_summary", "")).strip() or summary_text
        sentiment = GeminiClient._safe_sentiment(parsed.get("sentiment"))
        risk_level = GeminiClient._safe_risk_level(parsed.get("risk_level"))
        confidence_score = GeminiClient._safe_confidence(parsed.get("confidence_score"), fallback=0.0)
        evidence = GeminiClient._normalize_evidence(parsed.get("evidence"))
        insights = GeminiClient._normalize_insights(parsed.get("insights"))
        praise_points = GeminiClient._normalize_point_list(parsed.get("praise_points"))
        criticism_points = GeminiClient._normalize_point_list(parsed.get("criticism_points"))
        action_recommendation = GeminiClient._normalize_action_recommendation(parsed.get("action_recommendation"))

        return AnalysisOutput(
            transcript_text=fallback_transcript,
            summary_text=summary_text,
            translated_summary=translated_summary,
            sentiment=sentiment,
            risk_level=risk_level,
            confidence_score=confidence_score,
            evidence=evidence,
            insights=insights,
            praise_points=praise_points,
            criticism_points=criticism_points,
            action_recommendation=action_recommendation,
        )

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
    def _build_analysis_chunk_prompt(
        *,
        title: str,
        language: str,
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
            "Return strict JSON with keys: summary_text, translated_summary, sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "action_recommendation as one short actionable string.\n"
            f"Video title: {title}\n"
            f"Language: {language}\n"
            f"Relevance reason: {relevance_reason}\n"
            f"Chunk: {chunk_index} of {total_chunks}\n"
            "Focus only on this chunk and cite direct transcript snippets. Do not invent claims beyond transcript evidence.\n"
            f"Transcript chunk:\n{chunk_text}\n"
        )

    @staticmethod
    def _build_analysis_reduce_prompt(
        *,
        title: str,
        language: str,
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
            "Return strict JSON with keys: summary_text, translated_summary, sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "action_recommendation as one short actionable string.\n"
            "Do not invent evidence. Use only evidence that appears in chunk analyses for summary, points, and recommendation.\n"
            "Knowledge base context (if provided) can be used to verify product facts, but transcript evidence is still required for claims about this video.\n"
            f"Video title: {title}\n"
            f"Language: {language}\n"
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

