from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(self, *, actor: str, action: str, resource_type: str, resource_id: str, details: str = "") -> AuditLog:
        log = AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

