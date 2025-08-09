import random
import asyncio
import logging
from bson import ObjectId
from typing import Any, Type, Set, Union, Optional, Tuple, Callable
from pydantic import BaseModel, create_model
from pydantic_core import PydanticUndefined

from app.db.database import get_user_items_collection
from app.models.item import ItemInDB

from agents.state import ItemState, ClassNodeState
from agents.llm_factory import AIModel

logger = logging.getLogger(__name__)


########################################################
# Node ID abbreviation functions
########################################################


def abbreviate_node_ids(
    nodes: list[ClassNodeState],
) -> tuple[list[ClassNodeState], dict[str, str], dict[str, str]]:
    if not nodes:
        raise ValueError("Nodes are empty")
    if any(node.id is None for node in nodes):
        raise ValueError("Node can't have None id: ", nodes)

    nodes_copy = [node.model_copy() for node in nodes]

    node_ids = [node.id for node in nodes_copy if node.id is not None]
    parent_node_ids = [
        node.parent_node_id for node in nodes_copy if node.parent_node_id is not None
    ]
    all_ids = set(node_ids + parent_node_ids)
    all_ids = [id for id in all_ids if id is not None and id != ""]

    new_node_ids = []
    original_id_to_abbreviated_map = {}
    abbreviated_id_to_original_map = {}
    for node_id in all_ids:
        # pick random 4 characters from the node_id
        while True:
            new_node_id = "".join(random.choices(node_id, k=4))
            if new_node_id not in new_node_ids:
                new_node_ids.append(new_node_id)
                original_id_to_abbreviated_map[node_id] = new_node_id
                abbreviated_id_to_original_map[new_node_id] = node_id
                break

    for node in nodes_copy:
        if node.id is not None:
            node.id = original_id_to_abbreviated_map[node.id]
        if node.parent_node_id is not None and node.parent_node_id != "":
            node.parent_node_id = original_id_to_abbreviated_map[node.parent_node_id]

    return nodes_copy, abbreviated_id_to_original_map, original_id_to_abbreviated_map


def restore_abbreviated_node_ids(
    nodes: list[ClassNodeState], shortened_id_to_original_map: dict[str, str]
) -> list[ClassNodeState]:
    if not nodes:
        raise ValueError("Nodes are empty")

    nodes_copy = [node.model_copy() for node in nodes]

    new_short_id_to_long_id_map = {}
    for node in nodes_copy:
        if node.id is None:
            raise ValueError(f"Node id is None: {node}")

        if node.id in shortened_id_to_original_map:
            node.id = shortened_id_to_original_map[node.id]
        elif node.id in new_short_id_to_long_id_map:
            node.id = new_short_id_to_long_id_map[node.id]
        else:
            new_node_id = str(ObjectId())
            new_short_id_to_long_id_map[node.id] = new_node_id
            node.id = new_node_id

        if node.parent_node_id is not None and node.parent_node_id != "":
            if node.parent_node_id in shortened_id_to_original_map:
                node.parent_node_id = shortened_id_to_original_map[node.parent_node_id]
            elif node.parent_node_id in new_short_id_to_long_id_map:
                node.parent_node_id = new_short_id_to_long_id_map[node.parent_node_id]
            else:
                new_parent_node_id = str(ObjectId())
                new_short_id_to_long_id_map[node.parent_node_id] = new_parent_node_id
                node.parent_node_id = new_parent_node_id

    return nodes_copy


########################################################
# Item formatting functions
########################################################
def format_single_item(item: ItemState) -> str:
    return f"""
<Item>
{item.content}
</Item>
""".strip()


def format_batch_items(
    items: list[ItemState] | ItemState, include_id: bool = True
) -> str:
    if isinstance(items, ItemState):
        items = [items]

    formatted_string = "\n".join(
        [
            f"<Item{f' id={item.id}' if include_id else ''}>{item.content}</Item>"
            for item in items
        ]
    )
    if formatted_string.strip() == "":
        raise ValueError("Items are empty")
    return formatted_string


########################################################
# Node formatting functions
########################################################


