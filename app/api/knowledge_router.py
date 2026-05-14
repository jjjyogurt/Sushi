from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_current_user
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.knowledge import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
    KnowledgeSourceListResponse,
    KnowledgeSourceResponse,
    KnowledgeSummaryResponse,
    KnowledgeUrlSourceCreateRequest,
)
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.services.access_control import AccessControlService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _map_base(model) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        monitor_profile_id=model.monitor_profile_id,
        name=model.name,
        description=model.description,
        is_active=model.is_active,
    )


def _map_source(model) -> KnowledgeSourceResponse:
    return KnowledgeSourceResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        monitor_profile_id=model.monitor_profile_id,
        knowledge_base_id=model.knowledge_base_id,
        source_type=model.source_type,
        title=model.title,
        uri_or_path=model.uri_or_path,
        status=model.status,
        error_message=model.error_message,
    )


@router.post("/bases", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=payload.monitor_profile_id, user_id=current_user.id)
        model = service.create_base(
            monitor_profile_id=payload.monitor_profile_id,
            name=payload.name,
            description=payload.description,
        )
        return _map_base(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/bases", response_model=KnowledgeBaseListResponse)
def list_knowledge_bases(
    monitor_profile_id: int = Query(..., description="Project scope"),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        AccessControlService(db).require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        items = service.list_bases(monitor_profile_id=monitor_profile_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    mapped = [_map_base(item) for item in items]
    return KnowledgeBaseListResponse(items=mapped, total=len(mapped))


@router.patch("/bases/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    knowledge_base_id: int,
    payload: KnowledgeBaseUpdateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        AccessControlService(db).require_knowledge_base_owner(knowledge_base_id=knowledge_base_id, user_id=current_user.id)
        model = service.update_base(
            knowledge_base_id=knowledge_base_id,
            name=payload.name,
            description=payload.description,
            is_active=payload.is_active,
        )
        return _map_base(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/bases/{knowledge_base_id}")
def delete_knowledge_base(
    knowledge_base_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        AccessControlService(db).require_knowledge_base_owner(knowledge_base_id=knowledge_base_id, user_id=current_user.id)
        service.delete_base(knowledge_base_id=knowledge_base_id)
        return {"status": "success"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sources/file", response_model=KnowledgeSourceResponse)
async def upload_knowledge_file(
    monitor_profile_id: int = Form(...),
    knowledge_base_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        access_control = AccessControlService(db)
        access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        access_control.require_knowledge_base_owner(knowledge_base_id=knowledge_base_id, user_id=current_user.id)
        model = await service.add_file_source(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
            upload=file,
        )
        return _map_source(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sources/url", response_model=KnowledgeSourceResponse)
def add_knowledge_url(
    payload: KnowledgeUrlSourceCreateRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        access_control = AccessControlService(db)
        access_control.require_profile_owner(monitor_profile_id=payload.monitor_profile_id, user_id=current_user.id)
        access_control.require_knowledge_base_owner(knowledge_base_id=payload.knowledge_base_id, user_id=current_user.id)
        model = service.add_url_source(
            monitor_profile_id=payload.monitor_profile_id,
            knowledge_base_id=payload.knowledge_base_id,
            url=payload.url,
            title=payload.title,
        )
        return _map_source(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sources", response_model=KnowledgeSourceListResponse)
def list_knowledge_sources(
    monitor_profile_id: int = Query(...),
    knowledge_base_id: int = Query(...),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        access_control = AccessControlService(db)
        access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        access_control.require_knowledge_base_owner(knowledge_base_id=knowledge_base_id, user_id=current_user.id)
        items = service.list_sources(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    mapped = [_map_source(item) for item in items]
    return KnowledgeSourceListResponse(items=mapped, total=len(mapped))


@router.delete("/sources/{source_id}")
def delete_knowledge_source(
    source_id: int,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        AccessControlService(db).require_knowledge_source_owner(source_id=source_id, user_id=current_user.id)
        service.delete_source(source_id=source_id)
        return {"status": "success"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/summary", response_model=KnowledgeSummaryResponse)
def get_knowledge_summary(
    monitor_profile_id: int = Query(...),
    knowledge_base_id: int = Query(...),
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = KnowledgeIngestionService(db)
    try:
        access_control = AccessControlService(db)
        access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=current_user.id)
        access_control.require_knowledge_base_owner(knowledge_base_id=knowledge_base_id, user_id=current_user.id)
        summary = service.get_summary(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return KnowledgeSummaryResponse(
        monitor_profile_id=monitor_profile_id,
        knowledge_base_id=knowledge_base_id,
        knowledge_md=summary,
    )
