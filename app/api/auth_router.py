from typing import List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.auth_dependencies import SESSION_COOKIE_NAME, get_current_user
from app.config import get_settings
from app.db import get_db_session
from app.models.app_user import AppUser
from app.schemas.auth import AuthLoginRequest, AuthSessionResponse, AuthUserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def map_auth_user_response(user: AppUser) -> AuthUserResponse:
    return AuthUserResponse(
        user_id=user.id,
        display_name=user.display_name,
        must_change_password=user.must_change_password,
    )


@router.post("/login", response_model=AuthSessionResponse)
def login(payload: AuthLoginRequest, response: Response, db: Session = Depends(get_db_session)):
    settings = get_settings()
    service = AuthService(db)
    user = service.authenticate(user_id=payload.user_id, password=payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid user ID or password.")
    session_token = service.create_session_for_user(user_id=user.id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=service.cookie_max_age_seconds(),
        httponly=True,
        secure=True,
        samesite="none",
    )
    return AuthSessionResponse(user=map_auth_user_response(user))


@router.post("/logout")
def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db_session),
):
    settings = get_settings()
    service = AuthService(db)
    if session_token:
        service.clear_session(session_token)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )
    return {"status": "success"}


@router.get("/me", response_model=AuthSessionResponse)
def me(current_user: AppUser = Depends(get_current_user)):
    return AuthSessionResponse(user=map_auth_user_response(current_user))


@router.get("/users", response_model=List[AuthUserResponse])
def list_users(db: Session = Depends(get_db_session)):
    settings = get_settings()
    if not settings.public_user_list_allowed():
        raise HTTPException(
            status_code=403,
            detail="User directory listing is disabled for this deployment.",
        )
    service = AuthService(db)
    return [map_auth_user_response(user) for user in service.list_users()]
