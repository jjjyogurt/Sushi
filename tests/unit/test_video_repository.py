from datetime import datetime, timezone

from app.models.analysis_result import AnalysisResult
from app.models.chat import ChatMessage, ChatSession
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.incident import Alert, Incident
from app.models.monitor_profile import MonitorProfile
from app.models.video_comment import VideoComment
from app.models.video_watchlist_entry import VideoWatchlistEntry
from app.repositories.video_repository import VideoRepository
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

    all_items = repository.list(monitor_profile_id=monitor_profile.id)
    assert len(all_items) == 2


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


def test_list_filters_by_title_query_case_insensitive(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="title-match-1",
        video_url="https://youtu.be/title-match-1",
        title="HoverAir X1 Pro Full Review",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        relevance_reason="seed",
    )
    repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="title-miss-1",
        video_url="https://youtu.be/title-miss-1",
        title="DJI Neo Flight Tips",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        relevance_reason="seed",
    )

    filtered = repository.list(monitor_profile_id=monitor_profile.id, title_query="  hoverair x1 pro ")
    assert [item.youtube_video_id for item in filtered] == ["title-match-1"]


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


def test_list_filters_by_risk_level_on_latest_analysis(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    medium_video = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="risk-medium",
        video_url="https://youtu.be/risk-medium",
        title="Risk medium",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.7,
        relevance_reason="seed",
    )
    low_video = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="risk-low",
        video_url="https://youtu.be/risk-low",
        title="Risk low",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        relevance_reason="seed",
    )
    db_session.add_all(
        [
            AnalysisResult(
                video_candidate_id=medium_video.id,
                analysis_version="v1",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.NEUTRAL,
                risk_level=RiskLevel.MEDIUM,
                confidence_score="0.8",
                evidence_json="[]",
                insights_json="[]",
                error_message="",
            ),
            AnalysisResult(
                video_candidate_id=low_video.id,
                analysis_version="v1",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.POSITIVE,
                risk_level=RiskLevel.LOW,
                confidence_score="0.8",
                evidence_json="[]",
                insights_json="[]",
                error_message="",
            ),
        ]
    )
    db_session.commit()

    filtered = repository.list(monitor_profile_id=monitor_profile.id, risk_level="medium")
    assert [item.youtube_video_id for item in filtered] == ["risk-medium"]


def test_list_filters_by_sentiment_on_latest_analysis(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    negative_video = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="sentiment-negative",
        video_url="https://youtu.be/sentiment-negative",
        title="Sentiment negative",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.7,
        relevance_reason="seed",
    )
    neutral_video = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="sentiment-neutral",
        video_url="https://youtu.be/sentiment-neutral",
        title="Sentiment neutral",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.6,
        relevance_reason="seed",
    )
    db_session.add_all(
        [
            AnalysisResult(
                video_candidate_id=negative_video.id,
                analysis_version="v1",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.NEGATIVE,
                risk_level=RiskLevel.HIGH,
                confidence_score="0.8",
                evidence_json="[]",
                insights_json="[]",
                error_message="",
            ),
            AnalysisResult(
                video_candidate_id=neutral_video.id,
                analysis_version="v1",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.NEUTRAL,
                risk_level=RiskLevel.MEDIUM,
                confidence_score="0.8",
                evidence_json="[]",
                insights_json="[]",
                error_message="",
            ),
        ]
    )
    db_session.commit()

    filtered = repository.list(monitor_profile_id=monitor_profile.id, sentiment="negative")
    assert [item.youtube_video_id for item in filtered] == ["sentiment-negative"]


def test_delete_removes_video_dependencies(db_session, monitor_profile):
    repository = VideoRepository(db_session)
    video = repository.upsert_candidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="delete-me",
        video_url="https://youtu.be/delete-me",
        title="Delete candidate",
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.5,
        relevance_reason="seed",
    )

    analysis = AnalysisResult(
        video_candidate_id=video.id,
        analysis_version="v1",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="",
        summary_text="",
        translated_summary="",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.8",
        evidence_json="[]",
        insights_json="[]",
        error_message="",
    )
    incident = Incident(video_candidate_id=video.id, severity="high", owner="owner-a", notes="note")
    chat_session = ChatSession(video_candidate_id=video.id, created_by="u1")
    watch = VideoWatchlistEntry(video_candidate_id=video.id, user_id="u1")
    now = datetime.now(timezone.utc)
    comment = VideoComment(
        video_candidate_id=video.id,
        youtube_comment_id="c1",
        text="test",
        like_count=0,
        published_at=now,
        updated_at_remote=now,
        is_reply=False,
    )
    db_session.add_all([analysis, incident, chat_session, watch, comment])
    db_session.flush()
    alert = Alert(incident_id=incident.id, channel="inbox", message="alert")
    chat_message = ChatMessage(chat_session_id=chat_session.id, role="user", content="hello")
    db_session.add_all([alert, chat_message])
    db_session.commit()

    deleted = repository.delete(video.id)
    assert deleted is True
    assert repository.get_by_id(video.id) is None
    assert db_session.query(AnalysisResult).filter(AnalysisResult.video_candidate_id == video.id).count() == 0
    assert db_session.query(Incident).filter(Incident.video_candidate_id == video.id).count() == 0
    assert db_session.query(ChatSession).filter(ChatSession.video_candidate_id == video.id).count() == 0
    assert db_session.query(VideoWatchlistEntry).filter(VideoWatchlistEntry.video_candidate_id == video.id).count() == 0
    assert db_session.query(VideoComment).filter(VideoComment.video_candidate_id == video.id).count() == 0
