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


def test_fallback_plan_does_not_add_localized_german_variants():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HOVERAIR X1 PRO/PROMAX"],
        languages=["de"],
        markets=["Germany"],
    )

    queries = [q for q, lang, reg in plan.query_specs if lang == "de" and reg == "DE"]
    lowered = [query.lower() for query in queries]
    assert lowered == ["hoverair x1 pro/promax"]
    assert "hoverair x1 pro/promax test" not in lowered
    assert "hoverair x1 pro/promax deutschland" not in lowered


def test_fallback_plan_does_not_add_localized_japanese_variants():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["ja"],
        markets=["Japan"],
    )

    queries = [q for q, lang, reg in plan.query_specs if lang == "ja" and reg == "JP"]
    assert queries == ["HOVERAir X1"]


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


def test_fallback_plan_includes_exact_keywords_for_each_language():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    keywords = [f"Product {index}" for index in range(1, 10)]
    plan = service.build_plan(
        keywords=keywords,
        languages=["en", "de"],
        markets=["Germany"],
    )

    specs = set(plan.query_specs)
    for keyword in keywords:
        assert (keyword, "en", "DE") in specs
        assert (keyword, "de", "DE") in specs


def test_fallback_plan_prioritizes_non_english_before_english_fallback():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HoverAir", "X1 Pro Max", "Beacon"],
        languages=["de", "fr", "en", "ja", "es"],
        markets=["Germany"],
    )

    assert {(lang, reg) for _q, lang, reg in plan.query_specs} == {
        ("de", "DE"),
        ("fr", "DE"),
        ("en", "DE"),
    }
    assert [(lang, reg) for _q, lang, reg in plan.query_specs[:3]] == [
        ("de", "DE"),
        ("de", "DE"),
        ("de", "DE"),
    ]
    assert len(plan.query_specs) == 9


def test_fallback_plan_uses_first_three_languages_when_english_not_configured():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HoverAir"],
        languages=["de", "fr", "ja", "es"],
        markets=["Germany"],
    )

    assert [(lang, reg) for _q, lang, reg in plan.query_specs] == [
        ("de", "DE"),
        ("fr", "DE"),
        ("ja", "DE"),
    ]


def test_gemini_is_not_used_for_discovery_query_expansion(monkeypatch):
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
    assert "best pocket drone review" not in queries
    assert "pocket drone" not in [keyword.lower() for keyword in plan.match_keywords]
    gemini.plan_youtube_discovery_queries.assert_not_called()


def test_gemini_error_cannot_affect_keyword_only_discovery(monkeypatch):
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

    assert len(plan.query_specs) == 1
    assert plan.query_specs == [("HOVERAir X1", "en", "US")]
    assert plan.match_keywords == ["HOVERAir X1"]
    gemini.plan_youtube_discovery_queries.assert_not_called()


def test_fallback_when_no_gemini_client():
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["HOVERAir X1"],
        languages=["en", "ja"],
        markets=["US", "Japan"],
    )

    assert len(plan.query_specs) == 4
    pairs = {(lang, reg) for _q, lang, reg in plan.query_specs}
    assert pairs == {("en", "US"), ("en", "JP"), ("ja", "US"), ("ja", "JP")}


def test_fallback_when_gemini_api_key_missing(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)
    mock_gemini = MagicMock()

    service = DiscoveryKeywordService(settings, gemini_client=mock_gemini)
    plan = service.build_plan(
        keywords=["hoverair"],
        languages=["en"],
        markets=["global"],
    )

    mock_gemini.plan_youtube_discovery_queries.assert_not_called()
    assert plan.query_specs == [("hoverair", "en", "")]


def test_empty_keywords_returns_empty_plan():
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
    settings = get_settings()
    service = DiscoveryKeywordService(settings, gemini_client=None)
    plan = service.build_plan(
        keywords=["   ", "", "  ", ""],
        languages=["en"],
        markets=["US"],
    )

    assert plan.query_specs == []
    assert plan.match_keywords == []
