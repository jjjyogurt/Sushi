from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.app_user import AppUser


class AppUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: str) -> Optional[AppUser]:
        return self.session.get(AppUser, user_id)

    def list_all(self) -> List[AppUser]:
        return self.session.query(AppUser).order_by(AppUser.id.asc()).all()
