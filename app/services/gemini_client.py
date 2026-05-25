import json
import logging
import re
from typing import Any, Dict, List, Optional

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

    def analyze_video(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_context: str = "",
        agent_instructions: Optional[str] = None,
    ) -> AnalysisOutput:
        self._ensure_runtime_ready()
        max_transcript_chars = max(1, self.settings.analysis_max_transcript_chars)
        transcript_for_prompt = transcript_text[:max_transcript_chars]
        hard_capped = len(transcript_for_prompt) < len(transcript_text)
        single_pass_threshold = max(1, self.settings.analysis_single_pass_max_estimated_tokens)
        resolved_agent_instructions = agent_instructions or self._analysis_agent_instructions()
        single_pass_prompt = self._build_analysis_single_pass_prompt(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            transcript_text=transcript_for_prompt,
            agent_instructions=resolved_agent_instructions,
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
            agent_instructions=resolved_agent_instructions,
        )

    def ensure_ready(self) -> None:
        self._ensure_runtime_ready()

    def generate_voc_report(
        self,
        *,
        analyzer_prompt: str,
        cleaned_rows: List[dict],
        total_rows: int,
    ) -> str:
        self._ensure_runtime_ready()
        normalized_rows = [row for row in cleaned_rows if isinstance(row, dict)]
        if not normalized_rows:
            raise GeminiResponseError("VOC analyzer input is empty.")

        max_rows = 1200
        rows_for_prompt = normalized_rows[:max_rows]
        payload = json.dumps(rows_for_prompt, ensure_ascii=True)
        prompt = (
            "You are generating a VOC report from cleaned customer feedback rows.\n"
            "Follow the analyzer system prompt below strictly.\n"
            "Return markdown only. Do not wrap the output in code fences.\n"
            f"Total uploaded rows: {total_rows}\n"
            f"Cleaned rows supplied to analyzer: {len(rows_for_prompt)}\n"
            "Analyzer system prompt:\n"
            f"{analyzer_prompt}\n"
            "Cleaned rows JSON:\n"
            f"{payload}\n"
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        normalized = raw.strip()
        if normalized.startswith("```"):
            normalized = self._extract_fenced_payload(normalized).strip()
        if not normalized:
            raise GeminiResponseError("Gemini VOC report output is empty.")
        return normalized

    def generate_project_insights_report(
        self,
        *,
        project_name: str,
        brand_keywords: List[str],
        key_products: List[str],
        target_output_language: str = "en",
        total_video_count: int,
        analyzed_video_count: int,
        records: List[dict],
        agent_instructions: str,
    ) -> dict:
        self._ensure_runtime_ready()
        normalized_records = [row for row in records if isinstance(row, dict)]
        if not normalized_records:
            raise GeminiResponseError("Project insights input is empty.")

        max_records = 80
        records_for_prompt = normalized_records[:max_records]
        payload = json.dumps(records_for_prompt, ensure_ascii=True)
        brand_keywords_csv = ", ".join([item for item in [str(raw or "").strip() for raw in brand_keywords] if item]) or "none"
        key_products_csv = ", ".join([item for item in [str(raw or "").strip() for raw in key_products] if item]) or "none"
        output_language_name = "Simplified Chinese" if target_output_language == "zh-Hans" else "English"
        prompt = (
            "You are a professional product-insights researcher for consumer electronics.\n"
            "Generate a project-level synthesis using only the evidence provided.\n"
            "This is a comprehensive multi-video project report, not a single-video review.\n"
            "Aggregate recurring themes across all included videos and prioritize cross-video patterns.\n"
            "Output must align to an executive portfolio template (decision-first, no fluff).\n"
            "Return strict JSON only with this exact shape:\n"
            '{'
            '"summary_headline":"string",'
            '"core_insight":"string",'
            '"top_risk_trigger":"string",'
            '"overall_sentiment":"positive|neutral|negative",'
            '"risk_level":"low|medium|high|critical",'
            '"risk_score":0.0,'
            '"praise_points":["string"],'
            '"criticism_points":["string"],'
            '"user_recommendations":["string"]'
            '}\n'
            "Rules:\n"
            "- Base all claims on provided records only.\n"
            "- Treat this as a strict single-project analysis scope. Do not mix in data from other projects.\n"
            "- The focus products for this project are listed below; anchor the analysis to these products.\n"
            "- Brand keywords are provided as lexical guides for entity resolution and product references.\n"
            "- Do not mention competitor models, brands, or benchmarks unless they are explicitly present in this project's records.\n"
            "- If no valid direct comparison appears in this project's records, do not invent one.\n"
            "- Keep lists concise and high-signal (max 5 each).\n"
            f"- Write all user-facing string fields in {output_language_name}. Keep enum values in English exactly as specified.\n"
            "- Do not fabricate incidents, timestamps, or failures.\n"
            "- Use critical/high risk wording only when evidence supports it.\n"
            "- Do not include methodology, process notes, or snapshot-report style wording.\n"
            "- `summary_headline`: one line, decision-first. If risk is high/critical, prioritize safety/reliability impact.\n"
            "- `core_insight`: 3-4 sentences with richer synthesis; include what is happening, where sentiment shifts, concrete evidence cues, and why it matters for product/marketing decisions.\n"
            "- `top_risk_trigger`: one short line naming the single most important failure moment/category.\n"
            "- `praise_points`: include only repeatable strengths; prioritize Hoverair/V-Copter advantages when competitor comparisons exist.\n"
            "- `criticism_points`: include only concrete failure/friction signals; prioritize competitor wins as criticism when directly compared.\n"
            "- `user_recommendations`: tactical and executable by marketing/product teams in 24-72h.\n"
            "- Prefer objective technical failures over subjective creative preference when both are present.\n"
            "- When available in evidence, include brief proof qualifiers in list items (for example: repeated across multiple videos or explicit on-camera demonstration).\n"
            f"Project name: {project_name}\n"
            f"Project brand keywords: {brand_keywords_csv}\n"
            f"Project key products to monitor: {key_products_csv}\n"
            f"Target output language: {output_language_name}\n"
            f"Total project videos: {total_video_count}\n"
            f"Analyzed videos included: {analyzed_video_count}\n"
            f"Records JSON:\n{payload}\n"
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        parsed = self._parse_json_payload(raw=raw, context="project insights report")
        return self._normalize_project_insights_payload(parsed)

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
            insights=analysis_output.insights,
            praise_points=analysis_output.praise_points,
            criticism_points=analysis_output.criticism_points,
            audience_profiles=analysis_output.audience_profiles,
            usage_scenarios=analysis_output.usage_scenarios,
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
            sentiment=analysis_output.sentiment,
            risk_level=analysis_output.risk_level,
            confidence_score=analysis_output.confidence_score,
            evidence=analysis_output.evidence,
            insights=translated_fields.get("insights", analysis_output.insights),
            praise_points=translated_fields.get("praise_points", analysis_output.praise_points),
            criticism_points=translated_fields.get("criticism_points", analysis_output.criticism_points),
            audience_profiles=translated_fields.get("audience_profiles", analysis_output.audience_profiles),
            usage_scenarios=translated_fields.get("usage_scenarios", analysis_output.usage_scenarios),
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

    def plan_youtube_discovery_queries(
        self,
        *,
        keywords: List[str],
        language_codes: List[str],
        region_specs: List[dict],
    ) -> dict:
        """Return JSON with queries[] and match_keywords[] for localized YouTube search."""
        self._ensure_runtime_ready()
        payload = {
            "keywords": keywords,
            "language_codes": language_codes,
            "regions": region_specs,
        }
        prompt = (
            "You prepare YouTube search query strings for influencer/product video discovery.\n"
            "Use the user's keywords verbatim for product names, brands, and model numbers.\n"
            "For each query, add natural local phrasing so relevant videos rank well in that locale "
            "(reviews, unboxing, hands-on, tests — use what is typical for that language/market).\n"
            "Return strict JSON only with this exact shape:\n"
            '{"queries":[{"q":"string","relevanceLanguage":"ISO-639-1","regionCode":"ISO-3166-1 alpha-2 or empty string"}],'
            '"match_keywords":["string"]}\n'
            "Coverage: include exactly one query object per combination of language_codes × regions "
            "when regions imply a country; relevanceLanguage must match the query language; "
            "regionCode must match the region code for that market, or \"\" when the market is global/worldwide.\n"
            "match_keywords must include the original keywords plus translations/transliterations useful for title matching.\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}\n"
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        return self._parse_json_payload(raw=raw, context="youtube discovery plan")

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
        return AgentSettingsService.default_content()

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
        sentiment = GeminiClient._safe_sentiment(parsed.get("sentiment"))
        risk_level = GeminiClient._safe_risk_level(parsed.get("risk_level"))
        confidence_score = GeminiClient._safe_confidence(parsed.get("confidence_score"), fallback=0.0)
        evidence = GeminiClient._normalize_evidence(parsed.get("evidence"))
        insights = GeminiClient._normalize_insights(parsed.get("insights"))
        praise_points = GeminiClient._normalize_point_list(parsed.get("praise_points"))
        criticism_points = GeminiClient._normalize_point_list(parsed.get("criticism_points"))
        audience_profiles = GeminiClient._normalize_audience_profiles(parsed.get("audience_profiles"))
        usage_scenarios = GeminiClient._normalize_usage_scenarios(parsed.get("usage_scenarios"))
        action_recommendation = GeminiClient._normalize_action_recommendation(parsed.get("action_recommendation"))

        normalized_target = str(target_output_language or "").strip().lower()
        audience_text = "\n".join(
            [str(item.get("description", "")) for item in audience_profiles if isinstance(item, dict)]
        )
        text_bundle = "\n".join([summary_text, summary_headline, summary_body, audience_text, *usage_scenarios])
        if self._is_output_language_mismatch(text=text_bundle, target_output_language=normalized_target):
            translated_fields = self._translate_analysis_text_fields(
                target_output_language=normalized_target,
                summary_text=summary_text,
                translated_summary=translated_summary,
                summary_headline=summary_headline,
                summary_body=summary_body,
                insights=insights,
                praise_points=praise_points,
                criticism_points=criticism_points,
                audience_profiles=audience_profiles,
                usage_scenarios=usage_scenarios,
                action_recommendation=action_recommendation,
            )
            summary_text = translated_fields.get("summary_text", summary_text)
            translated_summary = translated_fields.get("translated_summary", translated_summary)
            summary_headline = translated_fields.get("summary_headline", summary_headline)
            summary_body = translated_fields.get("summary_body", summary_body)
            insights = translated_fields.get("insights", insights)
            praise_points = translated_fields.get("praise_points", praise_points)
            criticism_points = translated_fields.get("criticism_points", criticism_points)
            audience_profiles = translated_fields.get("audience_profiles", audience_profiles)
            usage_scenarios = translated_fields.get("usage_scenarios", usage_scenarios)
            action_recommendation = translated_fields.get("action_recommendation", action_recommendation)

        return AnalysisOutput(
            transcript_text=fallback_transcript,
            summary_text=summary_text,
            translated_summary=translated_summary,
            summary_headline=summary_headline,
            summary_body=summary_body,
            sentiment=sentiment,
            risk_level=risk_level,
            confidence_score=confidence_score,
            evidence=evidence,
            insights=insights,
            praise_points=praise_points,
            criticism_points=criticism_points,
            audience_profiles=audience_profiles,
            usage_scenarios=usage_scenarios,
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
        insights: List[str],
        praise_points: List[str],
        criticism_points: List[str],
        audience_profiles: List[dict],
        usage_scenarios: List[str],
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
            "insights": insights,
            "praise_points": praise_points,
            "criticism_points": criticism_points,
            "audience_profiles": audience_profiles,
            "usage_scenarios": usage_scenarios,
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
                "insights": self._normalize_insights(parsed.get("insights")) or insights,
                "praise_points": self._normalize_point_list(parsed.get("praise_points")) or praise_points,
                "criticism_points": self._normalize_point_list(parsed.get("criticism_points")) or criticism_points,
                "audience_profiles": self._normalize_audience_profiles(parsed.get("audience_profiles"))
                or audience_profiles,
                "usage_scenarios": self._normalize_usage_scenarios(parsed.get("usage_scenarios"))
                or usage_scenarios,
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
        highlights: List[dict],
        lowlights: List[dict],
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
                "highlights": self._normalize_comment_points(parsed.get("highlights")) or highlights,
                "lowlights": self._normalize_comment_points(parsed.get("lowlights")) or lowlights,
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
    def _normalize_audience_profiles(value: Any) -> List[dict]:
        if not isinstance(value, list):
            return []
        default_types = ["Primary", "Secondary", "Specialist"]
        normalized: List[dict] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            profile_type = str(item.get("type") or item.get("label") or item.get("segment") or "").strip()
            description = str(item.get("description") or item.get("text") or item.get("point") or "").strip()
            if not description:
                continue
            if not profile_type:
                profile_type = default_types[min(index, len(default_types) - 1)]
            normalized = [*normalized, {"type": profile_type, "description": description}]
        return normalized[:3]

    @staticmethod
    def _normalize_usage_scenarios(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        cleaned = [item for item in [str(raw).strip() for raw in value] if item]
        return cleaned[:4]

    @staticmethod
    def _normalize_action_recommendation(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_project_insights_payload(parsed: dict) -> Dict[str, Any]:
        sentiment = GeminiClient._safe_sentiment(parsed.get("overall_sentiment")).value
        risk_level = GeminiClient._safe_risk_level(parsed.get("risk_level")).value
        risk_score_raw = GeminiClient._safe_confidence(parsed.get("risk_score"), fallback=0.0) * 10
        if parsed.get("risk_score") is not None:
            try:
                risk_score_raw = float(parsed.get("risk_score"))
            except (TypeError, ValueError):
                risk_score_raw = 0.0
        risk_score = max(0.0, min(10.0, round(risk_score_raw, 1)))
        return {
            "summary_headline": str(parsed.get("summary_headline", "")).strip(),
            "summary_body": str(parsed.get("core_insight", "")).strip(),
            "top_risk_trigger": str(parsed.get("top_risk_trigger", "")).strip(),
            "overall_sentiment": sentiment,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "praise_points": GeminiClient._normalize_point_list(parsed.get("praise_points")),
            "criticism_points": GeminiClient._normalize_point_list(parsed.get("criticism_points")),
            "user_recommendations": GeminiClient._normalize_point_list(parsed.get("user_recommendations")),
        }

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
        highlights = GeminiClient._normalize_comment_points(parsed.get("highlights"))
        lowlights = GeminiClient._normalize_comment_points(parsed.get("lowlights"))
        return CommentsAnalysisOutput(summary=summary, highlights=highlights, lowlights=lowlights)

    @staticmethod
    def _normalize_comment_points(value: Any) -> List[dict]:
        if not isinstance(value, list):
            return []
        normalized = []
        for item in value:
            if isinstance(item, dict):
                point = str(item.get("point", "")).strip()
                quote = str(item.get("quote", "")).strip()
                if not point and quote:
                    point = quote
                if not point:
                    continue
                normalized = [*normalized, {"point": point, "quote": quote}]
                continue
            point_text = str(item).strip()
            if point_text:
                normalized = [*normalized, {"point": point_text, "quote": ""}]
        return normalized[:3]

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
            "sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, audience_profiles, "
            "usage_scenarios, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "audience_profiles as list of 2-3 objects {type, description}, usage_scenarios as list of short strings with max 4 items, "
            "action_recommendation as one short actionable string.\n"
            "Audience profiles should identify likely viewer/customer segments from the title and transcript only; "
            "use product/marketing useful types like Primary, Secondary, Specialist, Current Owners, or Competitor Shoppers. "
            "Do not infer age, gender, income, or demographics unless explicitly stated. "
            "Usage scenarios must capture real-world contexts the influencer actually tests or discusses, "
            "such as cycling, vlogging, skiing, hiking, travel, indoor setup, or low-light test. "
            "If unclear, return [] for usage_scenarios and only evidence-supported audience profiles.\n"
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
            "sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, audience_profiles, "
            "usage_scenarios, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "audience_profiles as list of 2-3 objects {type, description}, usage_scenarios as list of short strings with max 4 items, "
            "action_recommendation as one short actionable string.\n"
            "Audience profiles should identify likely viewer/customer segments from this chunk only; do not infer age, gender, income, or demographics unless explicitly stated. "
            "Usage scenarios must capture real-world contexts actually tested or discussed in this chunk; return [] if unclear.\n"
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
            "sentiment, risk_level, "
            "confidence_score, evidence, insights, praise_points, criticism_points, audience_profiles, "
            "usage_scenarios, action_recommendation.\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high, critical], "
            "confidence_score in [0, 1], evidence as list of {timestamp, quote, reason}, insights as list of strings, "
            "praise_points as list of short strings with max 5 items, criticism_points as list of short strings with max 5 items, "
            "audience_profiles as list of 2-3 objects {type, description}, usage_scenarios as list of short strings with max 4 items, "
            "action_recommendation as one short actionable string.\n"
            "Audience profiles should synthesize likely viewer/customer segments from chunk analyses only; do not infer age, gender, income, or demographics unless explicitly stated. "
            "Usage scenarios must capture real-world contexts actually tested or discussed; return [] if unclear.\n"
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
            "Answer in the same language as the user's latest question unless the user explicitly asks for another language.\n"
            "The context, transcript, source material, or video language must not determine the response language.\n"
            f"Preferred answer language: {language}\n"
            f"Context:\n{context}\n"
            f"Question: {question}\n"
        )

    @staticmethod
    def _build_comments_sentiment_prompt(*, title: str, language: str, comments_bullets: str) -> str:
        return (
            "You are a neutral analyst summarizing user sentiment from YouTube comments for a product video.\n"
            "Return strict JSON with keys: summary, highlights, lowlights.\n"
            "Rules:\n"
            "- Be unbiased and fact-based. Reflect only what appears in comments.\n"
            "- Do not advocate for or against the product. Do not use hype or loaded language.\n"
            "- summary must be 2 to 3 concise sentences and should reflect both positive and negative signals proportionally.\n"
            "- If evidence is mixed or limited, explicitly say uncertainty or mixed sentiment in summary.\n"
            "- highlights is a list of up to 3 objects: {point, quote}.\n"
            "- lowlights is a list of up to 3 objects: {point, quote}.\n"
            "- point should be a concise takeaway in your own words.\n"
            "- quote must be a short, verbatim snippet from a real user comment.\n"
            "- If no positive points are present, return highlights as [].\n"
            "- If no negative points are present, return lowlights as [].\n"
            "- Do not invent claims that are not in the comments. Do not infer causes not explicitly mentioned.\n"
            "- Avoid duplicate points. Prioritize most repeated or strongly evidenced themes.\n"
            f"Preferred answer language: {language}\n"
            f"Video title: {title}\n"
            f"Comments:\n{comments_bullets}\n"
        )
