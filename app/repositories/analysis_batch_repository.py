from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, func, update
from sqlalchemy.orm import Session

from app.models.analysis_batch import AnalysisBatch, AnalysisBatchItem
from app.models.enums import AnalysisBatchItemStatus, AnalysisBatchStatus


class AnalysisBatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_batch(self, *, monitor_profile_id: Optional[int], created_by: str, video_ids: List[int]) -> AnalysisBatch:
        batch = AnalysisBatch(
            monitor_profile_id=monitor_profile_id,
            created_by=created_by,
            status=AnalysisBatchStatus.QUEUED,
            total_count=len(video_ids),
            processed_count=0,
            success_count=0,
            failed_count=0,
            last_error="",
        )
        self.session.add(batch)
        self.session.flush()

        for video_id in video_ids:
            self.session.add(
                AnalysisBatchItem(
                    batch_id=batch.id,
                    video_id=video_id,
                    status=AnalysisBatchItemStatus.QUEUED,
                    attempt_count=0,
                    error_message="",
                )
            )

        self.session.commit()
        self.session.refresh(batch)
        return batch

    def get_batch(self, batch_id: int) -> Optional[AnalysisBatch]:
        return self.session.get(AnalysisBatch, batch_id)

    def get_items_for_batch(self, batch_id: int) -> List[AnalysisBatchItem]:
        return (
            self.session.query(AnalysisBatchItem)
            .filter(AnalysisBatchItem.batch_id == batch_id)
            .order_by(AnalysisBatchItem.id.asc())
            .all()
        )

    def get_latest_active_batch(self, *, monitor_profile_id: Optional[int], created_by: Optional[str] = None) -> Optional[AnalysisBatch]:
        query = self.session.query(AnalysisBatch).filter(
            AnalysisBatch.status.in_([AnalysisBatchStatus.QUEUED, AnalysisBatchStatus.RUNNING])
        )
        if monitor_profile_id is None:
            query = query.filter(AnalysisBatch.monitor_profile_id.is_(None))
            if created_by is not None:
                query = query.filter(AnalysisBatch.created_by == created_by)
        else:
            query = query.filter(AnalysisBatch.monitor_profile_id == monitor_profile_id)
        return query.order_by(AnalysisBatch.created_at.desc()).first()

    def claim_next_item(self) -> Optional[AnalysisBatchItem]:
        active_batch = (
            self.session.query(AnalysisBatch)
            .filter(AnalysisBatch.status.in_([AnalysisBatchStatus.QUEUED, AnalysisBatchStatus.RUNNING]))
            .order_by(AnalysisBatch.created_at.asc())
            .first()
        )
        if active_batch is None:
            return None

        item = (
            self.session.query(AnalysisBatchItem)
            .filter(AnalysisBatchItem.batch_id == active_batch.id)
            .filter(AnalysisBatchItem.status == AnalysisBatchItemStatus.QUEUED)
            .order_by(AnalysisBatchItem.id.asc())
            .first()
        )
        if item is None:
            self._finalize_batch_if_done(active_batch.id)
            return None

        now = datetime.now(timezone.utc)
        if active_batch.started_at is None:
            active_batch.started_at = now
        active_batch.status = AnalysisBatchStatus.RUNNING

        claim_result = self.session.execute(
            update(AnalysisBatchItem)
            .where(AnalysisBatchItem.id == item.id)
            .where(AnalysisBatchItem.status == AnalysisBatchItemStatus.QUEUED)
            .values(
                status=AnalysisBatchItemStatus.RUNNING,
                attempt_count=int(item.attempt_count or 0) + 1,
                started_at=now,
                error_message="",
            )
        )
        if int(claim_result.rowcount or 0) == 0:
            self.session.rollback()
            return None

        self.session.commit()
        self.session.refresh(item)
        return item

    def has_queued_items(self) -> bool:
        return (
            self.session.query(AnalysisBatchItem.id)
            .join(AnalysisBatch, AnalysisBatch.id == AnalysisBatchItem.batch_id)
            .filter(AnalysisBatch.status.in_([AnalysisBatchStatus.QUEUED, AnalysisBatchStatus.RUNNING]))
            .filter(AnalysisBatchItem.status == AnalysisBatchItemStatus.QUEUED)
            .first()
            is not None
        )

    def mark_item_completed(self, item_id: int) -> AnalysisBatchItem:
        item = self.session.get(AnalysisBatchItem, item_id)
        if item is None:
            raise ValueError("Batch item not found.")
        item.status = AnalysisBatchItemStatus.COMPLETED
        item.finished_at = datetime.now(timezone.utc)
        item.error_message = ""
        self.session.commit()
        self._recompute_batch_counts(item.batch_id)
        self.session.refresh(item)
        return item

    def mark_item_failed(self, item_id: int, *, error_message: str) -> AnalysisBatchItem:
        item = self.session.get(AnalysisBatchItem, item_id)
        if item is None:
            raise ValueError("Batch item not found.")
        item.status = AnalysisBatchItemStatus.FAILED
        item.finished_at = datetime.now(timezone.utc)
        item.error_message = error_message[:2000]
        self.session.commit()
        self._recompute_batch_counts(item.batch_id)
        self.session.refresh(item)
        return item

    def cancel_batch(self, batch_id: int) -> AnalysisBatch:
        batch = self.session.get(AnalysisBatch, batch_id)
        if batch is None:
            raise ValueError("Analysis batch not found.")
        if batch.status in (AnalysisBatchStatus.COMPLETED, AnalysisBatchStatus.CANCELLED):
            return batch

        self.session.query(AnalysisBatchItem).filter(
            AnalysisBatchItem.batch_id == batch_id,
            AnalysisBatchItem.status.in_([AnalysisBatchItemStatus.QUEUED, AnalysisBatchItemStatus.RUNNING]),
        ).update(
            {
                AnalysisBatchItem.status: AnalysisBatchItemStatus.CANCELLED,
                AnalysisBatchItem.finished_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        batch.status = AnalysisBatchStatus.CANCELLED
        batch.finished_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def _recompute_batch_counts(self, batch_id: int) -> None:
        batch = self.session.get(AnalysisBatch, batch_id)
        if batch is None:
            return

        counts = dict(
            self.session.query(AnalysisBatchItem.status, func.count(AnalysisBatchItem.id))
            .filter(AnalysisBatchItem.batch_id == batch_id)
            .group_by(AnalysisBatchItem.status)
            .all()
        )

        completed = int(counts.get(AnalysisBatchItemStatus.COMPLETED, 0))
        failed = int(counts.get(AnalysisBatchItemStatus.FAILED, 0))
        cancelled = int(counts.get(AnalysisBatchItemStatus.CANCELLED, 0))
        queued = int(counts.get(AnalysisBatchItemStatus.QUEUED, 0))
        running = int(counts.get(AnalysisBatchItemStatus.RUNNING, 0))

        batch.success_count = completed
        batch.failed_count = failed
        batch.processed_count = completed + failed + cancelled

        if queued == 0 and running == 0:
            batch.finished_at = datetime.now(timezone.utc)
            if batch.processed_count == 0:
                batch.status = AnalysisBatchStatus.CANCELLED
            elif failed > 0 and completed == 0:
                batch.status = AnalysisBatchStatus.FAILED
            elif failed > 0:
                batch.status = AnalysisBatchStatus.COMPLETED
                batch.last_error = "Some videos failed during analysis."
            else:
                batch.status = AnalysisBatchStatus.COMPLETED
        else:
            batch.status = AnalysisBatchStatus.RUNNING

        self.session.commit()

    def _finalize_batch_if_done(self, batch_id: int) -> None:
        has_remaining = (
            self.session.query(AnalysisBatchItem.id)
            .filter(
                AnalysisBatchItem.batch_id == batch_id,
                AnalysisBatchItem.status.in_([AnalysisBatchItemStatus.QUEUED, AnalysisBatchItemStatus.RUNNING]),
            )
            .first()
        )
        if has_remaining is None:
            self._recompute_batch_counts(batch_id)
