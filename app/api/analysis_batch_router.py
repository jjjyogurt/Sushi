from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.api.mappers import map_analysis_batch_item_response, map_analysis_batch_response
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.analysis_batch import AnalysisBatchCreateRequest, AnalysisBatchDetailResponse, AnalysisBatchResponse
from app.services.analysis_batch_service import AnalysisBatchService
from app.services.analysis_worker_tasks import AnalysisWorkerTaskClient

router = APIRouter(prefix="/analysis/batches", tags=["analysis-batches"])


@router.post("", response_model=AnalysisBatchResponse)
def create_analysis_batch(
    payload: AnalysisBatchCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AnalysisBatchService(db)
    try:
        batch = service.create_batch(
            monitor_profile_id=payload.monitor_profile_id,
            created_by=current_user.id,
        )
        background_tasks.add_task(
            AnalysisWorkerTaskClient().enqueue_drain,
            reason=f"analysis_batch:{batch.id}",
        )
        return map_analysis_batch_response(batch)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{batch_id}", response_model=AnalysisBatchResponse)
def get_analysis_batch(
    batch_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AnalysisBatchService(db)
    try:
        return map_analysis_batch_response(service.get_batch(batch_id, user_id=current_user.id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{batch_id}/items", response_model=AnalysisBatchDetailResponse)
def get_analysis_batch_items(
    batch_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AnalysisBatchService(db)
    try:
        batch = service.get_batch(batch_id, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    items = service.list_batch_items(batch_id)
    return AnalysisBatchDetailResponse(
        batch=map_analysis_batch_response(batch),
        items=[map_analysis_batch_item_response(item) for item in items],
    )


@router.get("/active/latest", response_model=AnalysisBatchResponse)
def get_latest_active_batch(
    monitor_profile_id: Optional[int] = Query(default=None),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AnalysisBatchService(db)
    try:
        batch = service.get_latest_active_batch(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if batch is None:
        raise HTTPException(status_code=404, detail="No active analysis batch.")
    return map_analysis_batch_response(batch)


@router.post("/{batch_id}/cancel", response_model=AnalysisBatchResponse)
def cancel_analysis_batch(
    batch_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = AnalysisBatchService(db)
    try:
        return map_analysis_batch_response(service.cancel_batch(batch_id, user_id=current_user.id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
