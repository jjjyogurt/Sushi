from __future__ import annotations

import logging
import time

from app.db import get_db_engine
from app.db_migrations import (
    ensure_analysis_batch_tables,
    ensure_analysis_results_comment_columns,
    ensure_analysis_results_language_column_and_index,
    ensure_analysis_results_summary_columns,
    ensure_default_app_users,
    ensure_monitor_profiles_key_products_column,
    ensure_project_insight_reports_portfolio_columns,
    ensure_video_candidate_assignment_columns,
    ensure_video_comments_table,
    retire_legacy_business_impact_columns,
)
from app.models.base import Base
from app.services.analysis_batch_service import AnalysisBatchService
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def bootstrap_db() -> None:
    engine = get_db_engine(max_retries=15, retry_delay=2.0)
    Base.metadata.create_all(bind=engine)
    ensure_analysis_batch_tables(engine)
    ensure_monitor_profiles_key_products_column(engine)
    ensure_analysis_results_summary_columns(engine)
    ensure_analysis_results_language_column_and_index(engine)
    ensure_analysis_results_comment_columns(engine)
    ensure_video_comments_table(engine)
    ensure_video_candidate_assignment_columns(engine)
    ensure_project_insight_reports_portfolio_columns(engine)
    retire_legacy_business_impact_columns(engine)
    ensure_default_app_users(engine)


def run_forever(poll_interval_seconds: float = 2.0) -> None:
    engine = get_db_engine(max_retries=15, retry_delay=2.0)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    logger.info("analysis worker started poll_interval_seconds=%s", poll_interval_seconds)

    while True:
        processed = False
        with SessionLocal() as session:
            service = AnalysisBatchService(session)
            processed = service.process_next_item()
        if not processed:
            time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    bootstrap_db()
    run_forever()
