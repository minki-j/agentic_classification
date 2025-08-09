from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId
from app.models.item import ItemInDB, ClassifiedAs


class UploadItem(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ItemUploadRequest(BaseModel):
    items: List[UploadItem]


class ItemResponse(ItemInDB):
    """
    Overrides the ItemInDB model to only include the classified_as field for the selected taxonomy.
    Converts the id to a string.
    """

    id: str = Field(default_factory=str)
    classified_as: List[ClassifiedAs] = Field(
        default_factory=list
    )  # Not a dictionary but a list! Only return the list of ClassifiedAs for the selected taxonomy.

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not isinstance(v, ObjectId):
            return str(v)
        return v


class ItemInResponse(BaseModel):
    item: ItemResponse


class ItemsInResponse(BaseModel):
    items: List[ItemResponse]
    count: int  # TODO: it's confusing. It should be total_items.
    unclassified_count: int


class GetIdsByListOfContentRequest(BaseModel):
    content_list: list[str]
