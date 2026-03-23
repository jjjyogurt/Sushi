from fastapi import APIRouter, Query

from app.schemas.health import GeminiHealthResponse
from app.services.gemini_health_service import GeminiHealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/gemini", response_model=GeminiHealthResponse)
def gemini_health(probe: bool = Query(default=False)):
    service = GeminiHealthService()
    status = service.status(probe=probe)
    return GeminiHealthResponse(**status)
