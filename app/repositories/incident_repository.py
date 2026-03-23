from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.incident import Alert, Incident


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

    def list_alerts(self) -> List[Alert]:
        return self.session.query(Alert).order_by(desc(Alert.created_at)).all()

