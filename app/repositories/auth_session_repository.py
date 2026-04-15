from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, user_id: str, token_hash: str, expires_at: datetime) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        self.session.commit()
        self.session.refresh(auth_session)
        return auth_session

    def get_active_by_token_hash(self, token_hash: str) -> Optional[AuthSession]:
        now = datetime.now(timezone.utc)
        return (
            self.session.query(AuthSession)
            .filter(AuthSession.token_hash == token_hash, AuthSession.expires_at > now)
            .one_or_none()
        )

    def delete_by_token_hash(self, token_hash: str) -> bool:
        auth_session = self.session.query(AuthSession).filter(AuthSession.token_hash == token_hash).one_or_none()
        if auth_session is None:
            return False
        self.session.delete(auth_session)
        self.session.commit()
        return True
