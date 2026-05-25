from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import ProjectInsightJobStatus
from app.models.project_insight_job import ProjectInsightJob


ACTIVE_STATUSES = (ProjectInsightJobStatus.QUEUED, ProjectInsightJobStatus.RUNNING)


class ProjectInsightJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_or_get_active(self, *, monitor_profile_id: int, created_by: str) -> ProjectInsightJob:
        existing = self.get_latest_active_for_profile(monitor_profile_id)
        if existing is not None:
            return existing

        job = ProjectInsightJob(
            monitor_profile_id=monitor_profile_id,
            created_by=created_by,
            status=ProjectInsightJobStatus.QUEUED,
            report_id=None,
            last_error="",
        )
        self.session.add(job)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing_after_race = self.get_latest_active_for_profile(monitor_profile_id)
            if existing_after_race is not None:
                return existing_after_race
            raise
        self.session.refresh(job)
        return job

    def get(self, job_id: int) -> Optional[ProjectInsightJob]:
        return self.session.get(ProjectInsightJob, job_id)

    def get_for_profile(self, *, monitor_profile_id: int, job_id: int) -> Optional[ProjectInsightJob]:
        return (
            self.session.query(ProjectInsightJob)
            .filter(ProjectInsightJob.id == job_id)
            .filter(ProjectInsightJob.monitor_profile_id == monitor_profile_id)
            .one_or_none()
        )

    def get_latest_active_for_profile(self, monitor_profile_id: int) -> Optional[ProjectInsightJob]:
        return (
            self.session.query(ProjectInsightJob)
            .filter(ProjectInsightJob.monitor_profile_id == monitor_profile_id)
            .filter(ProjectInsightJob.status.in_(ACTIVE_STATUSES))
            .order_by(ProjectInsightJob.created_at.desc(), ProjectInsightJob.id.desc())
            .first()
        )

    def claim_next_job(self) -> Optional[ProjectInsightJob]:
        job = (
            self.session.query(ProjectInsightJob)
            .filter(ProjectInsightJob.status == ProjectInsightJobStatus.QUEUED)
            .order_by(ProjectInsightJob.created_at.asc(), ProjectInsightJob.id.asc())
            .first()
        )
        if job is None:
            return None

        now = datetime.now(timezone.utc)
        claim_result = self.session.execute(
            update(ProjectInsightJob)
            .where(ProjectInsightJob.id == job.id)
            .where(ProjectInsightJob.status == ProjectInsightJobStatus.QUEUED)
            .values(
                status=ProjectInsightJobStatus.RUNNING,
                started_at=now,
                last_error="",
            )
        )
        if int(claim_result.rowcount or 0) == 0:
            self.session.rollback()
            return None
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_completed(self, *, job_id: int, report_id: int) -> ProjectInsightJob:
        job = self._require_job(job_id)
        job.status = ProjectInsightJobStatus.COMPLETED
        job.report_id = report_id
        job.finished_at = datetime.now(timezone.utc)
        job.last_error = ""
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_failed(self, *, job_id: int, error_message: str) -> ProjectInsightJob:
        job = self._require_job(job_id)
        job.status = ProjectInsightJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.last_error = error_message[:2000]
        self.session.commit()
        self.session.refresh(job)
        return job

    def cancel_for_profile(self, monitor_profile_id: int) -> int:
        updated = (
            self.session.query(ProjectInsightJob)
            .filter(ProjectInsightJob.monitor_profile_id == monitor_profile_id)
            .filter(ProjectInsightJob.status.in_(ACTIVE_STATUSES))
            .update(
                {
                    ProjectInsightJob.status: ProjectInsightJobStatus.CANCELLED,
                    ProjectInsightJob.finished_at: datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )
        self.session.commit()
        return int(updated or 0)

    def has_queued_jobs(self) -> bool:
        return (
            self.session.query(ProjectInsightJob.id)
            .filter(ProjectInsightJob.status == ProjectInsightJobStatus.QUEUED)
            .first()
            is not None
        )

    def delete_for_profile(self, monitor_profile_id: int) -> int:
        deleted = self.session.query(ProjectInsightJob).filter(
            ProjectInsightJob.monitor_profile_id == monitor_profile_id
        ).delete(synchronize_session=False)
        self.session.commit()
        return int(deleted)

    def _require_job(self, job_id: int) -> ProjectInsightJob:
        job = self.session.get(ProjectInsightJob, job_id)
        if job is None:
            raise ValueError("Project insight job not found.")
        return job
