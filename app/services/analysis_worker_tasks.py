from __future__ import annotations

import json
import logging
from typing import Optional

from google.protobuf import duration_pb2

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AnalysisWorkerTaskClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def is_configured(self) -> bool:
        return bool(
            self.settings.gcp_project_id
            and self.settings.gcp_region
            and self.settings.analysis_worker_tasks_queue
            and self.settings.analysis_worker_url
        )

    def enqueue_drain(self, *, reason: str) -> bool:
        if not self.is_configured():
            logger.info("analysis worker task enqueue skipped; Cloud Tasks config is incomplete")
            return False

        try:
            from google.cloud import tasks_v2

            client = tasks_v2.CloudTasksClient()
            parent = client.queue_path(
                self.settings.gcp_project_id,
                self.settings.gcp_region,
                self.settings.analysis_worker_tasks_queue,
            )
            task = tasks_v2.Task(
                http_request=self._build_http_request(tasks_v2=tasks_v2, reason=reason)
            )
            task.dispatch_deadline = duration_pb2.Duration(
                seconds=max(1, int(self.settings.analysis_worker_dispatch_deadline_seconds))
            )
            client.create_task(parent=parent, task=task)
            logger.info("analysis worker drain task enqueued reason=%s", reason)
            return True
        except Exception as error:  # noqa: BLE001
            logger.exception("analysis worker task enqueue failed reason=%s error=%s", reason, error)
            return False

    def _build_http_request(self, *, tasks_v2, reason: str):
        url = self._worker_drain_url()
        headers = {"Content-Type": "application/json"}
        if self.settings.analysis_worker_internal_token:
            headers["X-Sushi-Worker-Token"] = self.settings.analysis_worker_internal_token

        request = tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=url,
            headers=headers,
            body=json.dumps({"reason": reason}).encode("utf-8"),
        )
        if self.settings.analysis_worker_task_service_account_email:
            request.oidc_token.service_account_email = (
                self.settings.analysis_worker_task_service_account_email
            )
            request.oidc_token.audience = self.settings.analysis_worker_url.rstrip("/")
        return request

    def _worker_drain_url(self) -> str:
        return (
            self.settings.analysis_worker_url.rstrip("/")
            + "/"
            + self.settings.analysis_worker_drain_path.strip("/")
        )
