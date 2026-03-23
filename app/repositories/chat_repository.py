from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_session(self, *, video_candidate_id: int, created_by: str) -> ChatSession:
        existing = (
            self.session.query(ChatSession)
            .filter(ChatSession.video_candidate_id == video_candidate_id)
            .order_by(ChatSession.created_at.asc())
            .first()
        )
        if existing:
            return existing

        session = ChatSession(video_candidate_id=video_candidate_id, created_by=created_by)
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def add_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        citations_json: str,
        confidence_score: str,
        insufficient_evidence: bool,
    ) -> ChatMessage:
        message = ChatMessage(
            chat_session_id=session_id,
            role=role,
            content=content,
            citations_json=citations_json,
            confidence_score=confidence_score,
            insufficient_evidence=insufficient_evidence,
        )
        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)
        return message

    def list_messages(self, session_id: int) -> List[ChatMessage]:
        return (
            self.session.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def get_message(self, message_id: int) -> Optional[ChatMessage]:
        return self.session.get(ChatMessage, message_id)

