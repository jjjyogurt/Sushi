from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db_session
from app.main import app
from app.models.base import Base
from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.repositories.video_repository import VideoRepository
from app.services.analysis_service import AnalysisService
from app.services.exceptions import GeminiConfigurationError, TranscriptBlockedError
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


@pytest.fixture()
def api_db_session():
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
def client(api_db_session):
    def override_db():
        yield api_db_session

    app.dependency_overrides[get_db_session] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def api_monitor_profile(api_db_session):
    return create_profile(api_db_session, "Primary Project")


def test_list_videos_global_includes_project_name_and_sentiment(client, api_db_session, api_monitor_profile):
    second_profile = create_profile(api_db_session, "Second Project")
    repository = VideoRepository(api_db_session)

    video_one = repository.upsert_candidate(
        monitor_profile_id=api_monitor_profile.id,
        youtube_video_id="router-global-1",
        video_url="https://youtu.be/router-global-1",
        title="Global one",
        channel_name="CreatorOne",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.6,
        relevance_reason="seed",
    )
    repository.upsert_candidate(
        monitor_profile_id=second_profile.id,
        youtube_video_id="router-global-2",
        video_url="https://youtu.be/router-global-2",
        title="Global two",
        channel_name="CreatorTwo",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.4,
        relevance_reason="seed",
    )

    analysis = AnalysisResult(
        video_candidate_id=video_one.id,
        analysis_version="v1",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="transcript",
        summary_text="summary",
        translated_summary="summary",
        sentiment=Sentiment.POSITIVE,
        risk_level=RiskLevel.LOW,
        confidence_score="0.9",
        evidence_json="[]",
        insights_json="[]",
        error_message="",
    )
    api_db_session.add(analysis)
    api_db_session.commit()

    response = client.get("/videos")
    assert response.status_code == 200

    payload = response.json()
    items = payload["items"]
    by_video_id = {item["youtube_video_id"]: item for item in items}
    assert by_video_id["router-global-1"]["monitor_profile_name"] == api_monitor_profile.name
    assert by_video_id["router-global-2"]["monitor_profile_name"] == second_profile.name
    assert by_video_id["router-global-1"]["sentiment_label"] == "positive"


def test_search_and_bulk_add_endpoints(client, api_monitor_profile):
    settings = get_settings()
    original = settings.enable_mock_discovery
    settings.enable_mock_discovery = True

    try:
        search_response = client.post(
            "/videos/search",
            json={
                "monitor_profile_id": api_monitor_profile.id,
                "query": "hoverair review",
                "max_results": 3,
            },
        )
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert search_payload["total"] > 0

        addable = next(item for item in search_payload["items"] if item["can_add"])
        bulk_response = client.post(
            "/videos/bulk-add",
            json={
                "monitor_profile_id": api_monitor_profile.id,
                "candidates": [
                    {
                        "youtube_video_id": addable["youtube_video_id"],
                        "video_url": addable["video_url"],
                        "title": addable["title"],
                        "channel_name": addable["channel_name"],
                        "language": addable["language"],
                        "published_at": addable["published_at"],
                        "description": addable["description"],
                    }
                ],
            },
        )
        assert bulk_response.status_code == 200
        bulk_payload = bulk_response.json()
        assert bulk_payload["total"] == 1
        assert bulk_payload["items"][0]["monitor_profile_id"] == api_monitor_profile.id
    finally:
        settings.enable_mock_discovery = original


def test_analyze_endpoint_maps_gemini_not_ready_errors(client, monkeypatch):
    def _raise_not_ready(self, *, video_id: int, force_reanalyze: bool = False, knowledge_base_id=None):
        _ = (video_id, force_reanalyze, knowledge_base_id)
        raise GeminiConfigurationError("GEMINI_API_KEY is not configured.")

    monkeypatch.setattr(AnalysisService, "analyze_video", _raise_not_ready)

    response = client.post("/videos/31/analyze", json={"force_reanalyze": True})
    assert response.status_code == 503
    assert response.json()["detail"].startswith("GEMINI_NOT_READY:")


def test_analyze_endpoint_maps_transcript_blocked_errors(client, monkeypatch):
    def _raise_blocked(self, *, video_id: int, force_reanalyze: bool = False, knowledge_base_id=None):
        _ = (video_id, force_reanalyze, knowledge_base_id)
        raise TranscriptBlockedError("YouTube blocked transcript requests for current IP.")

    monkeypatch.setattr(AnalysisService, "analyze_video", _raise_blocked)

    response = client.post("/videos/31/analyze", json={"force_reanalyze": True})
    assert response.status_code == 503
    assert response.json()["detail"].startswith("TRANSCRIPT_BLOCKED:")


def test_get_latest_analysis_supports_legacy_insights_list(client, api_db_session, api_monitor_profile):
    repository = VideoRepository(api_db_session)
    video = repository.upsert_candidate(
        monitor_profile_id=api_monitor_profile.id,
        youtube_video_id="router-analysis-legacy",
        video_url="https://youtu.be/router-analysis-legacy",
        title="Legacy analysis row",
        channel_name="CreatorLegacy",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.51,
        relevance_reason="seed",
    )
    analysis = AnalysisResult(
        video_candidate_id=video.id,
        analysis_version="v1",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="legacy transcript",
        summary_text="legacy summary",
        translated_summary="legacy summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.7",
        evidence_json="[]",
        insights_json=encode_json(["legacy insight one", "legacy insight two"]),
        error_message="",
    )
    api_db_session.add(analysis)
    api_db_session.commit()

    response = client.get(f"/videos/{video.id}/analysis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["insights"] == ["legacy insight one", "legacy insight two"]
    assert payload["praise_points"] == []
    assert payload["criticism_points"] == []
    assert payload["action_recommendation"] == ""


def test_get_latest_analysis_supports_structured_insights_payload(client, api_db_session, api_monitor_profile):
    repository = VideoRepository(api_db_session)
    video = repository.upsert_candidate(
        monitor_profile_id=api_monitor_profile.id,
        youtube_video_id="router-analysis-structured",
        video_url="https://youtu.be/router-analysis-structured",
        title="Structured analysis row",
        channel_name="CreatorStructured",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.69,
        relevance_reason="seed",
    )
    analysis = AnalysisResult(
        video_candidate_id=video.id,
        analysis_version="v2",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="structured transcript",
        summary_text="structured summary",
        translated_summary="structured summary",
        sentiment=Sentiment.NEGATIVE,
        risk_level=RiskLevel.HIGH,
        confidence_score="0.9",
        evidence_json="[]",
        insights_json=encode_json(
            {
                "insights": ["insight one"],
                "praise_points": ["good stabilization", "compact design"],
                "criticism_points": [
                    "weak signal range",
                    "manual controls feel complex",
                    "obstacle sensing gap",
                    "connection drops",
                    "high price perception",
                    "should be truncated",
                ],
                "action_recommendation": "Explain signal expectations and manual-control tips to the influencer.",
            }
        ),
        error_message="",
    )
    api_db_session.add(analysis)
    api_db_session.commit()

    response = client.get(f"/videos/{video.id}/analysis")
    assert response.status_code == 200
    payload = response.json()
    assert payload["insights"] == ["insight one"]
    assert payload["praise_points"] == ["good stabilization", "compact design"]
    assert len(payload["criticism_points"]) == 5
    assert payload["criticism_points"][-1] == "high price perception"
    assert payload["action_recommendation"].startswith("Explain signal expectations")
