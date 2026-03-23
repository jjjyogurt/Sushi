from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.monitor_profile import MonitorProfile
from app.schemas.monitor import MonitorProfileCreate
from app.utils.json_codec import decode_json, encode_json


class MonitorRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, payload: MonitorProfileCreate) -> MonitorProfile:
        profile = MonitorProfile(
            name=payload.name,
            brand_keywords=encode_json(payload.brand_keywords),
            markets=encode_json(payload.markets),
            languages=encode_json(payload.languages),
            alert_sensitivity=payload.alert_sensitivity,
        )
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get(self, profile_id: int) -> Optional[MonitorProfile]:
        return self.session.get(MonitorProfile, profile_id)

    def list_all(self) -> List[MonitorProfile]:
        return self.session.query(MonitorProfile).order_by(MonitorProfile.created_at.desc()).all()

    def delete(self, profile_id: int) -> bool:
        profile = self.get(profile_id)
        if profile:
            self.session.delete(profile)
            self.session.commit()
            return True
        return False

    @staticmethod
    def unpack_keywords(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.brand_keywords, [])

    @staticmethod
    def unpack_markets(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.markets, [])

    @staticmethod
    def unpack_languages(profile: MonitorProfile) -> List[str]:
        return decode_json(profile.languages, [])

