from datetime import datetime, timezone

from app.models.analysis_result import AnalysisResult
from app.models.chat import ChatMessage, ChatSession
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.incident import Alert, Incident
from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate
from app.models.video_comment import VideoComment
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.monitor import MonitorProfileCreate
from app.utils.text import normalize_title, title_fingerprint
from app.utils.json_codec import encode_json


def _seed_profile_with_video_tree(db_session):
    profile = MonitorProfile(
        name="Old Project",
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["Japan"]),
        languages=encode_json(["ja"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    title = "HoverAir X1 review"
    video = VideoCandidate(
        monitor_profile_id=profile.id,
        youtube_video_id="old-japan-video",
        video_url="https://www.youtube.com/watch?v=old-japan-video",
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

    analysis = AnalysisResult(
        video_candidate_id=video.id,
        analysis_version="v1",
        language="en",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="test transcript",
        summary_text="test summary",
        translated_summary="test summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.LOW,
        confidence_score="0.7",
        evidence_json="[]",
        insights_json="[]",
        error_message="",
    )
    chat_session = ChatSession(video_candidate_id=video.id, created_by="tester")
    incident = Incident(video_candidate_id=video.id, severity=RiskLevel.LOW, notes="seed")
    comment = VideoComment(
        video_candidate_id=video.id,
        youtube_comment_id="seed-comment-1",
        parent_comment_id="",
        author_name="tester",
        text="seed",
        like_count=0,
        published_at=datetime.now(timezone.utc),
        updated_at_remote=datetime.now(timezone.utc),
        is_reply=False,
    )
    db_session.add_all([analysis, chat_session, incident, comment])
    db_session.commit()
    db_session.refresh(chat_session)
    db_session.refresh(incident)

    chat_message = ChatMessage(chat_session_id=chat_session.id, role="user", content="seed")
    alert = Alert(incident_id=incident.id, channel="inbox", message="seed")
    db_session.add_all([chat_message, alert])
    db_session.commit()

    return profile.id


def test_delete_profile_cascades_video_related_rows_and_new_japanese_project_starts_clean(db_session):
    old_profile_id = _seed_profile_with_video_tree(db_session)

    monitor_repository = MonitorRepository(db_session)
    deleted = monitor_repository.delete(old_profile_id)
    assert deleted is True

    assert db_session.query(VideoCandidate).count() == 0
    assert db_session.query(AnalysisResult).count() == 0
    assert db_session.query(ChatSession).count() == 0
    assert db_session.query(ChatMessage).count() == 0
    assert db_session.query(Incident).count() == 0
    assert db_session.query(Alert).count() == 0
    assert db_session.query(VideoComment).count() == 0

    japanese_profile = monitor_repository.create(
        MonitorProfileCreate(
            name="Mock HOVERAir Japan",
            brand_keywords=["HOVERAir X1", "X1 PRO"],
            markets=["Japan"],
            languages=["ja"],
            key_products=[],
            alert_sensitivity="medium",
        )
    )
    video_repository = VideoRepository(db_session)
    new_profile_videos = video_repository.list(monitor_profile_id=japanese_profile.id)
    assert new_profile_videos == []
