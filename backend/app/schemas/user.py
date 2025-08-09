from pydantic import BaseModel, Field, field_validator
from bson import ObjectId

from app.models.user import UserInDB


class UserBase(UserInDB):
    id: str = Field(default_factory=str)

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not isinstance(v, ObjectId):
            return str(v)
        return v


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    pass


class UserResponse(UserBase):
    pass


class UserInResponse(BaseModel):
    user: UserResponse
