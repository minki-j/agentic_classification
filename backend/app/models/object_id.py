from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field, field_serializer, field_validator


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        # print(f"[DEBUG] got a value: {v} of type: {type(v)}")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_core_schema__(cls, *args, **kwargs):
        from pydantic_core import core_schema

        return core_schema.with_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )


class MongoBaseModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_serializer("id")
    def serialize_id(self, value, _info):
        # Check if context says to skip string conversion
        if _info.context and _info.context.get("keep_objectid"):
            return value
        return str(value) if value else None

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if isinstance(v, str):
            return ObjectId(v)
        if isinstance(v, ObjectId):
            return v
        raise ValueError(f"Invalid id: {v} of type: {type(v)}")

    model_config = {
        "populate_by_name": True,
        "validate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
