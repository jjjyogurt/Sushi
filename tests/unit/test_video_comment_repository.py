from datetime import datetime, timezone

from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate
from app.repositories.video_comment_repository import VideoCommentRepository
from app.utils.json_codec import encode_json
from app.utils.text import normalize_title, title_fingerprint


def _create_profile(db_session, *, name: str, owner_user_id: str) -> MonitorProfile:
    profile = MonitorProfile(
        name=name,
        owner_user_id=owner_user_id,
        brand_keywords=encode_json([]),
        markets=encode_json([]),
        languages=encode_json([]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def _create_video(db_session, profile: MonitorProfile, *, youtube_video_id: str) -> VideoCandidate:
    title = "Shared YouTube Review"
    video = VideoCandidate(
        monitor_profile_id=profile.id,
        youtube_video_id=youtube_video_id,
        video_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
        title=title,
        normalized_title=normalize_title(title),
        title_fingerprint=title_fingerprint(title),
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.9,
        relevance_reason="seed",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def _comment_payload(*, comment_id: str, text: str = "Helpful comment"):
    now = datetime.now(timezone.utc)
    return {
        "youtube_comment_id": comment_id,
        "parent_comment_id": "",
        "author_name": "Viewer",
        "text": text,
        "like_count": 1,
        "published_at": now,
        "updated_at_remote": now,
        "is_reply": False,
    }


def test_replace_for_video_allows_same_youtube_comment_for_different_video_candidates(db_session):
    first_profile = _create_profile(db_session, name="First", owner_user_id="Sushi_1")
    second_profile = _create_profile(db_session, name="Second", owner_user_id="Sushi_2")
    first_video = _create_video(db_session, first_profile, youtube_video_id="same-video")
    second_video = _create_video(db_session, second_profile, youtube_video_id="same-video")
    repository = VideoCommentRepository(db_session)

    assert repository.replace_for_video(
        video_candidate_id=first_video.id,
        comments=[_comment_payload(comment_id="shared-comment", text="First account copy")],
    ) == 1
    assert repository.replace_for_video(
        video_candidate_id=second_video.id,
        comments=[_comment_payload(comment_id="shared-comment", text="Second account copy")],
    ) == 1

    assert repository.list_texts_for_video(video_candidate_id=first_video.id) == ["First account copy"]
    assert repository.list_texts_for_video(video_candidate_id=second_video.id) == ["Second account copy"]


def test_replace_for_video_deduplicates_repeated_comment_ids_in_same_payload(db_session, monitor_profile):
    video = _create_video(db_session, monitor_profile, youtube_video_id="dedupe-video")
    repository = VideoCommentRepository(db_session)

    stored_count = repository.replace_for_video(
        video_candidate_id=video.id,
        comments=[
            _comment_payload(comment_id="repeated-comment", text="First copy"),
            _comment_payload(comment_id="repeated-comment", text="Second copy"),
            _comment_payload(comment_id="", text="Missing id"),
        ],
    )

    assert stored_count == 1
    assert repository.list_texts_for_video(video_candidate_id=video.id) == ["First copy"]
