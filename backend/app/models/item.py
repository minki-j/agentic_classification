from typing import List, Dict
from datetime import datetime
from pydantic import Field

from agents.state import NodeAndConfidence, ItemState
from app.models.object_id import MongoBaseModel


class ClassifiedAs(NodeAndConfidence):
    is_verified: bool = Field(default=False)
    used_as_few_shot_example: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.now)


# Must inherit from MongoBaseModel first,
# Otherwise, the id field will be serialized as a string instead of an ObjectId
class ItemInDB(MongoBaseModel, ItemState):
    """Item model for MongoDB storage"""

    # id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    classified_as: Dict[str, List[ClassifiedAs]] = Field(
        default_factory=dict,
        description="key: taxonomy_id, value: list of classification results",
    )
