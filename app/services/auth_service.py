from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.app_user_repository import AppUserRepository
from app.repositories.auth_session_repository import AuthSessionRepository
from app.services.security import hash_session_token, verify_password

SESSION_TTL_HOURS = 12


class AuthService:
    def __init__(self, session: Session):
        self.session = session
        self.user_repository = AppUserRepository(session)
        self.auth_session_repository = AuthSessionRepository(session)

    def list_users(self):
        return self.user_repository.list_all()

    def authenticate(self, *, user_id: str, password: str):
        user = self.user_repository.get(user_id)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_session_for_user(self, *, user_id: str) -> str:
        raw_token = secrets.token_urlsafe(48)
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
        self.auth_session_repository.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return raw_token

    def resolve_user_from_raw_token(self, raw_token: str):
        if not raw_token:
            return None
        token_hash = hash_session_token(raw_token)
        auth_session = self.auth_session_repository.get_active_by_token_hash(token_hash)
        if auth_session is None:
            return None
        user = self.user_repository.get(auth_session.user_id)
        if user is None or not user.is_active:
            return None
        return user

    def clear_session(self, raw_token: str) -> bool:
        if not raw_token:
            return False
        token_hash = hash_session_token(raw_token)
        return self.auth_session_repository.delete_by_token_hash(token_hash)

    @staticmethod
    def cookie_max_age_seconds() -> int:
        return SESSION_TTL_HOURS * 3600
