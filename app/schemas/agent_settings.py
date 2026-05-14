from pydantic import BaseModel, Field


class AgentSettingsUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class AgentSettingsResponse(BaseModel):
    content: str
    settings_hash: str
    is_default: bool
    default_content: str
    max_chars: int
