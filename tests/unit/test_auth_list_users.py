from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.app_user import AppUser
from app.models.base import Base
from app.services.security import hash_password


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


def test_auth_users_list_returns_users():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    _create_user(session, "alpha")

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db
    client = TestClient(app)
    try:
        response = client.get("/auth/users")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)
        assert any(row.get("user_id") == "alpha" for row in payload)
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_auth_users_list_forbidden_when_disabled(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = test_session()
    _create_user(session, "beta")

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db
    mock_settings = MagicMock()
    mock_settings.public_user_list_allowed = lambda: False
    monkeypatch.setattr("app.api.auth_router.get_settings", lambda: mock_settings)
    client = TestClient(app)
    try:
        response = client.get("/auth/users")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        session.close()
