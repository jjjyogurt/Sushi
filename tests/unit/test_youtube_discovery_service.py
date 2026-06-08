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


def test_fallback_query_specs_preserves_keywords_as_separate_queries():
    specs = YouTubeDiscoveryService._fallback_query_specs(
        keywords=["HoverAir", "X1 Pro Max"],
        languages=["en"],
        markets=["US"],
    )
    queries = [q.lower() for q, _lang, _region in specs]
    assert "hoverair" in queries
    assert "x1 pro max" in queries
    assert "hoverair x1 pro max" not in queries


def test_normalized_languages_prioritizes_non_english_before_english_fallback():
    assert YouTubeDiscoveryService._normalized_languages(["en", "de"]) == ["de", "en"]


def test_normalized_languages_caps_to_two_non_english_plus_english_fallback():
    assert YouTubeDiscoveryService._normalized_languages(["de", "fr", "en", "ja", "es"]) == ["de", "fr", "en"]


def test_normalized_languages_caps_to_first_three_when_english_absent():
    assert YouTubeDiscoveryService._normalized_languages(["de", "fr", "ja", "es"]) == ["de", "fr", "ja"]


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
        params.get("order") == "date"
        and params.get("publishedAfter") == "2026-01-01T00:00:00Z"
        and params.get("publishedBefore") == "2026-12-31T00:00:00Z"
        for _url, params in requests_seen
    )