async def format_node_examples(
    example_item_ids: list[str], num_examples: int, max_length: int, user_id: str
) -> str:
    # fetch items from the database
    item_collection = get_user_items_collection(user_id)
    cursor = item_collection.find(
        {"_id": {"$in": [ObjectId(id) for id in example_item_ids]}}
    )
    items: list[ItemInDB] = [ItemInDB(**item) async for item in cursor]
    # print(f"Fetched {len(items)} items from db with ids: {example_item_ids}")
    # print(f"Items: {items}")

    formatted_examples = []
    for item in items[:num_examples]:
        # Truncate content if it exceeds max_length
        truncated_content = item.content[:max_length]

        # Replace newlines with spaces and strip whitespace
        cleaned_content = truncated_content.replace("\n", " ").strip()

        # Add ellipsis if content was truncated
        if len(item.content) > max_length:
            cleaned_content += "..."

        formatted_examples.append(f"- {cleaned_content}")

    formatted_string = "\n".join(formatted_examples)
    return formatted_string


async def format_single_node(
    node: ClassNodeState,
    user_id: str,
    include_parent_node_id: bool = True,
    num_examples: int = 10,
    max_length: int = 1000,
) -> str:
    """Format a single ClassNode into a readable string representation."""
    lines = [
        f"Id: {node.id}",
    ]

    if include_parent_node_id:
        parent_info = node.parent_node_id or "None"
        lines.append(f"Parent Node ID: {parent_info}")

    lines.extend(
        [
            f"Label: {node.label}",
            f"Description: {node.description}",
        ]
    )

    # Add few shot items if they exist
    if num_examples > 0:
        few_shot_item_ids = [
            item.item_id for item in node.items or [] if item.used_as_few_shot_example
        ]
        if few_shot_item_ids:
            formatted_examples = await format_node_examples(
                few_shot_item_ids, num_examples, max_length, user_id
            )
            lines.append(f"Exemplary Items:\n{formatted_examples}")

    return "\n".join(lines)


async def format_class_nodes(
    nodes: list[ClassNodeState] | ClassNodeState,
    num_examples: int,
    max_length: int,
    user_id: str,
    include_parent_node_id: bool = True,
) -> str:
    if isinstance(nodes, ClassNodeState):
        nodes = [nodes]

    return "\n\n".join(
        await asyncio.gather(
            *[
                format_single_node(
                    node, user_id, include_parent_node_id, num_examples, max_length
                )
                for node in nodes
            ]
        )
    )


async def format_children_nodes_from_parent_node_ids(
    nodes: list[ClassNodeState],
    parent_node_ids: list[str] | str,
    user_id: str,
    num_examples: int = 10,
    max_length: int = 1000,
) -> str:
    if isinstance(parent_node_ids, str):
        parent_node_ids = [parent_node_ids]

    nodes_to_format = []
    for parent_node_id in parent_node_ids:
        # Find the parent node
        parent_node = next((node for node in nodes if node.id == parent_node_id), None)
        if parent_node is None:
            continue

        # Find all children nodes for this parent
        children_nodes = [
            node for node in nodes if node.parent_node_id == parent_node_id
        ]

        if children_nodes:  # Only add if there are children
            nodes_to_format.append(
                {"parent_node": parent_node, "children_nodes": children_nodes}
            )

    if len(nodes_to_format) == 0:
        raise ValueError("No nodes to format")

    formatted_string = "\n\n".join(
        [
            f"""
<ParentNode>
{await format_class_nodes(parent_children_dict["parent_node"], num_examples=num_examples, max_length=max_length, include_parent_node_id=False, user_id=user_id)}
</ParentNode>

<ChildNodes>
{await format_class_nodes(parent_children_dict["children_nodes"], num_examples=num_examples, max_length=max_length, include_parent_node_id=False, user_id=user_id)}
</ChildNodes>
            """.strip()
            for parent_children_dict in nodes_to_format
        ]
    )

    if formatted_string.strip() == "":
        raise ValueError("Formmatted nodes string is empty")

    return formatted_string


########################################################
# Utility functions
########################################################


def has_children_nodes(nodes: list[ClassNodeState], parent_node_id: str) -> bool:
    return any(node.parent_node_id == parent_node_id for node in nodes)


def get_model_count_dict(
    models: list[AIModel], total_invocations: int
) -> dict[AIModel, int]:
    average_call_per_model = total_invocations // len(models)
    remainder = total_invocations % len(models)

    model_call_count_map = {}

    for model in models:
        model_call_count_map[model] = average_call_per_model

    for model in models[:remainder]:
        model_call_count_map[model] += 1

    return model_call_count_map


