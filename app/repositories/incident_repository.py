from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.incident import Alert, Incident
from app.models.monitor_profile import MonitorProfile
from app.models.video_candidate import VideoCandidate


class IncidentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_incident(
        self,
        *,
        video_candidate_id: int,
        severity,
        owner: str,
        notes: str,
    ) -> Incident:
        incident = Incident(video_candidate_id=video_candidate_id, severity=severity, owner=owner, notes=notes)
        self.session.add(incident)
        self.session.commit()
        self.session.refresh(incident)
        return incident

    def create_alert(self, *, incident_id: int, channel: str, message: str) -> Alert:
        alert = Alert(incident_id=incident_id, channel=channel, message=message, is_sent=True)
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def list_alerts(self, *, user_id: str = "") -> List[Alert]:
        query = self.session.query(Alert)
        if user_id:
            query = (
                query.join(Incident, Incident.id == Alert.incident_id)
                .join(VideoCandidate, VideoCandidate.id == Incident.video_candidate_id)
                .join(MonitorProfile, MonitorProfile.id == VideoCandidate.monitor_profile_id)
                .filter(MonitorProfile.owner_user_id == user_id)
            )
        return query.order_by(desc(Alert.created_at)).all()
