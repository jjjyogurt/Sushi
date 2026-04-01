from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.voc_evidence import VocEvidence
from app.models.voc_insight import VocInsight
from app.models.voc_project import VocProject
from app.models.voc_report import VocReport
from app.models.voc_row import VocRow
from app.models.voc_run import VocRun
from app.models.voc_skill_version import VocSkillVersion
from app.models.voc_template_version import VocTemplateVersion
from app.models.voc_upload import VocUpload


class VocProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, description: str) -> VocProject:
        project = VocProject(name=name, description=description)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def list_all(self) -> List[VocProject]:
        return self.session.query(VocProject).order_by(VocProject.created_at.desc()).all()

    def get(self, project_id: int) -> Optional[VocProject]:
        return self.session.get(VocProject, project_id)

    def update(self, project: VocProject, name: str, description: str, status: str) -> VocProject:
        project.name = name
        project.description = description
        project.status = status
        self.session.commit()
        self.session.refresh(project)
        return project

    def delete(self, project: VocProject) -> None:
        self.session.delete(project)
        self.session.commit()


class VocUploadRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        project_id: int,
        source_type: str,
        filename: str,
        total_rows: int,
    ) -> VocUpload:
        upload = VocUpload(
            project_id=project_id,
            source_type=source_type,
            filename=filename,
            status="uploaded",
            total_rows=total_rows,
            processed_rows=0,
            failed_rows=0,
        )
        self.session.add(upload)
        self.session.commit()
        self.session.refresh(upload)
        return upload

    def get(self, upload_id: int) -> Optional[VocUpload]:
        return self.session.get(VocUpload, upload_id)

    def list_by_project(self, project_id: int) -> List[VocUpload]:
        return (
            self.session.query(VocUpload)
            .filter(VocUpload.project_id == project_id)
            .order_by(VocUpload.created_at.desc())
            .all()
        )

    def update_counts(self, upload: VocUpload, processed: int, failed: int, status: str) -> VocUpload:
        upload.processed_rows = processed
        upload.failed_rows = failed
        upload.status = status
        self.session.commit()
        self.session.refresh(upload)
        return upload

    def set_error(self, upload: VocUpload, message: str) -> VocUpload:
        upload.error_message = message
        self.session.commit()
        self.session.refresh(upload)
        return upload


class VocRowRepository:
    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, rows: List[VocRow]) -> None:
        self.session.add_all(rows)
        self.session.commit()

    def list_by_upload(self, upload_id: int, status: Optional[str] = None, limit: int = 200) -> List[VocRow]:
        query = self.session.query(VocRow).filter(VocRow.upload_id == upload_id)
        if status:
            query = query.filter(VocRow.status == status)
        return query.order_by(VocRow.row_index.asc()).limit(limit).all()

    def list_all_by_upload(self, upload_id: int) -> List[VocRow]:
        return self.session.query(VocRow).filter(VocRow.upload_id == upload_id).all()

    def save(self, row: VocRow) -> VocRow:
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row


class VocRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        upload_id: int,
        run_type: str,
        total_rows: int,
        cleaner_skill_version_id: Optional[int] = None,
        analyzer_skill_version_id: Optional[int] = None,
        report_template_version_id: Optional[int] = None,
    ) -> VocRun:
        run = VocRun(
            upload_id=upload_id,
            run_type=run_type,
            status="running",
            started_at=datetime.utcnow(),
            total_rows=total_rows,
            processed_rows=0,
            failed_rows=0,
            cleaner_skill_version_id=cleaner_skill_version_id,
            analyzer_skill_version_id=analyzer_skill_version_id,
            report_template_version_id=report_template_version_id,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get(self, run_id: int) -> Optional[VocRun]:
        return self.session.get(VocRun, run_id)

    def update_progress(self, run: VocRun, processed: int, failed: int, status: str) -> VocRun:
        run.processed_rows = processed
        run.failed_rows = failed
        run.status = status
        if status in {"completed", "failed"}:
            run.completed_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(run)
        return run

    def set_error(self, run: VocRun, message: str) -> VocRun:
        run.error_message = message
        self.session.commit()
        self.session.refresh(run)
        return run


class VocInsightRepository:
    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, insights: List[VocInsight]) -> List[VocInsight]:
        self.session.add_all(insights)
        self.session.commit()
        for insight in insights:
            self.session.refresh(insight)
        return insights

    def list_by_upload(self, upload_id: int) -> List[VocInsight]:
        return self.session.query(VocInsight).filter(VocInsight.upload_id == upload_id).all()


