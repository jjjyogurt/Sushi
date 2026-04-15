from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class AuthUserResponse(BaseModel):
    user_id: str
    display_name: str
    must_change_password: bool


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse
