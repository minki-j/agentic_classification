from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId

from app.models.node import NodeInDB
from agents.state import ItemUnderNode


class NodeResponse(NodeInDB):
    id: str = Field(default_factory=str)

    @field_validator("id", mode="before")
    def validate_id(cls, v):
        if not isinstance(v, ObjectId):
            return str(v)
        return v


class NodeCreate(NodeInDB):
    pass


class NodeUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    parent_node_id: Optional[str] = None
    items: Optional[List[ItemUnderNode]] = None


class NodeInResponse(BaseModel):
    node: NodeResponse


class NodesInResponse(BaseModel):
    nodes: List[NodeResponse]
    count: int


class InitialNodesRequest(BaseModel):
    taxonomy_id: str
    num_of_items_to_use: int = Field(
        ...,
        gt=0,
        le=1000,
        description="Number of items to use for initial node creation",
    )
    llm_name: str


class InitialNodesResponse(BaseModel):
    message: str


class ParentUpdate(BaseModel):
    taxonomy_id: str
    child_id: str
    parent_id: str


class NodeUpdateResultResponse(BaseModel):
    success: bool
    message: str
