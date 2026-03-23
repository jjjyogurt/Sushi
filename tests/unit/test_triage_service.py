from app.config import get_settings
from app.models.enums import QueueState
from app.services.triage_service import TriageService


def test_discovery_persists_candidates(db_session, monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    service = TriageService(db_session)
    results = service.discover_for_profile(monitor_profile_id=monitor_profile.id, max_results=3)
    assert len(results) == 3
    assert all(item.monitor_profile_id == monitor_profile.id for item in results)
    settings.enable_mock_discovery = original


def test_approve_updates_queue_state(db_session, monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    service = TriageService(db_session)
    candidates = service.discover_for_profile(monitor_profile_id=monitor_profile.id, max_results=1)
    updated = service.approve(video_id=candidates[0].id, approved=True)
    assert updated.queue_state == QueueState.APPROVED
    settings.enable_mock_discovery = original

