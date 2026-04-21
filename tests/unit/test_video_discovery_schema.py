from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.video import DISCOVERY_PUBLISH_WINDOW_MAX_DAYS, VideoDiscoveryRequest


def test_video_discovery_request_accepts_publish_window():
    body = VideoDiscoveryRequest(
        monitor_profile_id=1,
        max_results=10,
        published_after=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        published_before=datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    assert body.published_after == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert body.published_before == datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_video_discovery_request_normalizes_naive_datetimes_to_utc():
    body = VideoDiscoveryRequest(
        monitor_profile_id=1,
        published_after=datetime(2026, 1, 1, 0, 0, 0),
        published_before=datetime(2026, 1, 2, 0, 0, 0),
    )
    assert body.published_after.tzinfo == timezone.utc
    assert body.published_before.tzinfo == timezone.utc


def test_video_discovery_request_rejects_inverted_window():
    with pytest.raises(ValidationError):
        VideoDiscoveryRequest(
            monitor_profile_id=1,
            published_after=datetime(2026, 5, 2, 0, 0, 0, tzinfo=timezone.utc),
            published_before=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
        )


def test_video_discovery_request_rejects_excessive_window():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=DISCOVERY_PUBLISH_WINDOW_MAX_DAYS + 1)
    with pytest.raises(ValidationError):
        VideoDiscoveryRequest(
            monitor_profile_id=1,
            published_after=start,
            published_before=end,
        )
