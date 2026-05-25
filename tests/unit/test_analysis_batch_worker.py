from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.workers import analysis_batch_worker


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_drain_queue_processes_items_until_empty(monkeypatch):
    class FakeInsightJobService:
        def __init__(self, _session):
            pass

        def process_next_job(self):
            return False

        def has_queued_jobs(self):
            return False

    class FakeBatchService:
        processed_results = [True, True, False]

        def __init__(self, _session):
            pass

        def process_next_item(self):
            return self.processed_results.pop(0)

        def has_queued_items(self):
            return False

    monkeypatch.setattr(analysis_batch_worker, "ProjectInsightJobService", FakeInsightJobService)
    monkeypatch.setattr(analysis_batch_worker, "AnalysisBatchService", FakeBatchService)

    result = analysis_batch_worker.drain_queue(
        max_seconds=60,
        session_factory=_session_factory(),
    )

    assert result.status == "drained"
    assert result.processed_count == 2
    assert result.queue_empty is True
    assert result.time_budget_exhausted is False


def test_drain_queue_pauses_at_item_limit_when_work_remains(monkeypatch):
    class FakeInsightJobService:
        def __init__(self, _session):
            pass

        def process_next_job(self):
            return False

        def has_queued_jobs(self):
            return False

    class FakeBatchService:
        def __init__(self, _session):
            pass

        def process_next_item(self):
            return True

        def has_queued_items(self):
            return True

    monkeypatch.setattr(analysis_batch_worker, "ProjectInsightJobService", FakeInsightJobService)
    monkeypatch.setattr(analysis_batch_worker, "AnalysisBatchService", FakeBatchService)

    result = analysis_batch_worker.drain_queue(
        max_seconds=60,
        max_items=2,
        session_factory=_session_factory(),
    )

    assert result.status == "paused"
    assert result.processed_count == 2
    assert result.queue_empty is False
    assert result.item_limit_reached is True
    assert analysis_batch_worker.should_enqueue_continuation(result) is True


def test_drain_queue_processes_project_insight_jobs_before_analysis_batches(monkeypatch):
    class FakeInsightJobService:
        processed_results = [True, False]

        def __init__(self, _session):
            pass

        def process_next_job(self):
            return self.processed_results.pop(0) if self.processed_results else False

        def has_queued_jobs(self):
            return False

    class FakeBatchService:
        processed_results = [True, False]

        def __init__(self, _session):
            pass

        def process_next_item(self):
            return self.processed_results.pop(0) if self.processed_results else False

        def has_queued_items(self):
            return False

    monkeypatch.setattr(analysis_batch_worker, "ProjectInsightJobService", FakeInsightJobService)
    monkeypatch.setattr(analysis_batch_worker, "AnalysisBatchService", FakeBatchService)

    result = analysis_batch_worker.drain_queue(
        max_seconds=60,
        session_factory=_session_factory(),
    )

    assert result.status == "drained"
    assert result.processed_count == 2
    assert result.queue_empty is True


def test_worker_request_auth_uses_internal_token_when_configured(monkeypatch):
    settings = analysis_batch_worker.get_settings()
    original_token = settings.analysis_worker_internal_token
    monkeypatch.setattr(settings, "analysis_worker_internal_token", "unit-secret")

    try:
        assert analysis_batch_worker.worker_request_is_authorized(
            {"X-Sushi-Worker-Token": "unit-secret"}
        )
        assert not analysis_batch_worker.worker_request_is_authorized(
            {"X-Sushi-Worker-Token": "wrong"}
        )
    finally:
        monkeypatch.setattr(settings, "analysis_worker_internal_token", original_token)
