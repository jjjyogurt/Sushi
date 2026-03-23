from datetime import datetime, timezone

from app.repositories.video_repository import VideoRepository


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