def choose_top_node_ids_from_classification_results(
    classification_results: list[Any], majority_threshold: float
) -> list[tuple[str, float]]:
    """
    Filters and ranks node IDs based on classification results.

    Selects the most frequently occurring nodes while ensuring:
    1. The top node is always included
    2. Total selected nodes don't exceed TOP_K_THRESHOLD of total classifications
    3. Individual nodes appear in at least majority_threshold of classifications

    Returns:
        list[tuple[str, float]]: A list of tuples containing node IDs and their confidence scores.
    """

    # Count frequency of each node across all classification results
    node_frequency_counts = {}
    for classification_result in classification_results:
        if not classification_result.node_ids:
            node_frequency_counts["empty"] = node_frequency_counts.get("empty", 0) + 1
            continue
        for node_id in classification_result.node_ids:
            node_frequency_counts[node_id] = node_frequency_counts.get(node_id, 0) + 1

    # Sort nodes by frequency (highest to lowest)
    sorted_nodes_by_frequency = dict(
        sorted(node_frequency_counts.items(), key=lambda item: item[1], reverse=True)
    )

    total_classifications = len(classification_results)
    min_count = int(total_classifications * majority_threshold + 0.5)  # round up

    # Filter nodes based on thresholds
    selected_node_and_confidence_score = []
    top_node_included = False
    for node_id, frequency_count in sorted_nodes_by_frequency.items():
        confidence_score = frequency_count / total_classifications
        # Always include the top-ranked node
        if not top_node_included:
            if node_id != "empty":
                selected_node_and_confidence_score.append((node_id, confidence_score))
            top_node_included = True
            continue

        if node_id == "empty":
            continue

        # Check if this node meets minimum frequency requirement
        if frequency_count < min_count:
            break

        selected_node_and_confidence_score.append((node_id, confidence_score))

    return selected_node_and_confidence_score


def exclude_fields(
    original_model: Type[BaseModel],
    exclude_fields: Union[Set[str], list[str]],
    new_model_name: Optional[str] = None,
) -> Tuple[Type[BaseModel], Callable]:
    """
    Create a new Pydantic model based on an existing one, excluding specified fields,
    and return a converter function to convert back to the original model.

    Args:
        original_model: The original Pydantic model class
        exclude_fields: Set or list of field names to exclude
        new_model_name: Name for the new model class (optional)

    Returns:
        Tuple of (new_model_class, converter_function)
        - new_model_class: New Pydantic model class with excluded fields
        - converter_function: Function to convert new_model instance to original_model instance
    """
    if isinstance(exclude_fields, list):
        exclude_fields = set(exclude_fields)

    if new_model_name is None:
        new_model_name = f"{original_model.__name__}V2"

    # Get all fields from the original model
    original_fields = original_model.model_fields

    # Create dictionary of fields to include in new model
    new_fields = {}
    excluded_field_defaults = {}

    for field_name, field_info in original_fields.items():
        if field_name not in exclude_fields:
            # Preserve the field annotation and default value
            new_fields[field_name] = (field_info.annotation, field_info)
        else:
            # Check if excluded field is optional (has default value or factory)
            if field_info.default is not PydanticUndefined:
                excluded_field_defaults[field_name] = field_info.default
            elif field_info.default_factory is not None:
                excluded_field_defaults[field_name] = field_info.default_factory
            else:
                # Field has no default - raise an error
                raise ValueError(
                    f"Cannot exclude required field '{field_name}' from model '{original_model.__name__}'. "
                    f"Only optional fields (with default values or default factories) can be excluded."
                )

    # Create the new model
    new_model = create_model(new_model_name, **new_fields)

    # Create converter function
    def convert_to_original(new_instance: BaseModel) -> BaseModel:
        """Convert an instance of the new model to the original model."""
        # Get all data from the new instance
        data = new_instance.model_dump()

        # Add excluded fields with their default values
        for field_name, default_value in excluded_field_defaults.items():
            if callable(default_value):  # default_factory case
                data[field_name] = default_value()
            else:
                data[field_name] = default_value

        # Create and return original model instance
        return original_model(**data)

    return new_model, convert_to_original
