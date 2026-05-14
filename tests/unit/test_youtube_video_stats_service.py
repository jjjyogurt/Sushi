from types import SimpleNamespace

from app.services.youtube_video_stats_service import YouTubeVideoReachMetrics, YouTubeVideoStatsService


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_reach_metrics_combines_video_views_and_channel_subscribers(monkeypatch):
    service = YouTubeVideoStatsService()
    service.settings = SimpleNamespace(
        youtube_data_api_key="test-key",
        youtube_comments_timeout_seconds=5.0,
    )
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        if url == service.VIDEOS_ENDPOINT:
            return FakeResponse(
                {
                    "items": [
                        {
                            "id": "video-1",
                            "statistics": {"viewCount": "12345"},
                            "snippet": {"channelId": "channel-1"},
                        }
                    ]
                }
            )
        if url == service.CHANNELS_ENDPOINT:
            return FakeResponse(
                {
                    "items": [
                        {
                            "id": "channel-1",
                            "statistics": {"subscriberCount": "67890"},
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.services.youtube_video_stats_service.requests.get", fake_get)

    metrics_by_video_id = service.fetch_reach_metrics(youtube_video_ids=["video-1"])

    assert metrics_by_video_id == {
        "video-1": YouTubeVideoReachMetrics(
            view_count=12345,
            subscriber_count=67890,
        )
    }
    assert calls[0]["params"]["part"] == "statistics,snippet"
    assert calls[1]["params"]["part"] == "statistics"


def test_fetch_view_counts_keeps_existing_video_statistics_call(monkeypatch):
    service = YouTubeVideoStatsService()
    service.settings = SimpleNamespace(
        youtube_data_api_key="test-key",
        youtube_comments_timeout_seconds=5.0,
    )
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(
            {
                "items": [
                    {
                        "id": "video-1",
                        "statistics": {"viewCount": "12345"},
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.youtube_video_stats_service.requests.get", fake_get)

    view_counts = service.fetch_view_counts(youtube_video_ids=["video-1"])

    assert view_counts == {"video-1": 12345}
    assert len(calls) == 1
    assert calls[0]["url"] == service.VIDEOS_ENDPOINT
    assert calls[0]["params"]["part"] == "statistics"


def test_fetch_reach_metrics_keeps_views_when_channel_lookup_fails(monkeypatch):
    service = YouTubeVideoStatsService()
    service.settings = SimpleNamespace(
        youtube_data_api_key="test-key",
        youtube_comments_timeout_seconds=5.0,
    )

    def fake_get(url, *, params, timeout):
        if url == service.VIDEOS_ENDPOINT:
            return FakeResponse(
                {
                    "items": [
                        {
                            "id": "video-1",
                            "statistics": {"viewCount": "12345"},
                            "snippet": {"channelId": "channel-1"},
                        }
                    ]
                }
            )
        if url == service.CHANNELS_ENDPOINT:
            raise RuntimeError("quota exhausted")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.services.youtube_video_stats_service.requests.get", fake_get)

    metrics_by_video_id = service.fetch_reach_metrics(youtube_video_ids=["video-1"])

    assert metrics_by_video_id == {
        "video-1": YouTubeVideoReachMetrics(
            view_count=12345,
            subscriber_count=None,
        )
    }

