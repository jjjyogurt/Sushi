from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.health import GeminiHealthResponse
from app.services.gemini_health_service import GeminiHealthService

router = APIRouter(prefix="/health", tags=["health"])


class HealthCheckResponse(BaseModel):
    status: str
    service: str


@router.get("", response_model=HealthCheckResponse)
def health_check():
    """Basic health check for service liveness."""
    return HealthCheckResponse(status="ok", service="sushi-backend")


@router.get("/gemini", response_model=GeminiHealthResponse)
def gemini_health(probe: bool = Query(default=False)):
    service = GeminiHealthService()
    status = service.status(probe=probe)
    return GeminiHealthResponse(**status)
