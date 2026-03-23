import json
from typing import List

from app.config import Settings
from app.models.enums import RiskLevel, Sentiment
from app.services.types import AnalysisOutput, ChatOutput


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze_video(
        self,
        *,
        title: str,
        language: str,
        relevance_reason: str,
        brand_keywords: List[str],
        transcript_text: str,
    ) -> AnalysisOutput:
        if not self.settings.gemini_api_key or not self._sdk_available():
            return self._mock_analysis(title=title, language=language, transcript_text=transcript_text)

        transcript_for_prompt = transcript_text[: self.settings.analysis_max_transcript_chars]
        prompt = self._build_analysis_prompt(
            title=title,
            language=language,
            relevance_reason=relevance_reason,
            brand_keywords=brand_keywords,
            transcript_text=transcript_for_prompt,
        )
        raw = self._generate_text(model_name=self.settings.gemini_model_analysis, prompt=prompt)
        parsed = self._parse_json_payload(raw=raw)
        return self._analysis_from_parsed(
            parsed=parsed, fallback_title=title, fallback_transcript=transcript_text
        )

    def chat_about_video(self, *, context: str, question: str, language: str) -> ChatOutput:
        if not self.settings.gemini_api_key or not self._sdk_available():
            return self._mock_chat(context=context, question=question)

        prompt = self._build_chat_prompt(context=context, question=question, language=language)
        raw = self._generate_text(model_name=self.settings.gemini_model_chat, prompt=prompt)
        parsed = self._parse_json_payload(raw=raw)
        return self._chat_from_parsed(parsed=parsed)

    def _generate_text(self, *, model_name: str, prompt: str) -> str:
        try:
            import google.generativeai as genai
        except ImportError as error:
            raise RuntimeError("google-generativeai package is required to call Gemini.") from error

        genai.configure(api_key=self.settings.gemini_api_key)
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        if not response or not getattr(response, "text", ""):
            raise RuntimeError("Gemini returned an empty response.")
        return response.text.strip()

    @staticmethod
    def _sdk_available() -> bool:
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return False
        return True

    @staticmethod
    def _parse_json_payload(*, raw: str) -> dict:
        normalized = raw.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            normalized = normalized.replace("json", "", 1).strip()
        try:
            return json.loads(normalized)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _analysis_from_parsed(*, parsed: dict, fallback_title: str, fallback_transcript: str) -> AnalysisOutput:
        sentiment = GeminiClient._safe_sentiment(parsed.get("sentiment"))
        risk_level = GeminiClient._safe_risk_level(parsed.get("risk_level"))
        transcript_text = parsed.get("transcript_text") or fallback_transcript or f"Transcript unavailable for {fallback_title}."
        summary_text = parsed.get("summary_text") or "Summary unavailable."
        translated_summary = parsed.get("translated_summary") or summary_text
        confidence_score = float(parsed.get("confidence_score", 0.5))
        evidence = parsed.get("evidence") or [{"timestamp": "00:00", "quote": summary_text, "reason": "Fallback"}]
        insights = parsed.get("insights") or ["No structured insights generated."]
        return AnalysisOutput(
            transcript_text=transcript_text,
            summary_text=summary_text,
            translated_summary=translated_summary,
            sentiment=sentiment,
            risk_level=risk_level,
            confidence_score=confidence_score,
            evidence=evidence,
            insights=insights,
        )

    @staticmethod
    def _safe_sentiment(value) -> Sentiment:
        try:
            return Sentiment(str(value).lower())
        except ValueError:
            return Sentiment.NEUTRAL

    @staticmethod
    def _safe_risk_level(value) -> RiskLevel:
        try:
            return RiskLevel(str(value).lower())
        except ValueError:
            return RiskLevel.MEDIUM

    @staticmethod
    def _chat_from_parsed(*, parsed: dict) -> ChatOutput:
        content = parsed.get("content") or "There is not enough evidence in this transcript to answer confidently."
        citations = parsed.get("citations") or []
        confidence_score = float(parsed.get("confidence_score", 0.4))
        insufficient_evidence = bool(parsed.get("insufficient_evidence", confidence_score < 0.5))
        return ChatOutput(
            content=content,
            citations=citations,
            confidence_score=confidence_score,
            insufficient_evidence=insufficient_evidence,
        )

    @staticmethod
    def _build_analysis_prompt(
        *, title: str, language: str, relevance_reason: str, brand_keywords: List[str], transcript_text: str
    ) -> str:
        keywords_text = ", ".join(brand_keywords)
        return (
            "You are analyzing influencer video content for marketing risk monitoring.\n"
            "Return strict JSON with keys: summary_text, translated_summary, sentiment, "
            "risk_level, confidence_score, evidence, insights.\n"
            f"Video title: {title}\n"
            f"Language: {language}\n"
            f"Brand keywords: {keywords_text}\n"
            f"Relevance reason: {relevance_reason}\n"
            f"Transcript:\n{transcript_text}\n"
            "Rules: sentiment in [positive, neutral, negative], risk_level in [low, medium, high], "
            "evidence as list of {timestamp, quote, reason}, insights as list of strings.\n"
            "Focus on the transcript content. Use direct quotes and timestamps from transcript when possible.\n"
            "If uncertain, set insufficient claims and confidence below 0.5."
        )

    @staticmethod
    def _build_chat_prompt(*, context: str, question: str, language: str) -> str:
        return (
            "You are a grounded assistant for marketing review.\n"
            "Only answer using provided context. If insufficient evidence, say so.\n"
            "Return strict JSON with keys: content, citations, confidence_score, insufficient_evidence.\n"
            f"Preferred answer language: {language}\n"
            f"Context:\n{context}\n"
            f"Question: {question}\n"
        )

    @staticmethod
    def _mock_analysis(*, title: str, language: str, transcript_text: str) -> AnalysisOutput:
        transcript_lines = [line for line in transcript_text.splitlines() if line.strip()]
        excerpt = " ".join(transcript_lines[:3])[:400]
        summary = (
            f"The creator reviews {title} with mixed feedback. Key points from transcript: {excerpt}"
        )
        return AnalysisOutput(
            transcript_text=transcript_text,
            summary_text=summary,
            translated_summary=summary if language == "en" else f"[translated to {language}] {summary}",
            sentiment=Sentiment.NEUTRAL,
            risk_level=RiskLevel.MEDIUM,
            confidence_score=0.73,
            evidence=[
                {
                    "timestamp": transcript_lines[0].split(" ")[0] if transcript_lines else "00:00",
                    "quote": transcript_lines[0][6:] if transcript_lines else summary,
                    "reason": "Representative transcript signal.",
                },
                {
                    "timestamp": transcript_lines[1].split(" ")[0] if len(transcript_lines) > 1 else "00:30",
                    "quote": transcript_lines[1][6:] if len(transcript_lines) > 1 else "No second transcript line.",
                    "reason": "Additional transcript context.",
                },
            ],
            insights=[
                "Users like quick setup.",
                "Onboarding clarity should improve for power features.",
                "Reliability narrative may trend negative without response.",
            ],
        )

    @staticmethod
    def _mock_chat(*, context: str, question: str) -> ChatOutput:
        lowered = question.lower()
        if "evidence" in lowered or "quote" in lowered or "risk" in lowered:
            return ChatOutput(
                content="Key risk evidence appears around 05:10 where reliability concerns are mentioned.",
                citations=[{"timestamp": "05:10", "quote": "Reliability could be better after one week."}],
                confidence_score=0.79,
                insufficient_evidence=False,
            )

        if "fact" in lowered and "error" in lowered:
            return ChatOutput(
                content="There is not enough evidence in the transcript to confirm factual errors.",
                citations=[],
                confidence_score=0.32,
                insufficient_evidence=True,
            )

        short_context = context[:180].replace("\n", " ")
        return ChatOutput(
            content=f"Based on available context, the creator sentiment is mixed. Context excerpt: {short_context}",
            citations=[{"timestamp": "02:48", "quote": "I got confused with the advanced controls."}],
            confidence_score=0.62,
            insufficient_evidence=False,
        )

