from datetime import datetime, timezone

from app.models.monitor_profile import MonitorProfile
from app.repositories.video_repository import VideoRepository
from app.utils.json_codec import encode_json


def create_profile(db_session, name: str):
    profile = MonitorProfile(
        name=name,
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def test_same_video_id_upserts_without_duplicate(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    created = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="abc123",
        video_url="https://youtu.be/abc123",
        title="HoverAir review original",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.6,
        relevance_reason="title matched",
    )
    updated = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="abc123",
        video_url="https://youtu.be/abc123",
        title="HoverAir review updated title",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.7,
        relevance_reason="title matched",
    )

    all_items = repository.list(monitor_profile_id=monitor_profile.id)
    assert created.id == updated.id
    assert len(all_items) == 1
    assert all_items[0].title == "HoverAir review updated title"


def test_same_title_different_video_id_creates_two_records(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    shared_title = "HoverAir overview"
    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="id-1",
        video_url="https://youtu.be/id-1",
        title=shared_title,
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.55,
        relevance_reason="keyword",
    )
    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="id-2",
        video_url="https://youtu.be/id-2",
        title=shared_title,
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.58,
        relevance_reason="keyword",
    )

    filtered = repository.list(monitor_profile_id=monitor_profile.id, title_filter="overview")
    assert len(filtered) == 2


def test_list_without_profile_filter_returns_all_projects(db_session, monitor_profile):
    second_profile = create_profile(db_session, "Second Profile")
    repository = VideoRepository(db_session)

    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="global-1",
        video_url="https://youtu.be/global-1",
        title="Global queue one",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.4,
        relevance_reason="seed",
    )
    repository.upsert_candidate(
        monitor_profile_id=second_profile.id,
        youtube_video_id="global-2",
        video_url="https://youtu.be/global-2",
        title="Global queue two",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        relevance_reason="seed",
    )

    all_items = repository.list()
    assert len(all_items) == 2
    assert {item.monitor_profile_id for item in all_items} == {monitor_profile.id, second_profile.id}


def test_upsert_keeps_original_project_owner_for_same_video_id(db_session, monitor_profile):
    second_profile = create_profile(db_session, "Second Owner")
    repository = VideoRepository(db_session)

    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="owner-lock",
        video_url="https://youtu.be/owner-lock",
        title="Owner original",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.6,
        relevance_reason="seed",
    )
    updated = repository.upsert_candidate(
        monitor_profile_id=second_profile.id,
        youtube_video_id="owner-lock",
        video_url="https://youtu.be/owner-lock",
        title="Owner update",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.7,
        relevance_reason="seed",
    )

    assert updated.monitor_profile_id == monitor_profile.id

