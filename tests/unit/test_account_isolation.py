from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.app_user import AppUser
from app.models.base import Base
from app.models.enums import AnalysisBatchStatus, AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.repositories.analysis_batch_repository import AnalysisBatchRepository
from app.repositories.video_repository import VideoRepository
from app.services.security import hash_password
from app.utils.json_codec import encode_json


def _create_user(session, user_id: str):
    session.add(
        AppUser(
            id=user_id,
            display_name=user_id,
            password_hash=hash_password("1234"),
            must_change_password=False,
            is_active=True,
        )
    )
    session.commit()


def _create_profile(session, *, owner_user_id: str, name: str):
    profile = MonitorProfile(
        owner_user_id=owner_user_id,
        name=name,
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _create_video(session, *, profile_id: int, youtube_video_id: str, title: str):
    return VideoRepository(session).upsert_candidate(
        monitor_profile_id=profile_id,
        youtube_video_id=youtube_video_id,
        video_url=f"https://youtu.be/{youtube_video_id}",
        title=title,
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.8,
        relevance_reason="seed",
    )


def _add_analysis(session, video_id: int, *, risk_level: RiskLevel = RiskLevel.HIGH):
    analysis = AnalysisResult(
        video_candidate_id=video_id,
        analysis_version="v1",
        language="en",
        model_name="test-model",
        status=AnalysisStatus.COMPLETED,
        transcript_text="00:01 Signal dropped during flight.",
        summary_text="Signal dropped during flight.",
        translated_summary="Signal dropped during flight.",
        sentiment=Sentiment.NEGATIVE,
        risk_level=risk_level,
        confidence_score="0.9",
        evidence_json="[]",
        insights_json=encode_json({"criticism_points": ["Signal dropped."], "praise_points": []}),
        error_message="",
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def _login(client: TestClient, user_id: str):
    response = client.post("/auth/login", json={"user_id": user_id, "password": "1234"})
    assert response.status_code == 200


def test_account_isolation_blocks_cross_user_project_video_and_related_ids():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    _create_user(session, "Sushi_1")
    _create_user(session, "Sushi_2")
    profile_a = _create_profile(session, owner_user_id="Sushi_1", name="User A Project")
    profile_b = _create_profile(session, owner_user_id="Sushi_2", name="User B Project")
    video_a = _create_video(session, profile_id=profile_a.id, youtube_video_id="shared-youtube-id", title="A copy")
    video_b = _create_video(session, profile_id=profile_b.id, youtube_video_id="shared-youtube-id", title="B copy")
    _add_analysis(session, video_a.id)
    _add_analysis(session, video_b.id, risk_level=RiskLevel.LOW)
    batch_a = AnalysisBatchRepository(session).create_batch(
        monitor_profile_id=profile_a.id,
        created_by="Sushi_1",
        video_ids=[video_a.id],
    )
    batch_a.status = AnalysisBatchStatus.QUEUED
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            _login(client, "Sushi_1")
            kb_response = client.post("/knowledge/bases", json={"monitor_profile_id": profile_a.id, "name": "A KB"})
            assert kb_response.status_code == 200
            kb_a_id = kb_response.json()["id"]
            incident_response = client.post(
                f"/videos/{video_a.id}/escalate",
                json={"owner": "owner-a", "notes": "watch"},
            )
            assert incident_response.status_code == 200
            assert client.get("/alerts").json()["total"] == 1

            client.post("/auth/logout")
            _login(client, "Sushi_2")

            own_videos = client.get("/videos").json()["items"]
            assert [item["id"] for item in own_videos] == [video_b.id]
            assert client.get(f"/monitor-profiles/{profile_a.id}").status_code == 404
            assert client.get(f"/videos?monitor_profile_id={profile_a.id}").status_code == 404
            assert client.get(f"/videos/{video_a.id}/analysis").status_code == 404
            assert client.post(f"/videos/{video_a.id}/approve", json={"approved": True}).status_code == 404
            assert client.post(f"/videos/{video_a.id}/chat", json={"question": "What happened?"}).status_code == 404
            assert client.post(f"/watchlist/videos/{video_a.id}").status_code == 404
            assert client.get(f"/analysis/batches/{batch_a.id}").status_code == 404
            assert client.get("/alerts").json()["items"] == []
            assert client.get(f"/knowledge/bases?monitor_profile_id={profile_a.id}").status_code == 404
            assert client.patch(f"/knowledge/bases/{kb_a_id}", json={"name": "Stolen"}).status_code in {400, 404}
    finally:
        app.dependency_overrides.clear()
        session.close()
