from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate
from app.utils.json_codec import encode_json
from app.utils.text import normalize_title, title_fingerprint


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session: Session = test_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def monitor_profile(db_session: Session):
    profile = MonitorProfile(
        name="Test Profile",
        brand_keywords=encode_json(["hoverair", "hover air"]),
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
def discovered_video(db_session: Session, monitor_profile: MonitorProfile):
    title = "HoverAir Full Review"
    video = VideoCandidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id="video123",
        video_url="https://www.youtube.com/watch?v=video123",
        title=title,
        normalized_title=normalize_title(title),
        title_fingerprint=title_fingerprint(title),
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.9,
        relevance_reason="title matched: hoverair",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video

