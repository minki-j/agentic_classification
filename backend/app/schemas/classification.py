from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from agents.llm_factory import AIModel
from agents.state import ItemState, ClassNodeState


class ClassificationRequest(BaseModel):
    taxonomy_id: str
    batch_size: Optional[int] = Field(None, gt=0, le=100)
    models: Optional[List[AIModel]] = None
    majority_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    total_invocations: Optional[int] = Field(None, gt=0)


class ClassificationResponse(BaseModel):
    message: str
    items_classified: int
    status: str


class ExaminationRequest(BaseModel):
    taxonomy_id: str
    force_examine_node_ids: Optional[List[str]] = None


class ExaminationResponse(BaseModel):
    message: str
    nodes_examined: List[str]
    status: str


class ClassificationStatusResponse(BaseModel):
    session_id: str
    status: str
    progress: dict
    current_batch: Optional[int] = None
    total_batches: Optional[int] = None


class ClassifierStateUpdate(BaseModel):
    """Update classifier state configuration"""

    majority_threshold: Optional[float] = None
    batch_size: Optional[int] = None
    total_invocations: Optional[int] = None
    initial_batch_size: Optional[int] = None
    use_human_in_the_loop: Optional[bool] = None
    node_ids_not_to_examine: Optional[List[str]] = None
    models: Optional[List[str]] = None


class RemoveClassificationRequest(BaseModel):
    taxonomy_id: str
    item_id: str
    node_id_to_remove: str


class RemoveClassificationItemsOnlyRequest(BaseModel):
    taxonomy_id: str
    item_ids: List[str]
    node_id_to_remove: str


class RemoveClassificationResponse(BaseModel):
    message: str
    status: str


# Add new schema for manual classification addition
class AddClassificationRequest(BaseModel):
    taxonomy_id: str
    item_id: str
    node_id: str
    confidence_score: float = 1.0  # Default to 100%


class AddClassificationResponse(BaseModel):
    message: str
    status: str


class VerifyClassificationRequest(BaseModel):
    taxonomy_id: str
    node_id: str
    item_ids_to_verify: Optional[List[str]] = []
    item_ids_to_unverify: Optional[List[str]] = []


class UpdateFewShotExamplesRequest(BaseModel):
    taxonomy_id: str
    node_id: str
    item_ids_to_add: List[str]
    item_ids_to_remove: List[str]


class OptimizePromptWithDspyRequest(BaseModel):
    taxonomy_id: str
    node_id: str
