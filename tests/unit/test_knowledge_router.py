from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db_session
from app.main import app
from app.models.base import Base
from app.models.monitor_profile import MonitorProfile
from app.utils.json_codec import encode_json


def _seed_profile(session):
    profile = MonitorProfile(
        name="Knowledge Project",
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


def test_knowledge_router_supports_multi_kb_and_summary_generation():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    profile = _seed_profile(session)

    def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    try:
        with TestClient(app) as client:
            create_first = client.post(
                "/knowledge/bases",
                json={"monitor_profile_id": profile.id, "name": "Specs"},
            )
            assert create_first.status_code == 200
            kb_one = create_first.json()
            assert kb_one["is_active"] is True

            create_second = client.post(
                "/knowledge/bases",
                json={"monitor_profile_id": profile.id, "name": "FAQ"},
            )
            assert create_second.status_code == 200
            kb_two = create_second.json()

            activate_second = client.patch(
                f"/knowledge/bases/{kb_two['id']}",
                json={"is_active": True, "name": "Support FAQ"},
            )
            assert activate_second.status_code == 200
            assert activate_second.json()["name"] == "Support FAQ"

            upload_response = client.post(
                "/knowledge/sources/file",
                data={"monitor_profile_id": str(profile.id), "knowledge_base_id": str(kb_two["id"])},
                files={"file": ("specs.txt", b"HoverAir supports quick setup and stable hover.")},
            )
            assert upload_response.status_code == 200

            summary_response = client.get(
                f"/knowledge/summary?monitor_profile_id={profile.id}&knowledge_base_id={kb_two['id']}"
            )
            assert summary_response.status_code == 200
            assert "HoverAir supports quick setup" in summary_response.json()["knowledge_md"]
    finally:
        app.dependency_overrides.clear()
        session.close()
