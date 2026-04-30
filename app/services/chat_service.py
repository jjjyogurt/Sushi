import re
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.video_repository import VideoRepository
from app.services.gemini_client import GeminiClient
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.product_knowledge import default_product_knowledge
from app.services.prompt_guard_service import sanitize_transcript_context
from app.utils.json_codec import decode_json, encode_json


class ChatService:
    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()
        self.audit_repository = AuditRepository(session)
        self.chat_repository = ChatRepository(session)
        self.analysis_repository = AnalysisRepository(session)
        self.video_repository = VideoRepository(session)
        self.knowledge_retrieval_service = KnowledgeRetrievalService(session)
        self.gemini_client = GeminiClient(self.settings)

    def ask(self, *, video_id: int, question: str, user_id: str, knowledge_base_id: Optional[int] = None):
        candidate = self.video_repository.get_by_id(video_id)
        if candidate is None:
            raise ValueError("Video not found.")

        analysis = self.analysis_repository.get_latest_for_video(video_candidate_id=video_id)
        if analysis is None or not analysis.summary_text:
            raise ValueError("Video analysis not available yet.")

        session = self.chat_repository.get_or_create_session(video_candidate_id=video_id, created_by=user_id)
        self.chat_repository.add_message(
            session_id=session.id,
            role="user",
            content=question,
            citations_json="[]",
            confidence_score="1.00",
            insufficient_evidence=False,
        )

        knowledge_context = ""
        try:
            knowledge_context = self.knowledge_retrieval_service.build_knowledge_context(
                monitor_profile_id=candidate.monitor_profile_id,
                query_text=f"{question}\n{analysis.summary_text}",
                knowledge_base_id=knowledge_base_id,
                max_chunks=6,
                max_chars=5000,
            )
        except ValueError:
            # Keep chat resilient even if KB selection is absent/invalid.
            knowledge_context = ""

        fallback_knowledge = default_product_knowledge() if not knowledge_context else []
        context = self._build_context(
            transcript_text=analysis.transcript_text,
            summary_text=analysis.summary_text,
            evidence_json=analysis.evidence_json,
            knowledge=fallback_knowledge,
            knowledge_context=knowledge_context,
        )
        detected_question_language = self._detect_question_language(question)
        output = self.gemini_client.chat_about_video(
            context=context,
            question=question,
            language=detected_question_language,
        )

        assistant_message = self.chat_repository.add_message(
            session_id=session.id,
            role="assistant",
            content=output.content,
            citations_json=encode_json(output.citations),
            confidence_score=f"{output.confidence_score:.2f}",
            insufficient_evidence=output.insufficient_evidence,
        )
        self.audit_repository.record(
            actor=user_id,
            action="chat_question_answered",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"insufficient_evidence={output.insufficient_evidence}",
        )
        return assistant_message

    def list_messages(self, *, video_id: int, user_id: str):
        session = self.chat_repository.get_or_create_session(video_candidate_id=video_id, created_by=user_id)
        return self.chat_repository.list_messages(session.id)

    @staticmethod
    def parse_citations(citations_json: str):
        return decode_json(citations_json, [])

    def _build_context(
        self,
        *,
        transcript_text: str,
        summary_text: str,
        evidence_json: str,
        knowledge,
        knowledge_context: str = "",
    ):
        max_chars = max(2000, self.settings.chat_max_context_chars)
        sanitized_transcript = sanitize_transcript_context(transcript_text)
        knowledge_text = "\n".join(knowledge)
        shared_sections = [
            "Summary:",
            summary_text,
            "Evidence:",
            evidence_json,
            "Product knowledge:",
            knowledge_text,
            "Knowledge base context:",
            knowledge_context,
        ]
        shared_text = "\n".join(shared_sections)

        transcript_prefix = "Transcript:\n"
        transcript_budget = max(0, max_chars - len(transcript_prefix) - len(shared_text) - 1)
        transcript_excerpt = self._truncate_transcript(
            transcript_text=sanitized_transcript,
            max_chars=transcript_budget,
        )
        context = "\n".join([transcript_prefix.rstrip("\n"), transcript_excerpt, shared_text])
        if len(context) <= max_chars:
            return context
        return context[:max_chars]

    @staticmethod
    def _truncate_transcript(*, transcript_text: str, max_chars: int) -> str:
        if max_chars <= 0:
            return "[transcript omitted due to context size]"
        if len(transcript_text) <= max_chars:
            return transcript_text

        marker = "\n[transcript truncated]"
        budget = max(0, max_chars - len(marker))
        return f"{transcript_text[:budget].rstrip()}{marker}"

    @staticmethod
    def _detect_question_language(question: str) -> str:
        text = str(question or "").strip()
        if not text:
            return "en"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh-Hans"
        if re.search(r"[\u3040-\u30ff]", text):
            return "ja"
        if re.search(r"[\uac00-\ud7af]", text):
            return "ko"
        if re.search(r"[\u0400-\u04ff]", text):
            return "ru"
        if re.search(r"[\u0600-\u06ff]", text):
            return "ar"
        return "en"
