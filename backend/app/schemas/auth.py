from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class GoogleAuthUrl(BaseModel):
    auth_url: str


class GoogleCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None
