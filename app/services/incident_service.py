from sqlalchemy.orm import Session

from app.models.enums import RiskLevel
from app.repositories.audit_repository import AuditRepository
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.incident_repository import IncidentRepository
from app.repositories.video_repository import VideoRepository
from app.services.notification_service import NotificationService


class IncidentService:
    def __init__(self, session: Session):
        self.session = session
        self.audit_repository = AuditRepository(session)
        self.analysis_repository = AnalysisRepository(session)
        self.video_repository = VideoRepository(session)
        self.incident_repository = IncidentRepository(session)
        self.notification_service = NotificationService()

    def escalate(self, *, video_id: int, owner: str, notes: str):
        candidate = self.video_repository.get_by_id(video_id)
        if candidate is None:
            raise ValueError("Video not found.")

        latest = self.analysis_repository.get_latest_for_video(video_candidate_id=video_id)
        if latest is None:
            raise ValueError("Cannot escalate without completed analysis.")

        incident = self.incident_repository.create_incident(
            video_candidate_id=video_id,
            severity=latest.risk_level,
            owner=owner,
            notes=notes,
        )
        if latest.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            alert_text = self.notification_service.build_alert_message(
                title=candidate.title,
                severity=latest.risk_level,
                summary=latest.summary_text,
            )
            self.incident_repository.create_alert(incident_id=incident.id, channel="inbox", message=alert_text)
        self.audit_repository.record(
            actor="marketing-owner",
            action="incident_escalated",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"severity={latest.risk_level.value}",
        )
        return incident

    def list_alerts(self):
        return self.incident_repository.list_alerts()

