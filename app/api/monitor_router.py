from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.api.mappers import map_monitor_response
from app.db import get_db_session
from app.models.app_user import AppUser
from app.repositories.monitor_repository import MonitorRepository
from app.schemas.monitor import (
    MonitorProfileCreate,
    MonitorProfileMonitoringUpdate,
    MonitorProfileResponse,
    MonitorProfileUpdate,
)

router = APIRouter(prefix="/monitor-profiles", tags=["monitor-profiles"])


@router.post("", response_model=MonitorProfileResponse)
def create_profile(
    payload: MonitorProfileCreate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    profile = repository.create(payload, owner_user_id=current_user.id)
    return map_monitor_response(profile)


@router.get("", response_model=List[MonitorProfileResponse])
def list_profiles(
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    return [map_monitor_response(profile) for profile in repository.list_for_user(current_user.id)]


@router.get("/{profile_id}", response_model=MonitorProfileResponse)
def get_profile(
    profile_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    profile = repository.get_for_user(profile_id, current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return map_monitor_response(profile)


@router.put("/{profile_id}", response_model=MonitorProfileResponse)
def update_profile(
    profile_id: int,
    payload: MonitorProfileUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    profile = repository.update(profile_id, payload, owner_user_id=current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return map_monitor_response(profile)


@router.patch("/{profile_id}/monitoring-settings", response_model=MonitorProfileResponse)
def update_monitoring_settings(
    profile_id: int,
    payload: MonitorProfileMonitoringUpdate,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    profile = repository.update_monitoring_settings(
        profile_id,
        owner_user_id=current_user.id,
        enabled=payload.proactive_monitoring_enabled,
        cadence=payload.proactive_monitoring_cadence,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return map_monitor_response(profile)


@router.post("/{profile_id}/monitoring-updates/seen", response_model=MonitorProfileResponse)
def mark_monitoring_updates_seen(
    profile_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    profile = repository.mark_monitoring_updates_seen(profile_id, owner_user_id=current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return map_monitor_response(profile)


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    repository = MonitorRepository(db)
    success = repository.delete(profile_id, owner_user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Monitor profile not found.")
    return {"status": "success"}
