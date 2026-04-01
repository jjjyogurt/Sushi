from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.schemas.voc import (
    VocListResponse,
    VocProjectCreate,
    VocProjectResponse,
    VocProjectUpdate,
    VocPublishResponse,
    VocReportResponse,
    VocReportUpdate,
    VocRowResponse,
    VocRunCreate,
    VocRunResponse,
    VocSkillDefaultsResponse,
    VocSkillVersionCreate,
    VocSkillVersionResponse,
    VocSkillVersionUpdate,
    VocTemplateVersionCreate,
    VocTemplateVersionResponse,
    VocTemplateVersionUpdate,
    VocUploadResponse,
)
from app.services.voc_service import VocService
from app.voc_defaults import DEFAULT_ANALYZER_SKILL_CONTENT, DEFAULT_CLEANER_SKILL_CONTENT

router = APIRouter(prefix="/voc", tags=["voc"])


def _map_project(model) -> VocProjectResponse:
    return VocProjectResponse.model_validate(model)


def _map_upload(model) -> VocUploadResponse:
    return VocUploadResponse.model_validate(model)


def _map_row(model) -> VocRowResponse:
    return VocRowResponse.model_validate(model)


def _map_run(model) -> VocRunResponse:
    return VocRunResponse.model_validate(model)


def _map_report(model) -> VocReportResponse:
    return VocReportResponse.model_validate(model)


def _map_skill(model) -> VocSkillVersionResponse:
    return VocSkillVersionResponse.model_validate(model)


def _map_template(model) -> VocTemplateVersionResponse:
    return VocTemplateVersionResponse.model_validate(model)


@router.post("/projects", response_model=VocProjectResponse)
def create_project(payload: VocProjectCreate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        model = service.create_project(payload.name, payload.description)
        return _map_project(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/projects", response_model=VocListResponse)
def list_projects(db: Session = Depends(get_db_session)):
    service = VocService(db)
    items = [_map_project(item) for item in service.list_projects()]
    return VocListResponse(items=items, total=len(items))


@router.get("/projects/{project_id}", response_model=VocProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_project(service.get_project(project_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/projects/{project_id}", response_model=VocProjectResponse)
def update_project(project_id: int, payload: VocProjectUpdate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        model = service.update_project(project_id, payload.name, payload.description, payload.status)
        return _map_project(model)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        service.delete_project(project_id)
        return {"status": "success"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/uploads", response_model=VocUploadResponse)
async def create_upload(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
):
    service = VocService(db)
    try:
        content_type = (file.content_type or "").lower()
        if file.filename and not file.filename.lower().endswith(".csv") and "csv" not in content_type:
            raise ValueError("Only CSV files are supported.")
        content = await file.read()
        model = service.create_upload(project_id=project_id, filename=file.filename or "", content=content)
        return _map_upload(model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/uploads", response_model=VocListResponse)
def list_uploads(project_id: int = Query(...), db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        items = [_map_upload(item) for item in service.list_uploads(project_id)]
        return VocListResponse(items=items, total=len(items))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/uploads/{upload_id}", response_model=VocUploadResponse)
def get_upload(upload_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_upload(service.get_upload(upload_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/rows", response_model=VocListResponse)
def list_rows(
    upload_id: int = Query(...),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db_session),
):
    service = VocService(db)
    try:
        items = [_map_row(item) for item in service.list_rows(upload_id, status=status, limit=limit)]
        return VocListResponse(items=items, total=len(items))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/runs/clean", response_model=VocRunResponse)
def start_cleaning(payload: VocRunCreate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        run = service.start_cleaning(payload.upload_id)
        return _map_run(run)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/runs/analyze", response_model=VocReportResponse)
def start_analysis(payload: VocRunCreate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        _, report = service.start_analysis(payload.upload_id)
        return _map_report(report)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/reports", response_model=VocReportResponse)
def get_report(project_id: int = Query(...), db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_report(service.get_report(project_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/reports/{report_id}", response_model=VocReportResponse)
def update_report(report_id: int, payload: VocReportUpdate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_report(service.update_report(report_id, payload.content))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/reports/{report_id}/publish", response_model=VocPublishResponse)
def publish_report(report_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        gate, _ = service.publish_report(report_id)
        return VocPublishResponse(
            allowed=gate.allowed,
            requires_acknowledgment=gate.requires_acknowledgment,
            reason=gate.reason,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/settings/skills/defaults", response_model=VocSkillDefaultsResponse)
def get_skill_defaults():
    return VocSkillDefaultsResponse(cleaner=DEFAULT_CLEANER_SKILL_CONTENT, analyzer=DEFAULT_ANALYZER_SKILL_CONTENT)


@router.get("/settings/skills", response_model=VocListResponse)
def list_skills(skill_type: str = Query(...), db: Session = Depends(get_db_session)):
    service = VocService(db)
    items = [_map_skill(item) for item in service.list_skill_versions(skill_type)]
    return VocListResponse(items=items, total=len(items))


@router.post("/settings/skills", response_model=VocSkillVersionResponse)
def create_skill(payload: VocSkillVersionCreate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_skill(service.create_skill_version(payload.skill_type, payload.name, payload.content))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/settings/skills/{skill_id}", response_model=VocSkillVersionResponse)
def update_skill(skill_id: int, payload: VocSkillVersionUpdate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_skill(service.update_skill_version(skill_id, payload.name, payload.content))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/settings/skills/{skill_id}/validate", response_model=VocSkillVersionResponse)
def validate_skill(skill_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_skill(service.validate_skill_version(skill_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/settings/skills/{skill_id}/activate", response_model=VocSkillVersionResponse)
def activate_skill(skill_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_skill(service.activate_skill_version(skill_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/settings/templates", response_model=VocListResponse)
def list_templates(db: Session = Depends(get_db_session)):
    service = VocService(db)
    items = [_map_template(item) for item in service.list_templates()]
    return VocListResponse(items=items, total=len(items))


@router.post("/settings/templates", response_model=VocTemplateVersionResponse)
def create_template(payload: VocTemplateVersionCreate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_template(service.create_template(payload.name, payload.content))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/settings/templates/{template_id}", response_model=VocTemplateVersionResponse)
def update_template(template_id: int, payload: VocTemplateVersionUpdate, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_template(service.update_template(template_id, payload.name, payload.content))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/settings/templates/{template_id}/preview", response_model=VocTemplateVersionResponse)
def preview_template(template_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_template(service.preview_template(template_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/settings/templates/{template_id}/activate", response_model=VocTemplateVersionResponse)
def activate_template(template_id: int, db: Session = Depends(get_db_session)):
    service = VocService(db)
    try:
        return _map_template(service.activate_template(template_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
