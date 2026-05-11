from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.mappers import map_alert_response, map_incident_response
from app.db import get_db_session
from app.schemas.incident import AlertListResponse, IncidentCreateRequest, IncidentResponse
from app.services.incident_service import IncidentService

router = APIRouter(tags=["incidents"])


@router.post("/videos/{video_id}/escalate", response_model=IncidentResponse)
def escalate(video_id: int, payload: IncidentCreateRequest, db: Session = Depends(get_db_session)):
    service = IncidentService(db)
    try:
        result = service.escalate(video_id=video_id, owner=payload.owner, notes=payload.notes)
        response = map_incident_response(result.incident)
        response.alert_created = result.alert_created
        return response
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(db: Session = Depends(get_db_session)):
    service = IncidentService(db)
    alerts = service.list_alerts()
    mapped = [map_alert_response(item) for item in alerts]
    return AlertListResponse(items=mapped, total=len(mapped))