class VocEvidenceRepository:
    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, items: List[VocEvidence]) -> None:
        self.session.add_all(items)
        self.session.commit()

    def list_by_insight(self, insight_id: int) -> List[VocEvidence]:
        return self.session.query(VocEvidence).filter(VocEvidence.insight_id == insight_id).all()


class VocReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        project_id: int,
        upload_id: int,
        content: str,
        cleaner_skill_version_id: Optional[int],
        analyzer_skill_version_id: Optional[int],
        report_template_version_id: Optional[int],
    ) -> VocReport:
        report = VocReport(
            project_id=project_id,
            upload_id=upload_id,
            content=content,
            status="draft",
            cleaner_skill_version_id=cleaner_skill_version_id,
            analyzer_skill_version_id=analyzer_skill_version_id,
            report_template_version_id=report_template_version_id,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report

    def get(self, report_id: int) -> Optional[VocReport]:
        return self.session.get(VocReport, report_id)

    def get_latest_by_project(self, project_id: int) -> Optional[VocReport]:
        return (
            self.session.query(VocReport)
            .filter(VocReport.project_id == project_id)
            .order_by(VocReport.created_at.desc())
            .first()
        )

    def update_content(self, report: VocReport, content: str) -> VocReport:
        report.content = content
        self.session.commit()
        self.session.refresh(report)
        return report

    def update_status(self, report: VocReport, status: str, reason: str = "") -> VocReport:
        report.status = status
        report.publish_block_reason = reason
        self.session.commit()
        self.session.refresh(report)
        return report


class VocSettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_skill_versions(self, skill_type: str) -> List[VocSkillVersion]:
        return (
            self.session.query(VocSkillVersion)
            .filter(VocSkillVersion.skill_type == skill_type)
            .order_by(VocSkillVersion.created_at.desc())
            .all()
        )

    def create_skill_version(self, skill_type: str, name: str, content: str) -> VocSkillVersion:
        item = VocSkillVersion(skill_type=skill_type, name=name, content=content, status="draft", is_active=False)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get_skill_version(self, version_id: int) -> Optional[VocSkillVersion]:
        return self.session.get(VocSkillVersion, version_id)

    def update_skill_version(self, item: VocSkillVersion, name: str, content: str) -> VocSkillVersion:
        item.name = name
        item.content = content
        self.session.commit()
        self.session.refresh(item)
        return item

    def set_skill_status(self, item: VocSkillVersion, status: str) -> VocSkillVersion:
        item.status = status
        self.session.commit()
        self.session.refresh(item)
        return item

    def activate_skill_version(self, item: VocSkillVersion) -> VocSkillVersion:
        self.session.query(VocSkillVersion).filter(
            VocSkillVersion.skill_type == item.skill_type, VocSkillVersion.is_active.is_(True)
        ).update({"is_active": False}, synchronize_session=False)
        item.is_active = True
        item.status = "active"
        self.session.commit()
        self.session.refresh(item)
        return item

    def list_templates(self) -> List[VocTemplateVersion]:
        return self.session.query(VocTemplateVersion).order_by(VocTemplateVersion.created_at.desc()).all()

    def create_template(self, name: str, content: str) -> VocTemplateVersion:
        item = VocTemplateVersion(name=name, content=content, status="draft", is_active=False)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get_template(self, template_id: int) -> Optional[VocTemplateVersion]:
        return self.session.get(VocTemplateVersion, template_id)

    def update_template(self, item: VocTemplateVersion, name: str, content: str) -> VocTemplateVersion:
        item.name = name
        item.content = content
        self.session.commit()
        self.session.refresh(item)
        return item

    def set_template_status(self, item: VocTemplateVersion, status: str) -> VocTemplateVersion:
        item.status = status
        self.session.commit()
        self.session.refresh(item)
        return item

    def activate_template(self, item: VocTemplateVersion) -> VocTemplateVersion:
        self.session.query(VocTemplateVersion).filter(VocTemplateVersion.is_active.is_(True)).update(
            {"is_active": False}, synchronize_session=False
        )
        item.is_active = True
        item.status = "active"
        self.session.commit()
        self.session.refresh(item)
        return item
