from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.models.monitor_profile import MonitorProfile
from app.models.enums import QueueState
from app.schemas.video import VideoBulkAddCandidate
from app.services.triage_service import TriageService
from app.services.types import DiscoveredVideo
from app.utils.json_codec import encode_json


def create_profile(db_session, name: str):
    profile = MonitorProfile(
        name=name,
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def test_discover_respects_publish_window_with_mock_seed(db_session, monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    service = TriageService(db_session)
    now = datetime.now(timezone.utc)
    after = now - timedelta(hours=3)
    before = now + timedelta(minutes=2)
    try:
        results = service.discover_for_profile(
            monitor_profile_id=monitor_profile.id,
            max_results=20,
            published_after=after,
            published_before=before,
        )
        assert len(results) == 1
    finally:
        settings.enable_mock_discovery = original


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


def test_search_candidates_allows_same_video_in_another_project(db_session, monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True

    second_profile = create_profile(db_session, "Second Project")
    service = TriageService(db_session)
    fixed_candidate = DiscoveredVideo(
        youtube_video_id="conflict-fixed",
        video_url="https://www.youtube.com/watch?v=conflict-fixed",
        title="Conflict Test Video",
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        description="conflict seed",
    )
    service.discovery_service.mock_seed_for_keywords = lambda **kwargs: [fixed_candidate]

    initial_results = service.search_candidates(
        monitor_profile_id=monitor_profile.id,
        query="hoverair",
        max_results=1,
    )
    candidate = initial_results[0]
    service.video_repository.upsert_candidate(
        monitor_profile_id=second_profile.id,
        youtube_video_id=candidate["youtube_video_id"],
        video_url=candidate["video_url"],
        title=candidate["title"],
        channel_name=candidate["channel_name"],
        language=candidate["language"],
        published_at=candidate["published_at"],
        relevance_score=candidate["relevance_score"],
        relevance_reason=candidate["relevance_reason"],
    )

    results = service.search_candidates(monitor_profile_id=monitor_profile.id, query="hoverair", max_results=1)
    assert len(results) == 1
    assert results[0]["can_add"] is True
    assert results[0]["block_reason"] is None

    settings.enable_mock_discovery = original


def test_bulk_add_candidates_persists_selected_search_candidates(db_session, monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True

    service = TriageService(db_session)
    search_results = service.search_candidates(
        monitor_profile_id=monitor_profile.id,
        query="hoverair review",
        max_results=2,
    )
    addable = next(item for item in search_results if item["can_add"])

    candidate = VideoBulkAddCandidate(
        youtube_video_id=addable["youtube_video_id"],
        video_url=addable["video_url"],
        title=addable["title"],
        channel_name=addable["channel_name"],
        language=addable["language"],
        published_at=addable["published_at"] or datetime.now(timezone.utc),
        description=addable["description"],
    )
    persisted = service.add_bulk_candidates(
        monitor_profile_id=monitor_profile.id,
        candidates=[candidate],
    )

    assert len(persisted) == 1
    assert persisted[0].monitor_profile_id == monitor_profile.id
    assert persisted[0].youtube_video_id == candidate.youtube_video_id

    settings.enable_mock_discovery = original


def test_discover_scores_using_key_products(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Key Product Project",
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json(["x1 promax"]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="key-product-hit",
            video_url="https://www.youtube.com/watch?v=key-product-hit",
            title="X1 Promax long-term review",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="Hands on with x1 promax",
        )
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=1)
        assert len(discovered) == 1
        assert "x1 promax" in discovered[0].relevance_reason.lower()
    finally:
        settings.enable_mock_discovery = original_mock


def test_discover_requires_key_product_match_when_configured(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Aqua Discovery Project",
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json(["aqua"]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="promax-result",
            video_url="https://www.youtube.com/watch?v=promax-result",
            title="HoverAir X1 ProMax review",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="HoverAir review",
        ),
        DiscoveredVideo(
            youtube_video_id="aqua-result",
            video_url="https://www.youtube.com/watch?v=aqua-result",
            title="HoverAir Aqua waterproof drone first look",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="HoverAir Aqua details",
        ),
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=20)
        assert [item.youtube_video_id for item in discovered] == ["aqua-result"]
    finally:
        settings.enable_mock_discovery = original_mock


def test_discover_filters_out_titles_without_keyword_match(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Discovery Filter Project",
        brand_keywords=encode_json(["hoverair", "x1"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="keep-hoverair-video",
            video_url="https://www.youtube.com/watch?v=keep-hoverair-video",
            title="HoverAir X1 full review",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="HoverAir X1 deep dive",
        ),
        DiscoveredVideo(
            youtube_video_id="drop-non-brand-video",
            video_url="https://www.youtube.com/watch?v=drop-non-brand-video",
            title="DJI Mini 5 Pro review",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="No target keywords",
        ),
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=20)
        assert [item.youtube_video_id for item in discovered] == ["keep-hoverair-video"]
    finally:
        settings.enable_mock_discovery = original_mock


def test_discover_filters_use_word_boundaries_for_short_keywords(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Boundary Filter Project",
        brand_keywords=encode_json(["x1"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="drop-x10-video",
            video_url="https://www.youtube.com/watch?v=drop-x10-video",
            title="Hands-on with X10 camera drone",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="Should not match x1 keyword",
        ),
        DiscoveredVideo(
            youtube_video_id="keep-x1-video",
            video_url="https://www.youtube.com/watch?v=keep-x1-video",
            title="X1 camera drone first look",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="Should match x1 keyword",
        ),
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=20)
        assert [item.youtube_video_id for item in discovered] == ["keep-x1-video"]
    finally:
        settings.enable_mock_discovery = original_mock


def test_discover_filters_expand_slash_keywords(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Slash Keyword Project",
        brand_keywords=encode_json(["x1 pro/promax"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="keep-promax-video",
            video_url="https://www.youtube.com/watch?v=keep-promax-video",
            title="X1 Promax long-term review",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            description="Should match slash-expanded keyword",
        )
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=20)
        assert [item.youtube_video_id for item in discovered] == ["keep-promax-video"]
    finally:
        settings.enable_mock_discovery = original_mock


def test_discover_keeps_localized_title_when_language_is_non_latin(db_session):
    settings = get_settings()
    original_mock = settings.enable_mock_discovery
    settings.enable_mock_discovery = True
    profile = MonitorProfile(
        name="Japanese Discovery Project",
        brand_keywords=encode_json(["HOVERAir", "X1", "スマート"]),
        markets=encode_json(["Japan"]),
        languages=encode_json(["ja"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    service = TriageService(db_session)
    service.discovery_service.mock_seed_for_profile = lambda profile, max_results: [
        DiscoveredVideo(
            youtube_video_id="jp-smart-video",
            video_url="https://www.youtube.com/watch?v=jp-smart-video",
            title="HOVERAir X1 スマート レビュー",
            channel_name="JP Creator",
            language="ja",
            published_at=datetime.now(timezone.utc),
            description="Japanese localized keyword match",
        )
    ]

    try:
        discovered = service.discover_for_profile(monitor_profile_id=profile.id, max_results=20)
        assert [item.youtube_video_id for item in discovered] == ["jp-smart-video"]
    finally:
        settings.enable_mock_discovery = original_mock
