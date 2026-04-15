from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.models.app_user import AppUser
from app.services.auth_service import AuthService

SESSION_COOKIE_NAME = "sushi_session"


def get_optional_current_user(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db_session),
) -> Optional[AppUser]:
    if not session_token:
        return None
    service = AuthService(db)
    return service.resolve_user_from_raw_token(session_token)


def get_current_user(
    current_user: Optional[AppUser] = Depends(get_optional_current_user),
) -> AppUser:
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return current_user
