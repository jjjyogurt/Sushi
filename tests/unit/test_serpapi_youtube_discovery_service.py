from app.config import get_settings
from app.services.serpapi_youtube_discovery_service import (
    SERPAPI_YOUTUBE_ENDPOINT,
    SerpApiYouTubeDiscoveryService,
)


def test_serpapi_youtube_request_uses_localized_upload_date_params(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "video_results": [
                    {
                        "video_id": "de-video",
                        "link": "https://www.youtube.com/watch?v=de-video",
                    }
                ]
            }

    def fake_get(url, params=None, timeout=None):
        requests_seen.append((url, dict(params or {}), timeout))
        return FakeResponse()

    monkeypatch.setattr("app.services.serpapi_youtube_discovery_service.httpx.get", fake_get)
    settings = get_settings()
    original_key = settings.serpapi_api_key
    settings.serpapi_api_key = "serp-key"
    try:
        result = SerpApiYouTubeDiscoveryService(settings).discover_video_ids(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
        )
    finally:
        settings.serpapi_api_key = original_key

    assert [hit.video_id for hit in result.hits] == ["de-video"]
    assert requests_seen == [
        (
            SERPAPI_YOUTUBE_ENDPOINT,
            {
                "engine": "youtube",
                "search_query": "HOVERAir",
                "sp": "CAI=",
                "api_key": "serp-key",
                "hl": "de",
                "gl": "de",
            },
            20.0,
        )
    ]


def test_serpapi_youtube_parser_includes_localized_flat_video_sections(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "video_results": [
                    {
                        "video_id": "primary-video",
                        "link": "https://www.youtube.com/watch?v=primary-video",
                    }
                ],
                "neueste_videos_von_hover_air": [
                    {
                        "video_id": "localized-video",
                        "link": "https://www.youtube.com/watch?v=localized-video",
                    }
                ],
                "shorts_results": [
                    {
                        "shorts": [
                            {
                                "video_id": "short-video",
                                "link": "https://www.youtube.com/shorts/short-video",
                            }
                        ]
                    }
                ],
            }

    monkeypatch.setattr(
        "app.services.serpapi_youtube_discovery_service.httpx.get",
        lambda *args, **kwargs: FakeResponse(),
    )
    settings = get_settings()
    original_key = settings.serpapi_api_key
    settings.serpapi_api_key = "serp-key"
    try:
        result = SerpApiYouTubeDiscoveryService(settings).discover_video_ids(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
        )
    finally:
        settings.serpapi_api_key = original_key

    assert [hit.video_id for hit in result.hits] == ["primary-video", "localized-video"]
    assert result.stats.raw_count == 2


def test_serpapi_youtube_stops_after_max_results(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "video_results": [
                    {
                        "video_id": "first-video",
                        "link": "https://www.youtube.com/watch?v=first-video",
                    }
                ]
            }

    def fake_get(url, params=None, timeout=None):
        _ = (url, timeout)
        requests_seen.append(dict(params or {}))
        return FakeResponse()

    monkeypatch.setattr("app.services.serpapi_youtube_discovery_service.httpx.get", fake_get)
    settings = get_settings()
    original_key = settings.serpapi_api_key
    settings.serpapi_api_key = "serp-key"
    try:
        result = SerpApiYouTubeDiscoveryService(settings).discover_video_ids(
            query_specs=[
                ("HOVERAir", "de", "DE"),
                ("HOVERAir", "en", "DE"),
            ],
            max_results=1,
        )
    finally:
        settings.serpapi_api_key = original_key

    assert [hit.video_id for hit in result.hits] == ["first-video"]
    assert len(requests_seen) == 1
    assert requests_seen[0]["hl"] == "de"


def test_serpapi_youtube_timeout_returns_partial_stats(monkeypatch):
    import httpx

    def fake_get(*args, **kwargs):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr("app.services.serpapi_youtube_discovery_service.httpx.get", fake_get)
    settings = get_settings()
    original_key = settings.serpapi_api_key
    settings.serpapi_api_key = "serp-key"
    try:
        result = SerpApiYouTubeDiscoveryService(settings).discover_video_ids(
            query_specs=[("HOVERAir", "de", "DE")],
            max_results=10,
        )
    finally:
        settings.serpapi_api_key = original_key

    assert result.hits == []
    assert result.stats.error_count == 1
