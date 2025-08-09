from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from bson import ObjectId
from datetime import datetime
import dspy

from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.models.item import ItemInDB
from app.models.taxonomy import ClassifierState
from app.models.node import NodeInDB
from app.schemas.classification import (
    ClassificationRequest,
    ClassificationResponse,
    ExaminationRequest,
    ExaminationResponse,
    ClassificationStatusResponse,
    ClassifierStateUpdate,
    RemoveClassificationRequest,
    RemoveClassificationResponse,
    AddClassificationRequest,
    VerifyClassificationRequest,
    UpdateFewShotExamplesRequest,
    OptimizePromptWithDspyRequest,
    RemoveClassificationItemsOnlyRequest,
)
from app.db.database import get_db
from app.services.classifier_service import ClassifierService
from app.websocket.manager import connection_manager
from motor.core import AgnosticDatabase
from agents.state import Taxonomy
from app.services.dspy_optimizer import DspyOptimizer
from app.models.taxonomy import TaxonomyInDB


router = APIRouter()

active_sessions = {}


@router.post("/classify", response_model=ClassificationResponse)
async def classify_batch(
    request: ClassificationRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Start classification of a batch of items"""
    # Verify taxonomy exists and belongs to user
    taxonomy_doc = await db.taxonomies.find_one(
        {"_id": ObjectId(request.taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy_doc:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Check if nodes exist for taxonomy
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]
    nodes_count = await nodes_collection.count_documents({})

    if nodes_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No nodes found for taxonomy. Create initial nodes first.",
        )

    # Create classifier service with state loaded from DB
    classifier_service = await ClassifierService.create(
        connection_manager,
        request.taxonomy_id,
        str(current_user.id),
        db,
    )

    # Using background tasks will allow use to return the response immediately, while the long running task is running in the background. The progress of the task will be delivered via websocket.
    background_tasks.add_task(
        classifier_service.classify_batch,
        taxonomy_id=request.taxonomy_id,
        taxonomy=Taxonomy(
            id=str(taxonomy_doc["_id"]),
            name=taxonomy_doc["name"],
            aspect=taxonomy_doc["aspect"],
        ),
        batch_size=request.batch_size or 2,
        user_id=str(current_user.id),
        db=db,
        models=request.models,
        majority_threshold=request.majority_threshold,
        total_invocations=request.total_invocations,
    )

    return ClassificationResponse(
        message="Classification started",
        items_classified=0,
        status="running",
    )


@router.post("/examine", response_model=ExaminationResponse)
async def examine_nodes(
    request: ExaminationRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Start examination of nodes that need improvement"""
    # Verify taxonomy exists and belongs to user
    taxonomy_doc = await db.taxonomies.find_one(
        {"_id": ObjectId(request.taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy_doc:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Check if nodes exist
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]
    nodes_count = await nodes_collection.count_documents({})

    if nodes_count == 0:
        raise HTTPException(status_code=400, detail="No nodes found for taxonomy")

    # Create classifier service with state loaded from DB
    classifier_service = await ClassifierService.create(
        connection_manager,
        request.taxonomy_id,
        str(current_user.id),
        db,
    )

    background_tasks.add_task(
        classifier_service.examine_nodes,
        taxonomy_id=request.taxonomy_id,
        taxonomy=Taxonomy(
            id=str(taxonomy_doc["_id"]),
            name=taxonomy_doc["name"],
            aspect=taxonomy_doc["aspect"],
        ),
        user_id=str(current_user.id),
        db=db,
        force_node_ids=request.force_examine_node_ids,
    )

    return ExaminationResponse(
        message="Node examination started",
        nodes_examined=[],
        status="running",
    )


@router.post("/remove", response_model=RemoveClassificationResponse)
async def remove_classification(
    request: RemoveClassificationRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Remove a classification from an item"""
    # Remove the classification from the item
    user_items_collection = db[f"items_{str(current_user.id)}"]
    await user_items_collection.update_one(
        {
            "_id": ObjectId(request.item_id),
            f"classified_as.{request.taxonomy_id}": {
                "$exists": True,
                "$ne": None,
                "$type": "array",
            },
        },
        {
            "$pull": {
                f"classified_as.{request.taxonomy_id}": {
                    "node_id": request.node_id_to_remove
                }
            }
        },
    )

    # Remove the classification from the node
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]
    await nodes_collection.update_one(
        {
            "_id": ObjectId(request.node_id_to_remove),
            "items": {"$exists": True, "$ne": None, "$type": "array"},
        },
        {"$pull": {"items": {"item_id": request.item_id}}},
    )

    return RemoveClassificationResponse(
        message="Classification removed",
        status="success",
    )


@router.post("/remove-items-only", response_model=RemoveClassificationResponse)
async def remove_classification_items_only(
    request: RemoveClassificationItemsOnlyRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Remove a classification from an item"""
    # Remove the classification from the item
    user_items_collection = db[f"items_{str(current_user.id)}"]
    await user_items_collection.update_many(
        {
            "_id": {"$in": [ObjectId(item_id) for item_id in request.item_ids]},
            f"classified_as.{request.taxonomy_id}": {
                "$exists": True,
                "$ne": None,
                "$type": "array",
            },
        },
        {
            "$pull": {
                f"classified_as.{request.taxonomy_id}": {
                    "node_id": request.node_id_to_remove
                }
            }
        },
    )

    return RemoveClassificationResponse(
        message="Classification removed",
        status="success",
    )


@router.post("/add", status_code=status.HTTP_204_NO_CONTENT)
async def add_classification(
    request: AddClassificationRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Manually add a classification to an item"""
    user_items_collection = db[f"items_{str(current_user.id)}"]
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]

    # Add the classification to the item
    await user_items_collection.update_one(
        {"_id": ObjectId(request.item_id)},
        {
            "$push": {
                f"classified_as.{request.taxonomy_id}": {
                    "node_id": request.node_id,
                    "confidence_score": 1.0,
                    "is_verified": True,
                    "used_as_few_shot_example": False,
                    "updated_at": datetime.now(),
                }
            }
        },
    )

    # Add the item to the node
    await nodes_collection.update_one(
        {"_id": ObjectId(request.node_id)},
        {
            "$push": {
                "items": {
                    "item_id": request.item_id,
                    "confidence_score": request.confidence_score,
                }
            }
        },
    )


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_classification(
    request: VerifyClassificationRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Verify a classification for an item"""
    user_items_collection = db[f"items_{str(current_user.id)}"]
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]

    if request.item_ids_to_verify:
        for item_id in request.item_ids_to_verify:
            await user_items_collection.update_one(
                {
                    "_id": ObjectId(item_id),
                    f"classified_as.{request.taxonomy_id}.node_id": request.node_id,
                },
                {
                    "$set": {
                        f"classified_as.{request.taxonomy_id}.$.is_verified": True,
                        f"classified_as.{request.taxonomy_id}.$.updated_at": datetime.now(),
                    }
                },
            )
            await nodes_collection.update_one(
                {
                    "_id": ObjectId(request.node_id),
                    "items.item_id": item_id,
                },
                {"$set": {"items.$.is_verified": True}},
            )

    if request.item_ids_to_unverify:
        for item_id in request.item_ids_to_unverify:
            await user_items_collection.update_one(
                {
                    "_id": ObjectId(item_id),
                    f"classified_as.{request.taxonomy_id}.node_id": request.node_id,
                },
                {
                    "$set": {
                        f"classified_as.{request.taxonomy_id}.$.is_verified": False,
                        f"classified_as.{request.taxonomy_id}.$.updated_at": datetime.now(),
                    }
                },
            )
            await nodes_collection.update_one(
                {
                    "_id": ObjectId(request.node_id),
                    "items.item_id": item_id,
                },
                {"$set": {"items.$.is_verified": False}},
            )


@router.post("/update-few-shot-examples", status_code=status.HTTP_204_NO_CONTENT)
async def update_few_shot_examples(
    request: UpdateFewShotExamplesRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Update the few shot examples for a node"""
    item_ids_to_add = request.item_ids_to_add
    item_ids_to_remove = request.item_ids_to_remove

    user_items_collection = db[f"items_{str(current_user.id)}"]
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]

    for item_id in item_ids_to_add:
        await user_items_collection.update_one(
            {
                "_id": ObjectId(item_id),
                f"classified_as.{request.taxonomy_id}.node_id": request.node_id,
            },
            {
                "$set": {
                    f"classified_as.{request.taxonomy_id}.$.used_as_few_shot_example": True,
                    f"classified_as.{request.taxonomy_id}.$.updated_at": datetime.now(),
                }
            },
        )
        await nodes_collection.update_one(
            {
                "_id": ObjectId(request.node_id),
                "items.item_id": item_id,
            },
            {"$set": {"items.$.used_as_few_shot_example": True}},
        )
    for item_id in item_ids_to_remove:
        await user_items_collection.update_one(
            {
                "_id": ObjectId(item_id),
                f"classified_as.{request.taxonomy_id}.node_id": request.node_id,
            },
            {
                "$set": {
                    f"classified_as.{request.taxonomy_id}.$.used_as_few_shot_example": False,
                    f"classified_as.{request.taxonomy_id}.$.updated_at": datetime.now(),
                }
            },
        )
        await nodes_collection.update_one(
            {
                "_id": ObjectId(request.node_id),
                "items.item_id": item_id,
            },
            {"$set": {"items.$.used_as_few_shot_example": False}},
        )


@router.get("/status/{session_id}", response_model=ClassificationStatusResponse)
async def get_classification_status(
    session_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Get the status of a classification or examination session"""
    session_info = active_sessions.get(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_info["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Not authorized to access this session"
        )

    # Get progress information
    if session_info["type"] == "classification":
        user_items_collection = db[f"items_{str(current_user.id)}"]
        total_count = await user_items_collection.count_documents({})
        classified_count = await user_items_collection.count_documents(
            {"classified_as": {"$exists": True, "$ne": []}}
        )
        unclassified_count = total_count - classified_count

        progress = {
            "total_items": total_count,
            "classified_items": classified_count,
            "unclassified_items": unclassified_count,
        }
    else:
        # For examination, just return basic info
        nodes_collection = db[f"nodes_{session_info['taxonomy_id']}"]
        nodes_count = await nodes_collection.count_documents({})
        progress = {"total_nodes": nodes_count}

    return ClassificationStatusResponse(
        session_id=session_id,
        status=session_info["status"],
        progress=progress,
        current_batch=None,
        total_batches=None,
    )


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(
    session_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """Cancel an active classification or examination session"""
    session_info = active_sessions.get(session_id)

    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_info["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Not authorized to cancel this session"
        )

    # Note: We can't actually stop the background task once it's started
    # In production, I should use a task queue like Celery that supports cancellation


@router.put("/config/{taxonomy_id}", response_model=ClassifierState)
async def update_classifier_config(
    taxonomy_id: str,
    config_update: ClassifierStateUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Update classifier configuration for a taxonomy"""
    # Verify taxonomy exists and belongs to user
    taxonomy_doc = await db.taxonomies.find_one(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy_doc:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Get current state or create default
    current_state = taxonomy_doc.get("classifier_state")
    if current_state:
        state = ClassifierState(**current_state)
    else:
        state = ClassifierState()

    # Update only provided fields
    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(state, field, value)

    # Save updated state to database
    await db.taxonomies.update_one(
        {"_id": ObjectId(taxonomy_id)},
        {
            "$set": {
                "classifier_state": state.model_dump(),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return state


@router.get("/config/{taxonomy_id}", response_model=ClassifierState)
async def get_classifier_config(
    taxonomy_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Get classifier configuration for a taxonomy"""
    # Verify taxonomy exists and belongs to user
    taxonomy_doc = await db.taxonomies.find_one(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy_doc:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Get current state or return default
    current_state = taxonomy_doc.get("classifier_state")
    if current_state:
        return ClassifierState(**current_state)
    else:
        return ClassifierState()


@router.post("/dspy/optimize", status_code=status.HTTP_204_NO_CONTENT)
async def optimize_prompt_with_dspy(
    request: OptimizePromptWithDspyRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Optimize few shot examples for a node"""
    nodes_collection = db[f"nodes_{request.taxonomy_id}"]
    node = await nodes_collection.find_one({"_id": ObjectId(request.node_id)})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    node = NodeInDB(**node)

    items = node.items
    if items is None:
        raise HTTPException(status_code=400, detail="Node has no items")

    item_ids_to_optimize = [
        ObjectId(item.item_id) for item in items if item.is_verified
    ]
    if len(item_ids_to_optimize) < 15:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 30 verified items and found {len(item_ids_to_optimize)}",
        )

    user_items_collection = db[f"items_{str(current_user.id)}"]
    items_to_optimize = await user_items_collection.find(
        {"_id": {"$in": item_ids_to_optimize}}
    ).to_list(length=None)
    items_to_optimize = [ItemInDB(**item) for item in items_to_optimize]

    trainset = []
    for item in items_to_optimize:
        trainset.append(
            dspy.Example(review=item.content, category=node.label).with_inputs("review")
        )

    sibling_nodes = await nodes_collection.find(
        {"parent_node_id": node.parent_node_id}
    ).to_list(length=None)
    sibling_nodes = [NodeInDB(**sibling_node) for sibling_node in sibling_nodes]
    categories_labels = [sibling_node.label for sibling_node in sibling_nodes] + [
        node.label
    ]

    dspy_optimizer = DspyOptimizer(
        lm=dspy.LM("openai/gpt-4o-mini"),
        connection_manager=connection_manager,
        user_id=str(current_user.id),
        node_id=request.node_id,
        categories=categories_labels,
        trainset=trainset,
    )

    background_tasks.add_task(dspy_optimizer.compile)


@router.post("/init-trial-setup", status_code=status.HTTP_204_NO_CONTENT)
async def init_trial_setup(
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Initialize a trial setup for a user"""
    collections = await db.list_collection_names()
    if "sample_items" not in collections or "sample_nodes" not in collections:
        raise HTTPException(
            status_code=404, detail="sample_items collection not found in DB"
        )

    sample_taxonomy = TaxonomyInDB(
        user_id=str(current_user.id),
        name="Defect classification",
        aspect="I’m selling refurbished iPhones online, and customers have reported various defects. I want to categorize these issues in a clear, organized way so I can identify the most common problems, address them first, and understand which defects are rare.",
    )
    await db.taxonomies.insert_one(
        sample_taxonomy.model_dump(by_alias=True, context={"keep_objectid": True})
    )

    pipeline = [
        {"$match": {}},
        {"$out": f"items_{str(current_user.id)}"},
    ]
    await db.sample_items.aggregate(pipeline).to_list(None)

    pipeline = [
        {"$match": {}},
        {"$out": f"nodes_{str(sample_taxonomy.id)}"},
    ]
    await db.sample_nodes.aggregate(pipeline).to_list(None)
