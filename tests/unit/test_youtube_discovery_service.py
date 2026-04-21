import sys
import types
from datetime import datetime, timezone

from app.services.types import DiscoveredVideo
from app.services.youtube_discovery_service import (
    YouTubeDiscoveryService,
    filter_discovered_videos_by_publish_window,
)


def test_fallback_query_specs_japanese_and_german_markets():
    specs = YouTubeDiscoveryService._fallback_query_specs(
        keywords=["HOVERAir X1"],
        languages=["ja", "de"],
        markets=["Japan", "Germany"],
    )
    pairs = {(lang, region) for _q, lang, region in specs}
    assert ("ja", "JP") in pairs
    assert ("de", "DE") in pairs
    assert ("ja", "DE") in pairs
    assert ("de", "JP") in pairs
    assert all("hoverair" in q.lower() for q, _, _ in specs)


def test_discover_live_with_specs_youtube_data_api_japanese(monkeypatch):
    requests_seen = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        requests_seen.append((url, dict(params or {})))
        if params and params.get("regionCode") == "JP" and params.get("relevanceLanguage") == "ja":
            return FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": {"videoId": "jp-video"},
                            "snippet": {
                                "title": "HOVERAir X1 スマート レビュー",
                                "channelTitle": "JP Creator",
                                "description": "Japanese locale result",
                                "publishedAt": "2026-04-15T00:00:00Z",
                            },
                        }
                    ]
                },
            )
        return FakeResponse(200, {"items": []})

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "fake-key"
    discovered = service.discover_live_with_specs(
        query_specs=[("HOVERAir X1 レビュー", "ja", "JP")],
        max_results=5,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert [item.youtube_video_id for item in discovered] == ["jp-video"]
    assert discovered[0].language == "ja"
    assert any(params.get("regionCode") == "JP" for _url, params in requests_seen)
    assert any(params.get("relevanceLanguage") == "ja" for _url, params in requests_seen)


def test_discover_live_with_specs_youtube_data_api_german(monkeypatch):
    requests_seen = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        requests_seen.append((url, dict(params or {})))
        if params and params.get("regionCode") == "DE" and params.get("relevanceLanguage") == "de":
            return FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": {"videoId": "de-video"},
                            "snippet": {
                                "title": "HOVERAir X1 Test deutsch",
                                "channelTitle": "DE Creator",
                                "description": "German locale result",
                                "publishedAt": "2026-04-15T00:00:00Z",
                            },
                        }
                    ]
                },
            )
        return FakeResponse(200, {"items": []})

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "fake-key"
    discovered = service.discover_live_with_specs(
        query_specs=[("HOVERAir X1 Test", "de", "DE")],
        max_results=5,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert [item.youtube_video_id for item in discovered] == ["de-video"]
    assert discovered[0].language == "de"
    assert any(params.get("regionCode") == "DE" for _url, params in requests_seen)
    assert any(params.get("relevanceLanguage") == "de" for _url, params in requests_seen)


def test_filter_discovered_videos_by_publish_window_half_open():
    low = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
    mid = datetime(2026, 1, 11, 12, 0, 0, tzinfo=timezone.utc)
    high = datetime(2026, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
    videos = [
        DiscoveredVideo(
            youtube_video_id="a",
            video_url="https://www.youtube.com/watch?v=a",
            title="A",
            channel_name="C",
            language="en",
            published_at=low,
            description="d",
        ),
        DiscoveredVideo(
            youtube_video_id="b",
            video_url="https://www.youtube.com/watch?v=b",
            title="B",
            channel_name="C",
            language="en",
            published_at=mid,
            description="d",
        ),
        DiscoveredVideo(
            youtube_video_id="c",
            video_url="https://www.youtube.com/watch?v=c",
            title="C",
            channel_name="C",
            language="en",
            published_at=high,
            description="d",
        ),
    ]
    filtered = filter_discovered_videos_by_publish_window(
        videos,
        published_after=low,
        published_before=high,
    )
    assert [item.youtube_video_id for item in filtered] == ["a", "b"]


def test_discover_live_with_specs_passes_publish_window_to_data_api(monkeypatch):
    requests_seen = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        requests_seen.append((url, dict(params or {})))
        return FakeResponse(200, {"items": []})

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "fake-key"
    after = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    before = datetime(2026, 12, 31, 0, 0, 0, tzinfo=timezone.utc)
    service.discover_live_with_specs(
        query_specs=[("HOVERAir X1", "en", "US")],
        max_results=5,
        published_after=after,
        published_before=before,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert any(
        params.get("publishedAfter") == "2026-01-01T00:00:00Z" and params.get("publishedBefore") == "2026-12-31T00:00:00Z"
        for _url, params in requests_seen
    )


def test_discover_live_yt_dlp_filters_by_publish_window(monkeypatch):
    ts_old = 1_700_000_000
    ts_new = 1_800_000_000
    mid_ts = (ts_old + ts_new) // 2

    class FakeYoutubeDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        def extract_info(self, query, download=False):
            _ = download
            return {
                "entries": [
                    {
                        "id": "old",
                        "title": "Product one review",
                        "channel": "Creator",
                        "description": "Old",
                        "timestamp": ts_old,
                    },
                    {
                        "id": "new",
                        "title": "Product two review",
                        "channel": "Creator",
                        "description": "New",
                        "timestamp": ts_new,
                    },
                ]
            }

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)

    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = ""
    after = datetime.fromtimestamp(mid_ts, tz=timezone.utc)
    discovered = service.discover_live_with_specs(
        query_specs=[("product english", "en", "US")],
        max_results=10,
        published_after=after,
        published_before=None,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert [item.youtube_video_id for item in discovered] == ["new"]


def test_discover_live_runs_multi_queries_and_dedupes_yt_dlp(monkeypatch):
    queries_seen = []

    class FakeYoutubeDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        def extract_info(self, query, download=False):
            _ = download
            queries_seen.append(query)
            if "one" in query:
                return {
                    "entries": [
                        {
                            "id": "video-one",
                            "title": "Product one review",
                            "channel": "Creator One",
                            "description": "First",
                            "timestamp": 1_710_000_000,
                        }
                    ]
                }
            if "two" in query:
                return {
                    "entries": [
                        {
                            "id": "video-one",
                            "title": "Product one duplicate",
                            "channel": "Creator One",
                            "description": "Dup",
                            "timestamp": 1_710_000_100,
                        },
                        {
                            "id": "video-two",
                            "title": "Product two only",
                            "channel": "Creator Two",
                            "description": "Second",
                            "timestamp": 1_710_000_200,
                        },
                    ]
                }
            return {"entries": []}

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYoutubeDL)
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)

    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = ""
    discovered = service.discover_live_with_specs(
        query_specs=[
            ("one english", "en", "US"),
            ("two english", "en", "US"),
        ],
        max_results=5,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert [item.youtube_video_id for item in discovered] == ["video-one", "video-two"]
    assert len(queries_seen) >= 2
