from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.object_id import MongoBaseModel
from agents.state import Taxonomy


class ClassifierState(BaseModel):
    """State of the classifier service for persistence"""

    majority_threshold: float = settings.DEFAULT_MAJORITY_THRESHOLD
    batch_size: int = settings.DEFAULT_BATCH_SIZE
    total_invocations: int = settings.DEFAULT_TOTAL_INVOCATIONS
    initial_batch_size: int = settings.DEFAULT_INITIAL_BATCH_SIZE
    use_human_in_the_loop: bool = False
    node_ids_not_to_examine: List[str] = []
    examined_node_ids: List[str] = []
    models: List[str] = settings.DEFAULT_MODELS

    model_config = {"from_attributes": True}


# Must inherit from MongoBaseModel first,
# Otherwise, the id field will be serialized as a string instead of an ObjectId
class TaxonomyInDB(MongoBaseModel, Taxonomy):
    """Taxonomy model for MongoDB storage"""

    user_id: str
    classifier_state: Optional[ClassifierState] = Field(default_factory=ClassifierState)
