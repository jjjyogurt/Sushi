from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.base import Base
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.repositories.video_repository import VideoRepository
from app.services.project_insights_service import ProjectInsightsService
from app.services.youtube_video_stats_service import YouTubeVideoStatsService
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


@pytest.fixture()
def insights_db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(insights_db_session, monkeypatch):
    def use_fallback_payload(*args, **kwargs):
        return kwargs["fallback_payload"]

    monkeypatch.setattr(ProjectInsightsService, "_build_payload_with_gemini", use_fallback_payload)
    monkeypatch.setattr(YouTubeVideoStatsService, "fetch_view_counts", lambda self, youtube_video_ids: {})

    def override_db():
        yield insights_db_session

    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _seed_video(db_session, profile_id: int, youtube_video_id: str):
    repository = VideoRepository(db_session)
    return repository.upsert_candidate(
        monitor_profile_id=profile_id,
        youtube_video_id=youtube_video_id,
        video_url=f"https://youtu.be/{youtube_video_id}",
        title=f"Video {youtube_video_id}",
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.6,
        relevance_reason="seed",
    )


def test_refresh_insights_uses_only_completed_with_db_transcripts(client, insights_db_session):
    profile = create_profile(insights_db_session, "Insights Profile")
    video_completed = _seed_video(insights_db_session, profile.id, "insight-completed")
    video_failed = _seed_video(insights_db_session, profile.id, "insight-failed")
    video_empty_transcript = _seed_video(insights_db_session, profile.id, "insight-empty-transcript")

    insights_db_session.add_all(
        [
            AnalysisResult(
                video_candidate_id=video_completed.id,
                analysis_version="v1",
                language="en",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="Stored transcript from DB only.",
                summary_text="solid",
                translated_summary="solid",
                summary_headline="Strong positive creator signal.",
                summary_body="The product performed as expected in core tasks.",
                sentiment=Sentiment.POSITIVE,
                risk_level=RiskLevel.LOW,
                confidence_score="0.92",
                evidence_json="[]",
                insights_json=encode_json(
                    {
                        "praise_points": ["Stable tracking in windy conditions."],
                        "criticism_points": ["Battery life is shorter than expected."],
                        "action_recommendation": "Publish realistic battery guidance in campaign copy.",
                    }
                ),
                error_message="",
            ),
            AnalysisResult(
                video_candidate_id=video_failed.id,
                analysis_version="v1",
                language="en",
                model_name="test-model",
                status=AnalysisStatus.FAILED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.NEUTRAL,
                risk_level=RiskLevel.MEDIUM,
                confidence_score="0.0",
                evidence_json="[]",
                insights_json="{}",
                error_message="provider unavailable",
            ),
            AnalysisResult(
                video_candidate_id=video_empty_transcript.id,
                analysis_version="v1",
                language="en",
                model_name="test-model",
                status=AnalysisStatus.COMPLETED,
                transcript_text="",
                summary_text="",
                translated_summary="",
                sentiment=Sentiment.NEGATIVE,
                risk_level=RiskLevel.HIGH,
                confidence_score="0.5",
                evidence_json="[]",
                insights_json="{}",
                error_message="",
            ),
        ]
    )
    insights_db_session.commit()

    response = client.post(f"/monitor-profiles/{profile.id}/insights/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["monitor_profile_id"] == profile.id
    assert payload["analyzed_video_count"] == 1
    assert payload["total_video_count"] == 3
    assert payload["excluded_video_count"] == 2
    assert payload["coverage_pct"] == 33.3
    assert "analysis_not_completed:1" in payload["excluded_reasons"]
    assert "transcript_missing_in_db:1" in payload["excluded_reasons"]
    assert payload["praise_points"] == ["Stable tracking in windy conditions."]
    assert payload["criticism_points"] == ["Battery life is shorter than expected."]
    assert payload["user_recommendations"] == ["Publish realistic battery guidance in campaign copy."]
    assert payload["sentiment_breakdown"]["positive"] == 1
    assert payload["sentiment_breakdown"]["negative"] == 0
    assert payload["risk_breakdown"]["low"] == 1
    assert payload["reach_metrics"]["negative_reach_share_pct"] == 0.0
    assert payload["top_negative_videos"] == []


def test_insights_history_tracks_snapshots_in_latest_first_order(client, insights_db_session):
    profile = create_profile(insights_db_session, "Insights History Profile")
    video_one = _seed_video(insights_db_session, profile.id, "insight-history-1")
    video_two = _seed_video(insights_db_session, profile.id, "insight-history-2")

    first_analysis = AnalysisResult(
        video_candidate_id=video_one.id,
        analysis_version="v1",
        language="en",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="Transcript available",
        summary_text="summary",
        translated_summary="summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.7",
        evidence_json="[]",
        insights_json=encode_json({"praise_points": ["Compact design"], "criticism_points": [], "action_recommendation": ""}),
        error_message="",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    insights_db_session.add(first_analysis)
    insights_db_session.commit()

    first_refresh = client.post(f"/monitor-profiles/{profile.id}/insights/refresh")
    assert first_refresh.status_code == 200
    first_payload = first_refresh.json()
    assert first_payload["analyzed_video_count"] == 1

    second_analysis = AnalysisResult(
        video_candidate_id=video_two.id,
        analysis_version="v2",
        language="en",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="Second transcript available",
        summary_text="summary",
        translated_summary="summary",
        sentiment=Sentiment.POSITIVE,
        risk_level=RiskLevel.LOW,
        confidence_score="0.8",
        evidence_json="[]",
        insights_json=encode_json(
            {
                "praise_points": ["Easy setup"],
                "criticism_points": ["Controller grip could improve"],
                "action_recommendation": "Highlight quick setup in launch creatives.",
            }
        ),
        error_message="",
        created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    insights_db_session.add(second_analysis)
    insights_db_session.commit()

    second_refresh = client.post(f"/monitor-profiles/{profile.id}/insights/refresh")
    assert second_refresh.status_code == 200
    second_payload = second_refresh.json()
    assert second_payload["analyzed_video_count"] == 2

    current_response = client.get(f"/monitor-profiles/{profile.id}/insights/current")
    assert current_response.status_code == 200
    current_payload = current_response.json()["current"]
    assert current_payload["id"] == second_payload["id"]

    history_response = client.get(f"/monitor-profiles/{profile.id}/insights/history?limit=10")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["total"] == 2
    assert history_payload["items"][0]["id"] == second_payload["id"]
    assert history_payload["items"][1]["id"] == first_payload["id"]


def test_insights_history_delete_single_and_clear_all(client, insights_db_session):
    profile = create_profile(insights_db_session, "Insights Delete Profile")
    video = _seed_video(insights_db_session, profile.id, "insight-delete-1")

    analysis = AnalysisResult(
        video_candidate_id=video.id,
        analysis_version="v1",
        language="en",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="Transcript available",
        summary_text="summary",
        translated_summary="summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.7",
        evidence_json="[]",
        insights_json=encode_json({"praise_points": ["Compact design"], "criticism_points": [], "action_recommendation": ""}),
        error_message="",
    )
    insights_db_session.add(analysis)
    insights_db_session.commit()

    refresh_one = client.post(f"/monitor-profiles/{profile.id}/insights/refresh")
    assert refresh_one.status_code == 200
    refresh_two = client.post(f"/monitor-profiles/{profile.id}/insights/refresh")
    assert refresh_two.status_code == 200

    second_id = refresh_two.json()["id"]
    delete_single = client.delete(f"/monitor-profiles/{profile.id}/insights/history/{second_id}")
    assert delete_single.status_code == 200
    assert delete_single.json()["status"] == "success"
    assert delete_single.json()["deleted"] == 1

    history_after_single = client.get(f"/monitor-profiles/{profile.id}/insights/history")
    assert history_after_single.status_code == 200
    assert history_after_single.json()["total"] == 1

    clear_all = client.delete(f"/monitor-profiles/{profile.id}/insights/history")
    assert clear_all.status_code == 200
    assert clear_all.json()["status"] == "success"
    assert clear_all.json()["deleted"] == 1

    current_after_clear = client.get(f"/monitor-profiles/{profile.id}/insights/current")
    assert current_after_clear.status_code == 200
    assert current_after_clear.json()["current"] is None
