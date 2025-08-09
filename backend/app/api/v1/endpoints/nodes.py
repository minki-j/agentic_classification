from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from bson import ObjectId
import uuid
from datetime import datetime
import logging

from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.models.node import NodeInDB
from app.models.taxonomy import TaxonomyInDB
from app.schemas.node import (
    NodeResponse,
    NodesInResponse,
    InitialNodesRequest,
    InitialNodesResponse,
    NodeCreate,
    NodeUpdate,
    ParentUpdate,
    NodeUpdateResultResponse,
)
from app.db.database import get_db, get_user_items_collection
from app.services.classifier_service import ClassifierService
from app.websocket.manager import connection_manager
from motor.core import AgnosticDatabase
from agents.state import ItemState, ClassNodeState, Taxonomy, NodeAndConfidence
from app.db.serializers import MongoSerializer
from app.models.item import ItemInDB


router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/initial", response_model=InitialNodesResponse)
async def create_initial_nodes(
    request: InitialNodesRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    print(request)
    """Create initial nodes for a taxonomy using selected items"""
    # Verify taxonomy exists and belongs to user
    taxonomy = await db.taxonomies.find_one(
        {"_id": ObjectId(request.taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    taxonomy = TaxonomyInDB(**taxonomy)

    # Check if nodes already exist for this taxonomy
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]
    existing_nodes = await nodes_collection.count_documents({})

    if existing_nodes > 0:
        raise HTTPException(
            status_code=400, detail="Nodes already exist for this taxonomy"
        )

    # Get the requested number of items (preferably unclassified ones)
    user_items_collection = get_user_items_collection(str(current_user.id))

    # Get any items up to the requested amount
    items_cursor = user_items_collection.find({}).limit(request.num_of_items_to_use)
    items = await items_cursor.to_list()

    if not items:
        raise HTTPException(status_code=400, detail="No items found to create nodes")

    items = [ItemInDB(**item) for item in items]

    # Convert to Item objects
    items = [
        MongoSerializer.serialize_item_to_state(item, request.taxonomy_id)
        for item in items
    ]

    # Create the classifier service with state loaded from DB
    classifier_service = await ClassifierService.create(
        connection_manager,
        request.taxonomy_id,
        str(current_user.id),
        db,
    )

    background_tasks.add_task(
        classifier_service.create_initial_nodes,
        taxonomy_id=request.taxonomy_id,
        taxonomy=Taxonomy(
            **taxonomy.model_dump(by_alias=False, context={"keep_objectid": False})
        ),
        items=items,
        llm_name=request.llm_name,
        user_id=str(current_user.id),
        db=db,
    )

    return InitialNodesResponse(
        message="Initial node creation started",
    )


@router.get("/{taxonomy_id}", response_model=NodesInResponse)
async def list_nodes(
    taxonomy_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """List all nodes for a taxonomy"""
    # Verify taxonomy exists and belongs to user
    taxonomy = await db.taxonomies.find_one(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Get all nodes for taxonomy
    nodes_collection = db[f"nodes_{taxonomy_id}"]
    cursor = nodes_collection.find({})
    nodes = await cursor.to_list(length=None)

    # Convert to response format
    node_responses = []
    for node in nodes:
        node_responses.append(
            NodeResponse(
                id=str(node["_id"]),
                parent_node_id=node["parent_node_id"],
                label=node["label"],
                description=node["description"],
                items=node.get("items", []),
                created_at=node["created_at"],
                updated_at=node["updated_at"],
            )
        )

    return NodesInResponse(nodes=node_responses, count=len(node_responses))


@router.get("/{taxonomy_id}/{node_id}", response_model=NodeResponse)
async def get_node(
    taxonomy_id: str,
    node_id: str,  # This is the 4-character node ID, not MongoDB _id
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Get a specific node by its node_id"""
    # Find node by taxonomy_id and node_id
    nodes_collection = db[f"nodes_{taxonomy_id}"]
    node = await nodes_collection.find_one(
        {
            "_id": node_id,
        }
    )

    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    return NodeResponse(
        id=str(node["_id"]),
        parent_node_id=node["parent_node_id"],
        label=node["label"],
        description=node["description"],
        items=node.get("items", []),
        created_at=node["created_at"],
        updated_at=node["updated_at"],
    )


@router.patch("/{taxonomy_id}/{node_id}")
async def update_node(
    taxonomy_id: str,
    node_id: str,
    update_data: NodeUpdate,
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Update a node's label and description"""

    if all(value is None for value in update_data.model_dump().values()):
        raise HTTPException(status_code=400, detail="No update data provided")

    # Update the node
    nodes_collection = db[f"nodes_{taxonomy_id}"]
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}

    update_dict["updated_at"] = datetime.utcnow()
    result = await nodes_collection.update_one(
        {"_id": ObjectId(node_id)},
        {"$set": update_dict},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Node not found")


@router.post("/{taxonomy_id}", response_model=NodeResponse)
async def create_node(
    taxonomy_id: str,
    node_data: NodeCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Create a new node"""
    # Verify taxonomy exists and belongs to user
    taxonomy = await db.taxonomies.find_one(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Create the node
    nodes_collection = db[f"nodes_{taxonomy_id}"]

    node = MongoSerializer.deserialize_node_from_request(node_data)

    await nodes_collection.insert_one(node)

    node["id"] = str(node["_id"])
    del node["_id"]

    return NodeResponse(**node)


@router.delete("/{taxonomy_id}/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    taxonomy_id: str,
    node_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Delete a specific node from a taxonomy"""
    nodes_collection = db[f"nodes_{taxonomy_id}"]

    # Check if node has children
    children = await nodes_collection.find_one({"parent_node_id": node_id})
    if children:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete node with children. Delete or reassign children first.",
        )

    # Delete the node
    result = await nodes_collection.delete_one({"_id": ObjectId(node_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Node not found")

    # Remove this node from any item classifications
    items_collection = get_user_items_collection(str(current_user.id))
    await items_collection.update_many(
        {}, {"$pull": {"nodes_and_confidences": {"node_id": node_id}}}
    )


@router.delete("/{taxonomy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_nodes(
    taxonomy_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Delete all nodes for a taxonomy"""
    nodes_collection = db[f"nodes_{taxonomy_id}"]
    await nodes_collection.delete_many({})
