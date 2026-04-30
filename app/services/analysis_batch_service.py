from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import QueueState
from app.repositories.analysis_batch_repository import AnalysisBatchRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.video_repository import VideoRepository
from app.services.analysis_service import AnalysisService

logger = logging.getLogger(__name__)


class AnalysisBatchService:
    def __init__(self, session: Session):
        self.session = session
        self.batch_repository = AnalysisBatchRepository(session)
        self.video_repository = VideoRepository(session)
        self.analysis_repository = AnalysisRepository(session)
        self.analysis_service = AnalysisService(session)

    def create_batch(
        self,
        *,
        monitor_profile_id: Optional[int],
        created_by: str,
    ):
        videos = self.video_repository.list(
            monitor_profile_id=monitor_profile_id,
            queue_state=QueueState.APPROVED,
        )
        video_ids = [video.id for video in videos]
        latest_status_by_video = self.analysis_repository.get_latest_status_by_video_ids(video_ids, language="en")
        video_ids = [
            video_id
            for video_id in video_ids
            if str(latest_status_by_video.get(video_id, "")).lower() != "completed"
        ]
        if not video_ids:
            raise ValueError("No approved videos available to analyze.")

        return self.batch_repository.create_batch(
            monitor_profile_id=monitor_profile_id,
            created_by=created_by,
            video_ids=video_ids,
        )

    def get_batch(self, batch_id: int):
        batch = self.batch_repository.get_batch(batch_id)
        if batch is None:
            raise ValueError("Analysis batch not found.")
        return batch

    def list_batch_items(self, batch_id: int):
        return self.batch_repository.get_items_for_batch(batch_id)

    def get_latest_active_batch(self, monitor_profile_id: Optional[int]):
        return self.batch_repository.get_latest_active_batch(monitor_profile_id=monitor_profile_id)

    def cancel_batch(self, batch_id: int):
        return self.batch_repository.cancel_batch(batch_id)

    def process_next_item(self) -> bool:
        item = self.batch_repository.claim_next_item()
        if item is None:
            return False

        try:
            self.analysis_service.analyze_video(
                video_id=item.video_id,
                force_reanalyze=False,
            )
            self.batch_repository.mark_item_completed(item.id)
        except Exception as error:  # noqa: BLE001
            logger.exception(
                "analysis batch item failed batch_id=%s item_id=%s video_id=%s error=%s",
                item.batch_id,
                item.id,
                item.video_id,
                error,
            )
            self.batch_repository.mark_item_failed(item.id, error_message=str(error))
        return True