def test_discover_live_with_specs_requests_full_origin_limit_per_query(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"items": []}

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        requests_seen.append((url, dict(params or {})))
        return FakeResponse()

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "fake-key"
    service.discover_live_with_specs(
        query_specs=[
            ("HOVERAIR X1 PRO/PROMAX", "en", "DE"),
            ("HOVERAIR X1 PRO/PROMAX", "de", "DE"),
        ],
        max_results=50,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert len(requests_seen) == 2
    assert all(params.get("maxResults") == 50 for _url, params in requests_seen)


def test_discover_live_with_specs_caps_origin_limit_at_youtube_api_max(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"items": []}

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        requests_seen.append((url, dict(params or {})))
        return FakeResponse()

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "fake-key"
    service.discover_live_with_specs(
        query_specs=[("Ferrari Luce", "en", "US")],
        max_results=100,
    )
    service.settings.youtube_data_api_key = original_api_key

    assert len(requests_seen) == 1
    assert requests_seen[0][1].get("maxResults") == 50


def test_discover_live_with_specs_uses_serpapi_primary_with_data_api_enrichment(monkeypatch):
    serpapi_requests = []
    youtube_requests = []

    class SerpApiResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "video_results": [
                    {
                        "video_id": "serp-video",
                        "link": "https://www.youtube.com/watch?v=serp-video",
                    }
                ]
            }

    class YouTubeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        _ = timeout
        if "serpapi.com" in url:
            serpapi_requests.append((url, dict(params or {})))
            return SerpApiResponse()
        youtube_requests.append((url, dict(params or {})))
        if url.endswith("/videos"):
            return YouTubeResponse(
                {
                    "items": [
                        {
                            "id": "serp-video",
                            "snippet": {
                                "title": "SerpAPI validated HOVERAir result",
                                "channelTitle": "Market Creator",
                                "description": "Validated through videos.list",
                                "publishedAt": "2026-05-28T10:00:00Z",
                            },
                        }
                    ]
                }
            )
        return YouTubeResponse(
            {
                "items": [
                    {
                        "id": {"videoId": "data-video"},
                        "snippet": {
                            "title": "Data API HOVERAir result",
                            "channelTitle": "Data Creator",
                            "description": "Supplement result",
                            "publishedAt": "2026-05-28T09:00:00Z",
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_youtube_key = service.settings.youtube_data_api_key
    original_serpapi_key = service.settings.serpapi_api_key
    service.settings.youtube_data_api_key = "youtube-key"
    service.settings.serpapi_api_key = "serp-key"
    try:
        discovered = service.discover_live_with_specs(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
        )
    finally:
        service.settings.youtube_data_api_key = original_youtube_key
        service.settings.serpapi_api_key = original_serpapi_key

    assert [item.youtube_video_id for item in discovered] == ["serp-video", "data-video"]
    assert discovered[0].title == "SerpAPI validated HOVERAir result"
    assert serpapi_requests[0][1]["gl"] == "de"
    assert any(url.endswith("/videos") for url, _params in youtube_requests)
    assert service.last_discovery_stats["manual_discovery_source_policy"] == "serpapi_primary_data_api_supplement"
    assert service.last_discovery_stats["serpapi_enriched_count"] == 1


def test_discover_live_with_specs_does_not_save_unvalidated_serpapi_ids(monkeypatch):
    class SerpApiResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "video_results": [
                    {
                        "video_id": "deleted-video",
                        "link": "https://www.youtube.com/watch?v=deleted-video",
                    }
                ]
            }

    class YouTubeResponse:
        status_code = 200
        text = ""

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if "serpapi.com" in url:
            return SerpApiResponse()
        return YouTubeResponse({"items": []})

    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_youtube_key = service.settings.youtube_data_api_key
    original_serpapi_key = service.settings.serpapi_api_key
    service.settings.youtube_data_api_key = "youtube-key"
    service.settings.serpapi_api_key = "serp-key"
    try:
        discovered = service.discover_live_with_specs(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
        )
    finally:
        service.settings.youtube_data_api_key = original_youtube_key
        service.settings.serpapi_api_key = original_serpapi_key

    assert discovered == []
    assert service.last_discovery_stats["serpapi_video_id_count"] == 1
    assert service.last_discovery_stats["serpapi_enriched_count"] == 0


def test_discover_live_with_specs_can_disable_serpapi_for_pulse_path(monkeypatch):
    serpapi_called = False
    youtube_requests = []

    def fake_serpapi_get(*args, **kwargs):
        nonlocal serpapi_called
        serpapi_called = True
        raise AssertionError("SerpAPI should not be called")

    class YouTubeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"items": []}

    def fake_youtube_get(url, params=None, timeout=None):
        _ = timeout
        youtube_requests.append((url, dict(params or {})))
        return YouTubeResponse()

    monkeypatch.setattr("app.services.serpapi_youtube_discovery_service.httpx.get", fake_serpapi_get)
    monkeypatch.setattr("app.services.youtube_discovery_service.httpx.get", fake_youtube_get)
    service = YouTubeDiscoveryService()
    original_youtube_key = service.settings.youtube_data_api_key
    original_serpapi_key = service.settings.serpapi_api_key
    service.settings.youtube_data_api_key = "youtube-key"
    service.settings.serpapi_api_key = "serp-key"
    try:
        discovered = service.discover_live_with_specs(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
            include_serpapi=False,
        )
    finally:
        service.settings.youtube_data_api_key = original_youtube_key
        service.settings.serpapi_api_key = original_serpapi_key

    assert discovered == []
    assert serpapi_called is False
    assert len(youtube_requests) == 1
    assert service.last_discovery_stats["manual_discovery_source_policy"] == "youtube_data_api_only"


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


def test_discover_live_handles_empty_api_results(monkeypatch):
    """Test that discovery returns empty list when YouTube API returns no items."""

    class EmptyResponse:
        status_code = 200
        def json(self):
            return {"items": []}

    def fake_get(*args, **kwargs):
        return EmptyResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "test-key"

    result = service.discover_live_with_specs(
        query_specs=[("hoverair", "en", "US")],
        max_results=10,
    )

    service.settings.youtube_data_api_key = original_api_key
    assert result == []


def test_discover_live_handles_api_errors(monkeypatch):
    """Test that discovery gracefully handles YouTube API errors."""
    call_count = {"value": 0}

    class ErrorResponse:
        status_code = 403
        text = '{"error": {"message": "API key expired"}}'
        def json(self):
            return {"error": {"message": "API key expired"}}

    def fake_get(*args, **kwargs):
        call_count["value"] += 1
        return ErrorResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "invalid-key"

    result = service.discover_live_with_specs(
        query_specs=[("hoverair", "en", "US")],
        max_results=10,
    )

    service.settings.youtube_data_api_key = original_api_key
    assert result == []
    assert call_count["value"] >= 1


def test_discover_live_handles_malformed_api_response(monkeypatch):
    """Test that discovery handles malformed API responses gracefully."""

    class MalformedResponse:
        status_code = 200
        def json(self):
            return {"items": "not a list"}  # Malformed: items should be a list

    def fake_get(*args, **kwargs):
        return MalformedResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "test-key"

    result = service.discover_live_with_specs(
        query_specs=[("hoverair", "en", "US")],
        max_results=10,
    )

    service.settings.youtube_data_api_key = original_api_key
    assert result == []


def test_discover_live_handles_partial_video_data(monkeypatch):
    """Test that discovery skips videos with missing required fields."""

    class PartialDataResponse:
        status_code = 200
        def json(self):
            return {
                "items": [
                    {
                        "id": {"videoId": "valid-video"},
                        "snippet": {
                            "title": "Valid Video",
                            "channelTitle": "Creator",
                            "publishedAt": "2026-04-15T00:00:00Z",
                        },
                    },
                    {
                        "id": {"videoId": ""},  # Missing video ID
                        "snippet": {
                            "title": "Invalid Video",
                            "channelTitle": "Creator",
                            "publishedAt": "2026-04-15T00:00:00Z",
                        },
                    },
                    {
                        "id": {"videoId": "missing-title"},
                        "snippet": {
                            "title": "",  # Missing title
                            "channelTitle": "Creator",
                            "publishedAt": "2026-04-15T00:00:00Z",
                        },
                    },
                    {
                        # Missing id entirely
                        "snippet": {
                            "title": "No ID Video",
                            "channelTitle": "Creator",
                            "publishedAt": "2026-04-15T00:00:00Z",
                        },
                    },
                ]
            }

    def fake_get(*args, **kwargs):
        return PartialDataResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "test-key"

    result = service.discover_live_with_specs(
        query_specs=[("hoverair", "en", "US")],
        max_results=10,
    )

    service.settings.youtube_data_api_key = original_api_key
    assert len(result) == 1
    assert result[0].youtube_video_id == "valid-video"


def test_discover_live_continues_on_timeout(monkeypatch):
    """Test that discovery continues with other queries when one times out."""
    call_count = {"value": 0}

    class SuccessResponse:
        status_code = 200
        def json(self):
            return {
                "items": [
                    {
                        "id": {"videoId": "success-video"},
                        "snippet": {
                            "title": "Success Video",
                            "channelTitle": "Creator",
                            "publishedAt": "2026-04-15T00:00:00Z",
                        },
                    }
                ]
            }

    import httpx

    def fake_get(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise httpx.TimeoutException("Request timed out")
        return SuccessResponse()

    monkeypatch.setattr("httpx.get", fake_get)
    service = YouTubeDiscoveryService()
    original_api_key = service.settings.youtube_data_api_key
    service.settings.youtube_data_api_key = "test-key"

    result = service.discover_live_with_specs(
        query_specs=[
            ("query one", "en", "US"),
            ("query two", "en", "GB"),
        ],
        max_results=10,
    )

    service.settings.youtube_data_api_key = original_api_key
    assert len(result) == 1
    assert result[0].youtube_video_id == "success-video"
    assert call_count["value"] == 2
