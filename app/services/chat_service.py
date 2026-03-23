from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.video_repository import VideoRepository
from app.services.gemini_client import GeminiClient
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
        self.gemini_client = GeminiClient(self.settings)

    def ask(self, *, video_id: int, question: str, user_id: str):
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

        knowledge = default_product_knowledge()
        context = "\n".join(
            [
                "Transcript:",
                sanitize_transcript_context(analysis.transcript_text),
                "Summary:",
                analysis.summary_text,
                "Evidence:",
                analysis.evidence_json,
                "Product knowledge:",
                "\n".join(knowledge),
            ]
        )
        output = self.gemini_client.chat_about_video(context=context, question=question, language=candidate.language)

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

