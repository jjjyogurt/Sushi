from fastapi import APIRouter, HTTPException

from app.schemas.agent_settings import AgentSettingsResponse, AgentSettingsUpdateRequest
from app.services.agent_settings_service import AgentSettingsService

router = APIRouter(prefix="/agent-settings", tags=["agent-settings"])


@router.get("", response_model=AgentSettingsResponse)
def get_agent_settings():
    service = AgentSettingsService()
    return AgentSettingsResponse(**service.get_payload())


@router.put("", response_model=AgentSettingsResponse)
def update_agent_settings(payload: AgentSettingsUpdateRequest):
    service = AgentSettingsService()
    try:
        saved_content = service.save_content(payload.content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    response_payload = {
        "content": saved_content,
        "default_content": service.default_content(),
        "max_chars": service.MAX_CHARS,
    }
    return AgentSettingsResponse(**response_payload)


@router.post("/reset", response_model=AgentSettingsResponse)
def reset_agent_settings():
    service = AgentSettingsService()
    try:
        reset_content = service.reset_to_default()
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    response_payload = {
        "content": reset_content,
        "default_content": service.default_content(),
        "max_chars": service.MAX_CHARS,
    }
    return AgentSettingsResponse(**response_payload)
