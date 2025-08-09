from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId

from app.models.taxonomy import TaxonomyInDB, ClassifierState


class TaxonomyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    aspect: str = Field(..., min_length=1, max_length=500)
    rules: List[str] = Field(default_factory=list)


class TaxonomyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    aspect: Optional[str] = Field(None, min_length=1, max_length=500)
    classifier_state: Optional[ClassifierState] = None
    rules: Optional[List[str]] = None


class TaxonomyResponse(TaxonomyInDB):
    """Response model that inherits from TaxonomyInDB but converts id to string"""

    id: str = Field(default_factory=str)

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not isinstance(v, ObjectId):
            return str(v)
        return v


class TaxonomyInResponse(BaseModel):
    taxonomy: TaxonomyResponse


class TaxonomiesInResponse(BaseModel):
    taxonomies: List[TaxonomyResponse]
    count: int
