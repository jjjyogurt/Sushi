from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.app_user import AppUser
from app.models.base import Base
from app.models.monitor_profile import MonitorProfile
from app.services.security import hash_password


def _build_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    client = TestClient(app)
    return client, session


def _create_user(session, user_id: str = "Sushi_1"):
    user = AppUser(
        id=user_id,
        display_name=user_id,
        password_hash=hash_password("1234"),
        must_change_password=False,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def _login(client: TestClient, user_id: str = "Sushi_1"):
    response = client.post("/auth/login", json={"user_id": user_id, "password": "1234"})
    assert response.status_code == 200


def _create_monitor_profile(client: TestClient):
    payload = {
        "name": "Falcon Mini",
        "brand_keywords": ["falcon mini"],
        "markets": ["DE"],
        "languages": ["en"],
        "key_products": ["falcon mini", "falcon mini pro"],
        "alert_sensitivity": "medium",
    }
    response = client.post("/monitor-profiles", json=payload)
    assert response.status_code == 200
    return response.json()


def test_monitor_profile_create_and_list_include_key_products():
    client, session = _build_client()
    try:
        _create_user(session)
        _login(client)
        created = _create_monitor_profile(client)
        assert created["key_products"] == ["falcon mini", "falcon mini pro"]
        assert created["proactive_monitoring_enabled"] is False
        assert created["proactive_monitoring_cadence"] == "daily"
        assert created["unseen_monitoring_update_count"] == 0

        listed = client.get("/monitor-profiles")
        assert listed.status_code == 200
        items = listed.json()
        assert len(items) == 1
        assert items[0]["key_products"] == ["falcon mini", "falcon mini pro"]
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()


def test_monitor_profile_update_persists_key_products():
    client, session = _build_client()
    try:
        _create_user(session)
        _login(client)
        created = _create_monitor_profile(client)
        profile_id = created["id"]

        update_response = client.put(
            f"/monitor-profiles/{profile_id}",
            json={
                "name": "Falcon Mini Updated",
                "brand_keywords": ["falcon mini"],
                "markets": ["GERMANY"],
                "languages": ["de"],
                "key_products": ["falcon mini 2"],
                "alert_sensitivity": "high",
            },
        )
        assert update_response.status_code == 200
        payload = update_response.json()
        assert payload["name"] == "Falcon Mini Updated"
        assert payload["key_products"] == ["falcon mini 2"]
        assert payload["alert_sensitivity"] == "high"
        assert payload["proactive_monitoring_enabled"] is False
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()


def test_monitoring_settings_toggle_and_seen_contract():
    client, session = _build_client()
    try:
        _create_user(session)
        _login(client)
        created = _create_monitor_profile(client)
        profile_id = created["id"]

        toggle_response = client.patch(
            f"/monitor-profiles/{profile_id}/monitoring-settings",
            json={
                "proactive_monitoring_enabled": True,
                "proactive_monitoring_cadence": "monthly",
            },
        )
        assert toggle_response.status_code == 200
        toggled = toggle_response.json()
        assert toggled["proactive_monitoring_enabled"] is True
        assert toggled["proactive_monitoring_cadence"] == "monthly"

        profile = session.get(MonitorProfile, profile_id)
        profile.unseen_monitoring_update_count = 3
        profile.last_monitoring_digest = "3 new videos, 1 critical risk detected."
        session.commit()

        seen_response = client.post(f"/monitor-profiles/{profile_id}/monitoring-updates/seen")
        assert seen_response.status_code == 200
        seen = seen_response.json()
        assert seen["unseen_monitoring_update_count"] == 0
        assert seen["last_monitoring_digest"] == "3 new videos, 1 critical risk detected."
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()


def test_monitor_profile_update_not_found_returns_404():
    client, session = _build_client()
    try:
        _create_user(session)
        _login(client)
        response = client.put(
            "/monitor-profiles/9999",
            json={
                "name": "Missing Project",
                "brand_keywords": ["hoverair"],
                "markets": ["GLOBAL"],
                "languages": ["en"],
                "key_products": [],
                "alert_sensitivity": "medium",
            },
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()


def test_monitor_profile_update_validation_error_returns_422():
    client, session = _build_client()
    try:
        _create_user(session)
        _login(client)
        created = _create_monitor_profile(client)
        profile_id = created["id"]
        response = client.put(
            f"/monitor-profiles/{profile_id}",
            json={
                "name": "x",
                "brand_keywords": [],
                "markets": [],
                "languages": [],
                "key_products": "falcon",
                "alert_sensitivity": "medium",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
        client.close()
        session.close()
