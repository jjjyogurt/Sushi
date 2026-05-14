from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.app_user import AppUser
from app.models.base import Base
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate
from app.services.security import hash_password
from app.utils.json_codec import encode_json
from app.utils.text import normalize_title, title_fingerprint


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
        api_db_session.add(
            AppUser(
                id="Sushi_1",
                display_name="Sushi_1",
                password_hash=hash_password("1234"),
                must_change_password=False,
                is_active=True,
            )
        )
        api_db_session.commit()
        login = test_client.post("/auth/login", json={"user_id": "Sushi_1", "password": "1234"})
        assert login.status_code == 200
        yield test_client
    app.dependency_overrides.clear()


def _create_analyzed_video(db_session, *, title: str, risk_level: RiskLevel):
    profile = MonitorProfile(
        name="Alert Project",
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

    video = VideoCandidate(
        monitor_profile_id=profile.id,
        youtube_video_id=f"video-{risk_level.value}",
        video_url=f"https://www.youtube.com/watch?v=video-{risk_level.value}",
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
        model_name="gemini-3",
        status=AnalysisStatus.COMPLETED,
        transcript_text="seed",
        summary_text="seed summary",
        translated_summary="seed summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=risk_level,
        confidence_score="0.8",
        evidence_json=encode_json([]),
        insights_json=encode_json([]),
    )
    db_session.add(analysis)
    db_session.commit()
    return video


def test_escalate_low_risk_reports_no_alert_created(client, api_db_session):
    video = _create_analyzed_video(api_db_session, title="Low risk video", risk_level=RiskLevel.LOW)

    response = client.post(f"/videos/{video.id}/escalate", json={"owner": "owner-a", "notes": "watch"})
    alerts_response = client.get("/alerts")

    assert response.status_code == 200
    assert response.json()["alert_created"] is False
    assert alerts_response.status_code == 200
    assert alerts_response.json()["items"] == []


def test_escalate_high_risk_alert_has_video_context(client, api_db_session):
    video = _create_analyzed_video(api_db_session, title="High risk video", risk_level=RiskLevel.HIGH)

    response = client.post(f"/videos/{video.id}/escalate", json={"owner": "owner-a", "notes": "watch"})
    alerts_response = client.get("/alerts")

    assert response.status_code == 200
    assert response.json()["alert_created"] is True
    payload = alerts_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["video_candidate_id"] == video.id
    assert payload["items"][0]["video_title"] == "High risk video"
    assert payload["items"][0]["severity"] == "high"
    assert payload["items"][0]["owner"] == "owner-a"
