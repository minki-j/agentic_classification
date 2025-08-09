import operator
from typing import Any, Annotated, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from agents.llm_factory import AIModel

ROOT_NODE_ID = "6889fa6ca166114297756152"


# ===========================================
#                Data Models
# ===========================================
class Taxonomy(BaseModel):
    id: str
    name: str
    aspect: str
    rules: list[str] = Field(default_factory=list)
    # mutually_exclusive: bool #TODO


class NodeAndConfidence(BaseModel):
    node_id: str
    confidence_score: float


class ClassifiedAs(NodeAndConfidence):
    is_verified: bool = Field(default=False)
    used_as_few_shot_example: bool = Field(default=False)


# ItemState uses NodeAndConfidence instead of ClassifiedAs because this model is used as a schema for structured output of the LLM; is_verified and used_as_few_shot_example are not part of the LLM output.
class ItemState(BaseModel):
    id: str
    content: str
    classified_as: Optional[list[NodeAndConfidence]] = Field(
        default_factory=list,
        description="A list of tuples containing node IDs and their confidence scores.",
    )


class Example(BaseModel):
    content: str = Field(description="The content of the the example item")


class ItemUnderNode(BaseModel):
    item_id: str
    confidence_score: float
    is_verified: bool = Field(default=False)
    used_as_few_shot_example: bool = Field(default=False)


class ClassNodeState(BaseModel):
    id: Optional[str] = Field(
        default=None,
        description="A random 4 character and number string that is used to identify the node.",
    )
    parent_node_id: str = Field(
        description="The id of the parent node.",
    )
    label: str
    description: str
    items: Optional[list[ItemUnderNode]] = Field(
        default_factory=list,
        description="A list of items that are classified to this node.",
    )


class UnclassifiableCase(BaseModel):
    item: ItemState
    parent_node_id: str
    message_history: Annotated[list[BaseMessage], add_messages]


class ConfidenceLevel(Enum):
    FALSE = "False"
    NOT_SURE = "NotSure"
    TRUE = "True"


# ===========================================
#              REDUCER FUNCTIONS
# ===========================================
def extend_list(original: list, new: Any):
    if new is None:
        return original

    if not isinstance(new, list):
        new = [new]
    if len(new) == 1 and new[0] == "RESET":
        return []
    original.extend(new)
    return original


root_node = ClassNodeState(
    id=ROOT_NODE_ID,
    label="Root",
    description="The root node of the taxonomy.",
    parent_node_id="",
)


def node_reducer(
    original: list[ClassNodeState], new: list[ClassNodeState] | ClassNodeState | None
):
    if new is None:
        return original

    if not isinstance(new, list):
        new = [new]

    if any(node.id == "REPLACE_ALL" for node in new):
        return [root_node] + [node for node in new if node.id != "REPLACE_ALL"]

    if any(node.id == "RESET" for node in new):
        return [root_node]

    if len(original) == 0:
        original = [root_node]

    for new_node in new:
        existing_node_index = None
        for i, existing_node in enumerate(original):
            if existing_node.id == new_node.id:
                existing_node_index = i
                break

        if existing_node_index:
            original[existing_node_index] = new_node
        else:
            original.append(new_node)

    return original


def item_reducer(original: list[ItemState], new: list[ItemState] | ItemState | None):
    if new is None:
        return original

    if not isinstance(new, list):
        new = [new]

    if any(item.id == "REPLACE_ALL" for item in new):
        return [item for item in new if item.id != "REPLACE_ALL"]

    # Check for existing items with same ID and append node_ids, otherwise append new item
    for new_item in new:
        existing_item_index = None
        for i, existing_item in enumerate(original):
            if existing_item.id == new_item.id:
                existing_item_index = i
                break

        if existing_item_index is not None:
            # Append new node_ids to existing item
            if not new_item.classified_as:
                continue
            for node_and_confidence in new_item.classified_as:
                if original[existing_item_index].classified_as is None:
                    original[existing_item_index].classified_as = [node_and_confidence]
                    continue

                original_node_ids = [
                    original_node_and_confidence.node_id
                    for original_node_and_confidence in original[
                        existing_item_index
                    ].classified_as  # type: ignore
                ]

                if node_and_confidence.node_id not in original_node_ids:
                    original[existing_item_index].classified_as.append(  # type: ignore
                        node_and_confidence
                    )
                else:
                    # If the node_id is already in the existing item, we replace it.
                    original[existing_item_index].classified_as = [
                        original_node_and_confidence
                        for original_node_and_confidence in original[
                            existing_item_index
                        ].classified_as  # type: ignore
                        if original_node_and_confidence.node_id
                        != node_and_confidence.node_id
                    ] + [node_and_confidence]
        else:
            # Append new item
            original.append(new_item)

    return original


def append_to_same_key(original: dict[str, list[Any]], new: dict[str, Union[Any, Any]]):
    for key, value in new.items():
        if key in original:
            original[key].append(value)
        else:
            original[key] = [value]
    return original


def reducer_for_messages_per_branch_dict(
    original: dict[str, list[BaseMessage]], new: dict[str, list[BaseMessage]]
):
    """For this state, we only need one message history for each branch."""
    for key, value in new.items():
        if key in original:
            return original
        original[key] = value
    return original


# ============================================
#                 STATES
#
# (Keeping here to prevent "Circular Imports")
# ============================================


class ClassifyItemsOverallState(BaseModel):
    model_config = {"arbitrary_types_allowed": True, "use_enum_values": True}

    # Classification parameters
    taxonomy: Taxonomy
    user_id: str
    models: list[AIModel]
    batch_size: int = Field(default=3, gt=0)
    total_invocations: int
    majority_threshold: float

    # Configurations
    use_human_in_the_loop: bool = Field(default=False)
    is_for_single_batch: bool = Field(default=False)

    # Items and class nodes
    items: Annotated[list[ItemState], item_reducer] = Field(default_factory=list)
    root_node_id: str = Field(default=ROOT_NODE_ID)
    nodes: Annotated[list[ClassNodeState], node_reducer] = Field(
        default_factory=lambda: [],
    )
    items_need_further_classification: Annotated[list[ItemState], extend_list] = Field(
        default_factory=list
    )

    # Internal variables
    cases_need_further_classification: Annotated[
        list[dict[str, ItemState]], extend_list
    ] = Field(
        default_factory=list,
        description="The cases that need further classification. The key is the id of the parent node of the branch, and the value is the item that needs further classification.",
    )


class ClassificationReturnState(BaseModel):
    classified_item: ItemState
    cases_need_further_classification: Annotated[
        list[dict[str, ItemState]], extend_list
    ] = Field(default_factory=list)


class ResolveReturnState(BaseModel):
    nodes: Annotated[list[ClassNodeState], node_reducer]
    classified_item: Optional[ItemState] = Field(default=None)
    # TODO: add removeNode removeNodeId


class ExamineNodesReturnState(BaseModel):
    new_child_nodes: Annotated[list[ClassNodeState], operator.add]


# ===========================================
#                 INTERRUPTS
# ===========================================
class InterruptType(Enum):
    GET_USER_MESSAGE = "get_user_message"
    NEXT_BATCH = "next_batch"
