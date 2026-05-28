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


def test_fallback_plan_preserves_user_keywords_as_separate_queries():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HoverAir", "X1 Pro Max"],
        languages=["en"],
        markets=["US"],
    )
    queries = [q for q, _lang, _reg in plan.query_specs]
    lowered = [query.lower() for query in queries]
    assert "hoverair" in lowered
    assert "x1 pro max" in lowered
    assert "hoverair x1 pro max" not in lowered


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


def test_gemini_plan_keeps_exact_user_keyword_specs(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    gemini = MagicMock()
    gemini.plan_youtube_discovery_queries.return_value = {
        "queries": [
            {"q": "best pocket drone review", "relevanceLanguage": "en", "regionCode": "US"},
        ],
        "match_keywords": ["pocket drone"],
    }
    service = DiscoveryKeywordService(settings, gemini_client=gemini)
    plan = service.build_plan(
        keywords=["HoverAir", "X1 Pro Max"],
        languages=["en"],
        markets=["US"],
    )
    queries = [q.lower() for q, _lang, _reg in plan.query_specs]
    assert "hoverair" in queries
    assert "x1 pro max" in queries
    assert "best pocket drone review" in queries


def test_fallback_when_gemini_raises_exception(monkeypatch):
    """Test that discovery falls back to keyword-based plan when Gemini raises exception."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    gemini = MagicMock()
    gemini.plan_youtube_discovery_queries.side_effect = RuntimeError("Gemini API error")

    service = DiscoveryKeywordService(settings, gemini_client=gemini)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["en"],
        markets=["US"],
    )

    # Should have fallback specs based on keywords
    assert len(plan.query_specs) >= 1
    assert all("hoverair" in q.lower() for q, _lang, _reg in plan.query_specs)
    assert "HOVERAir X1" in plan.match_keywords
    gemini.plan_youtube_discovery_queries.assert_called_once()


def test_fallback_when_gemini_returns_empty_queries(monkeypatch):
    """Test that discovery falls back when Gemini returns empty queries list."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    gemini = MagicMock()
    gemini.plan_youtube_discovery_queries.return_value = {
        "queries": [],  # Empty list
        "match_keywords": [],
    }

    service = DiscoveryKeywordService(settings, gemini_client=gemini)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["en", "de"],
        markets=["US", "Germany"],
    )

    # Should fallback to keyword-based specs
    assert len(plan.query_specs) >= 1
    pairs = {(lang, reg) for _q, lang, reg in plan.query_specs}
    assert ("en", "US") in pairs or ("en", "DE") in pairs


def test_fallback_when_gemini_returns_malformed_response(monkeypatch):
    """Test that discovery falls back when Gemini returns malformed data."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    gemini = MagicMock()
    gemini.plan_youtube_discovery_queries.return_value = {
        "queries": [
            {"q": "", "relevanceLanguage": "en", "regionCode": "US"},  # Empty query
            {"relevanceLanguage": "de", "regionCode": "DE"},  # Missing query string
            "not a dict",  # Invalid item type
        ],
        "match_keywords": ["HOVERAir X1"],
    }

    service = DiscoveryKeywordService(settings, gemini_client=gemini)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["en"],
        markets=["US"],
    )

    # Should have at least fallback specs
    assert len(plan.query_specs) >= 1
    assert "HOVERAir X1" in plan.match_keywords


def test_fallback_when_no_gemini_client():
    """Test that discovery uses fallback when no Gemini client is provided."""
    settings = get_settings()
    # No gemini_api_key set, so _gemini_ready() should return False
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["en", "ja"],
        markets=["US", "Japan"],
    )

    # Should have fallback specs for all language/market pairs
    assert len(plan.query_specs) >= 1
    pairs = {(lang, reg) for _q, lang, reg in plan.query_specs}
    # Should have at least one spec
    assert len(pairs) >= 1


def test_fallback_when_gemini_api_key_missing(monkeypatch):
    """Test that discovery uses fallback when API key is empty."""
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)
    mock_gemini = MagicMock()

    service = DiscoveryKeywordService(settings, gemini_client=mock_gemini)
    plan = service.build_plan(
        keywords=["hoverair"],
        languages=["en"],
        markets=["global"],
    )

    # Gemini client should not be called when API key is missing
    mock_gemini.plan_youtube_discovery_queries.assert_not_called()
    assert len(plan.query_specs) >= 1


def test_empty_keywords_returns_empty_plan():
    """Test that empty keywords returns empty plan."""
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=[],
        languages=["en"],
        markets=["US"],
    )

    assert plan.query_specs == []
    assert plan.match_keywords == []


def test_whitespace_only_keywords_returns_empty_plan():
    """Test that whitespace-only keywords are treated as empty."""
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["   ", "", "  ", ""],
        languages=["en"],
        markets=["US"],
    )

    assert plan.query_specs == []
    assert plan.match_keywords == []
