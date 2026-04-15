from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.app_user import AppUser
from app.models.base import Base
from app.models.monitor_profile import MonitorProfile
from app.repositories.video_repository import VideoRepository
from app.services.security import hash_password
from app.utils.json_codec import encode_json


def _create_user(db_session, user_id: str, password: str = "1234"):
    user = AppUser(
        id=user_id,
        display_name=user_id,
        password_hash=hash_password(password),
        must_change_password=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_profile(db_session):
    profile = MonitorProfile(
        name="Auth Watchlist Project",
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


def _create_video(db_session, profile_id: int):
    repository = VideoRepository(db_session)
    return repository.upsert_candidate(
        monitor_profile_id=profile_id,
        youtube_video_id="watchlist-video-1",
        video_url="https://youtu.be/watchlist-video-1",
        title="Watchlist Video One",
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.87,
        relevance_reason="seed",
    )


def _login(client: TestClient, user_id: str, password: str = "1234"):
    response = client.post("/auth/login", json={"user_id": user_id, "password": password})
    assert response.status_code == 200
    return response


def test_auth_login_me_logout_flow():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    _create_user(session, "Sushi_1")

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            _login(client, "Sushi_1")
            me_response = client.get("/auth/me")
            assert me_response.status_code == 200
            assert me_response.json()["user"]["user_id"] == "Sushi_1"

            logout_response = client.post("/auth/logout")
            assert logout_response.status_code == 200

            me_after_logout = client.get("/auth/me")
            assert me_after_logout.status_code == 401
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_watchlist_isolation_across_accounts():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    _create_user(session, "Sushi_1")
    _create_user(session, "Sushi_2")
    profile = _create_profile(session)
    video = _create_video(session, profile.id)

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            unauthorized = client.get("/watchlist")
            assert unauthorized.status_code == 401

            _login(client, "Sushi_1")
            add_response = client.post(f"/watchlist/videos/{video.id}")
            assert add_response.status_code == 200

            user_one_watchlist = client.get("/watchlist")
            assert user_one_watchlist.status_code == 200
            assert [item["id"] for item in user_one_watchlist.json()["items"]] == [video.id]
            user_one_videos = client.get("/videos")
            assert user_one_videos.status_code == 200
            assert user_one_videos.json()["items"][0]["is_bookmarked"] is True

            client.post("/auth/logout")
            _login(client, "Sushi_2")
            user_two_watchlist = client.get("/watchlist")
            assert user_two_watchlist.status_code == 200
            assert user_two_watchlist.json()["items"] == []
            user_two_videos = client.get("/videos")
            assert user_two_videos.status_code == 200
            assert user_two_videos.json()["items"][0]["is_bookmarked"] is False
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_assign_video_requires_valid_assignee():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    _create_user(session, "Sushi_1")
    _create_user(session, "Sushi_2")
    profile = _create_profile(session)
    video = _create_video(session, profile.id)

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            _login(client, "Sushi_1")

            assign_response = client.patch(
                f"/videos/{video.id}/assignee",
                json={"assigned_user_id": "Sushi_2"},
            )
            assert assign_response.status_code == 200
            assert assign_response.json()["assigned_user_id"] == "Sushi_2"

            invalid_assign = client.patch(
                f"/videos/{video.id}/assignee",
                json={"assigned_user_id": "unknown-user"},
            )
            assert invalid_assign.status_code == 400
            assert "Assigned user not found" in invalid_assign.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        session.close()
