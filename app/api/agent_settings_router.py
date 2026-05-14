from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.agent_settings import AgentSettingsResponse, AgentSettingsUpdateRequest
from app.services.agent_settings_service import AgentSettingsService

router = APIRouter(prefix="/agent-settings", tags=["agent-settings"])


@router.get("", response_model=AgentSettingsResponse)
def get_agent_settings(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AgentSettingsService(db)
    return AgentSettingsResponse(**service.get_payload(user_id=current_user.id))


@router.put("", response_model=AgentSettingsResponse)
def update_agent_settings(
    payload: AgentSettingsUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AgentSettingsService(db)
    try:
        service.save_content(user_id=current_user.id, content=payload.content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return AgentSettingsResponse(**service.get_payload(user_id=current_user.id))


@router.post("/reset", response_model=AgentSettingsResponse)
def reset_agent_settings(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AgentSettingsService(db)
    try:
        service.reset_to_default(user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return AgentSettingsResponse(**service.get_payload(user_id=current_user.id))
