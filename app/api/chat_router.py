from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.mappers import map_chat_message_response
from app.db import get_db_session
from app.schemas.chat import ChatMessageResponse, ChatRequest
from app.services.chat_service import ChatService
from app.services.exceptions import GeminiError

router = APIRouter(prefix="/videos/{video_id}/chat", tags=["chat"])


@router.post("", response_model=ChatMessageResponse)
def ask_chatbot(video_id: int, payload: ChatRequest, db: Session = Depends(get_db_session)):
    service = ChatService(db)
    try:
        message = service.ask(
            video_id=video_id,
            question=payload.question,
            user_id=payload.user_id,
            knowledge_base_id=payload.knowledge_base_id,
        )
        return map_chat_message_response(message)
    except GeminiError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("", response_model=List[ChatMessageResponse])
def list_chat_messages(video_id: int, user_id: str = "marketing-user", db: Session = Depends(get_db_session)):
    service = ChatService(db)
    messages = service.list_messages(video_id=video_id, user_id=user_id)
    return [map_chat_message_response(message) for message in messages]

