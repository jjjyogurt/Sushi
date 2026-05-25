from __future__ import annotations

import logging
import os
import time
import threading
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.db import get_db_engine
from app.db_migrations import (
    ensure_agent_settings_table,
    ensure_analysis_batch_tables,
    ensure_analysis_results_agent_settings_hash_column_and_index,
    ensure_analysis_results_comment_columns,
    ensure_analysis_results_language_column_and_index,
    ensure_analysis_results_summary_columns,
    ensure_default_app_users,
    ensure_monitor_profiles_owner_user_id,
    ensure_monitor_profiles_key_products_column,
    ensure_project_insight_job_tables,
    ensure_project_insight_reports_portfolio_columns,
    ensure_video_candidate_scoped_youtube_uniqueness,
    ensure_video_candidate_assignment_columns,
    ensure_video_comments_table,
    retire_legacy_business_impact_columns,
)
from app.models.base import Base
from app.services.analysis_batch_service import AnalysisBatchService
from app.services.analysis_worker_tasks import AnalysisWorkerTaskClient
from app.services.project_insight_job_service import ProjectInsightJobService
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ready = threading.Event()
_drain_lock = threading.Lock()


@dataclass(frozen=True)
class DrainResult:
    status: str
    processed_count: int
    queue_empty: bool
    time_budget_exhausted: bool
    item_limit_reached: bool
    continuation_enqueued: bool = False

    def to_json_bytes(self) -> bytes:
        import json

        return json.dumps(asdict(self)).encode("utf-8")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if urlparse(self.path).path not in {"/", "/health"}:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        status = b"ok" if _ready.is_set() else b"starting"
        self.wfile.write(b'{"status":"' + status + b'","service":"sushi-analysis-worker"}')

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != get_settings().analysis_worker_drain_path:
            self.send_response(404)
            self.end_headers()
            return
        if not worker_request_is_authorized(self.headers):
            self._write_json(status_code=401, payload=b'{"detail":"Unauthorized"}')
            return
        if not _ready.is_set():
            self._write_json(status_code=503, payload=b'{"detail":"Worker is starting"}')
            return
        if not _drain_lock.acquire(blocking=False):
            result = DrainResult(
                status="already_running",
                processed_count=0,
                queue_empty=False,
                time_budget_exhausted=False,
                item_limit_reached=False,
            )
            self._write_json(status_code=202, payload=result.to_json_bytes())
            return

        try:
            result = drain_queue()
            if should_enqueue_continuation(result):
                continuation_enqueued = AnalysisWorkerTaskClient().enqueue_drain(
                    reason="analysis_worker_continuation"
                )
                result = DrainResult(
                    status=result.status,
                    processed_count=result.processed_count,
                    queue_empty=result.queue_empty,
                    time_budget_exhausted=result.time_budget_exhausted,
                    item_limit_reached=result.item_limit_reached,
                    continuation_enqueued=continuation_enqueued,
                )
            self._write_json(status_code=200, payload=result.to_json_bytes())
        finally:
            _drain_lock.release()

    def log_message(self, format, *args):  # noqa: A002
        return

    def _write_json(self, *, status_code: int, payload: bytes) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)


def start_health_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("analysis worker health server listening port=%s", port)


def serve_http_forever() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("analysis worker HTTP server listening port=%s", port)
    bootstrap_db()
    _ready.set()
    logger.info("analysis worker ready for drain requests")
    thread.join()


def bootstrap_db() -> None:
    engine = get_db_engine(max_retries=15, retry_delay=2.0)
    Base.metadata.create_all(bind=engine)
    ensure_default_app_users(engine)
    ensure_agent_settings_table(engine)
    ensure_analysis_batch_tables(engine)
    ensure_monitor_profiles_key_products_column(engine)
    ensure_monitor_profiles_owner_user_id(engine)
    ensure_project_insight_job_tables(engine)
    ensure_analysis_results_summary_columns(engine)
    ensure_analysis_results_language_column_and_index(engine)
    ensure_analysis_results_agent_settings_hash_column_and_index(engine)
    ensure_analysis_results_comment_columns(engine)
    ensure_video_comments_table(engine)
    ensure_video_candidate_assignment_columns(engine)
    ensure_video_candidate_scoped_youtube_uniqueness(engine)
    ensure_project_insight_reports_portfolio_columns(engine)
    retire_legacy_business_impact_columns(engine)


def worker_request_is_authorized(headers) -> bool:
    token = get_settings().analysis_worker_internal_token
    if not token:
        return True
    return headers.get("X-Sushi-Worker-Token") == token


def build_session_factory():
    engine = get_db_engine(max_retries=15, retry_delay=2.0)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def drain_queue(
    *,
    max_seconds: Optional[float] = None,
    max_items: Optional[int] = None,
    session_factory=None,
) -> DrainResult:
    settings = get_settings()
    budget_seconds = settings.analysis_worker_drain_max_seconds if max_seconds is None else max_seconds
    SessionLocal = session_factory or build_session_factory()
    processed_count = 0
    started_at = time.monotonic()
    time_budget_exhausted = False
    item_limit_reached = False
    queue_empty = False

    while True:
        if max_items is not None and processed_count >= max_items:
            item_limit_reached = True
            break
        if budget_seconds is not None and time.monotonic() - started_at >= budget_seconds:
            time_budget_exhausted = True
            break

        with SessionLocal() as session:
            processed = ProjectInsightJobService(session).process_next_job()
            if not processed:
                processed = AnalysisBatchService(session).process_next_item()
        if not processed:
            queue_empty = True
            break
        processed_count += 1

    if not queue_empty and (time_budget_exhausted or item_limit_reached):
        with SessionLocal() as session:
            queue_empty = not (
                ProjectInsightJobService(session).has_queued_jobs()
                or AnalysisBatchService(session).has_queued_items()
            )

    status = "drained" if queue_empty else "paused"
    return DrainResult(
        status=status,
        processed_count=processed_count,
        queue_empty=queue_empty,
        time_budget_exhausted=time_budget_exhausted,
        item_limit_reached=item_limit_reached,
    )


def should_enqueue_continuation(result: DrainResult) -> bool:
    return not result.queue_empty and (result.time_budget_exhausted or result.item_limit_reached)


def run_forever(poll_interval_seconds: float = 2.0) -> None:
    engine = get_db_engine(max_retries=15, retry_delay=2.0)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    logger.info("analysis worker started poll_interval_seconds=%s", poll_interval_seconds)

    while True:
        processed = False
        with SessionLocal() as session:
            processed = ProjectInsightJobService(session).process_next_job()
            if not processed:
                processed = AnalysisBatchService(session).process_next_item()
        if not processed:
            time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    if os.environ.get("ANALYSIS_WORKER_MODE", "http").lower() == "poll":
        start_health_server()
        bootstrap_db()
        _ready.set()
        run_forever()
    else:
        serve_http_forever()
