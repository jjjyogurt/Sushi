from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.project_insight_job import ProjectInsightJob
from app.repositories.project_insight_job_repository import ProjectInsightJobRepository
from app.services.access_control import AccessControlService
from app.services.project_insights_service import ProjectInsightsService

logger = logging.getLogger(__name__)


class ProjectInsightJobService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = ProjectInsightJobRepository(session)
        self.access_control = AccessControlService(session)

    def create_or_get_active_job(self, *, monitor_profile_id: int, user_id: str, language: str = "en") -> ProjectInsightJob:
        self.access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=user_id)
        return self.repository.create_or_get_active(
            monitor_profile_id=monitor_profile_id,
            language=language,
            created_by=user_id,
        )

    def get_active_job(self, *, monitor_profile_id: int, user_id: str, language: str = "en") -> Optional[ProjectInsightJob]:
        self.access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=user_id)
        return self.repository.get_latest_active_for_profile(monitor_profile_id, language=language)

    def get_job(self, *, monitor_profile_id: int, job_id: int, user_id: str) -> ProjectInsightJob:
        self.access_control.require_profile_owner(monitor_profile_id=monitor_profile_id, user_id=user_id)
        job = self.repository.get_for_profile(monitor_profile_id=monitor_profile_id, job_id=job_id)
        if job is None:
            raise ValueError("Project insight job not found.")
        return job

    def process_next_job(self) -> bool:
        job = self.repository.claim_next_job()
        if job is None:
            return False

        try:
            report = ProjectInsightsService(self.session).refresh_report(job.monitor_profile_id, language=job.language)
            self.repository.mark_completed(job_id=job.id, report_id=report.id)
        except Exception as error:  # noqa: BLE001
            logger.exception(
                "project insight job failed job_id=%s monitor_profile_id=%s error=%s",
                job.id,
                job.monitor_profile_id,
                error,
            )
            self.repository.mark_failed(job_id=job.id, error_message=str(error))
        return True

    def has_queued_jobs(self) -> bool:
        return self.repository.has_queued_jobs()
