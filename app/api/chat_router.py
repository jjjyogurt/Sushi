from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.api.mappers import map_chat_message_response
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.chat import ChatMessageResponse, ChatRequest
from app.services.access_control import AccessControlService
from app.services.chat_service import ChatService
from app.services.exceptions import GeminiError

router = APIRouter(prefix="/videos/{video_id}/chat", tags=["chat"])


@router.post("", response_model=ChatMessageResponse)
def ask_chatbot(
    video_id: int,
    payload: ChatRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = ChatService(db)
    try:
        AccessControlService(db).require_video_owner(video_id=video_id, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        message = service.ask(
            video_id=video_id,
            question=payload.question,
            user_id=current_user.id,
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
def list_chat_messages(
    video_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = ChatService(db)
    try:
        AccessControlService(db).require_video_owner(video_id=video_id, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    messages = service.list_messages(video_id=video_id, user_id=current_user.id)
    return [map_chat_message_response(message) for message in messages]
