from unittest.mock import MagicMock

from app.config import get_settings
from app.services.discovery_keyword_service import DiscoveryKeywordService


def test_fallback_plan_japanese_german_regions():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["ja", "de"],
        markets=["Japan", "Germany"],
    )
    pairs = {(lang, reg) for _q, lang, reg in plan.query_specs}
    assert ("ja", "JP") in pairs
    assert ("de", "DE") in pairs
    lowered = [m.lower() for m in plan.match_keywords]
    assert any("hoverair" in m for m in lowered)


def test_gemini_plan_merges_missing_pairs_for_jp_de(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    gemini = MagicMock()
    gemini.plan_youtube_discovery_queries.return_value = {
        "queries": [
            {"q": "HOVERAir レビュー", "relevanceLanguage": "ja", "regionCode": "JP"},
        ],
        "match_keywords": ["HOVERAir X1", "ホバーエアー"],
    }
    service = DiscoveryKeywordService(settings, gemini_client=gemini)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["ja", "de"],
        markets=["Japan", "Germany"],
    )
    pairs = {(lang, reg) for _q, lang, reg in plan.query_specs}
    assert ("ja", "JP") in pairs
    assert ("de", "DE") in pairs
    assert "ホバーエアー" in plan.match_keywords
    gemini.plan_youtube_discovery_queries.assert_called_once()
