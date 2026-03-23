from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.mappers import map_monitor_response
from app.db import get_db_session
from app.repositories.monitor_repository import MonitorRepository
from app.schemas.monitor import MonitorProfileCreate, MonitorProfileResponse

router = APIRouter(prefix="/monitor-profiles", tags=["monitor-profiles"])


@router.post("", response_model=MonitorProfileResponse)
def create_profile(payload: MonitorProfileCreate, db: Session = Depends(get_db_session)):
    repository = MonitorRepository(db)
    profile = repository.create(payload)
    return map_monitor_response(profile)


@router.get("", response_model=List[MonitorProfileResponse])
def list_profiles(db: Session = Depends(get_db_session)):
    repository = MonitorRepository(db)
    return [map_monitor_response(profile) for profile in repository.list_all()]


@router.get("/{profile_id}", response_model=MonitorProfileResponse)
def get_profile(profile_id: int, db: Session = Depends(get_db_session)):
    repository = MonitorRepository(db)
    profile = repository.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return map_monitor_response(profile)


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db_session)):
    repository = MonitorRepository(db)
    success = repository.delete(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return {"status": "success"}

