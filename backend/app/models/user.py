from typing import Optional
from pydantic import EmailStr

from app.models.object_id import MongoBaseModel


class UserInDB(MongoBaseModel):
    email: EmailStr
    name: str
    google_id: Optional[str] = None
    picture: Optional[str] = None
    is_superuser: bool = False
    is_paid_user: bool = False
