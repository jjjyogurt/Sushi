from typing import Optional

from pydantic import BaseModel


class GeminiHealthResponse(BaseModel):
    ready: bool
    api_key_configured: bool
    sdk_available: bool
    analysis_model: str
    chat_model: str
    probe_ok: Optional[bool] = None
    probe_error: Optional[str] = None
