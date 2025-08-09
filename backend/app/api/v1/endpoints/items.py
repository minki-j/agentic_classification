import random
import string
import logging
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from pydantic import ValidationError

from app.api.deps import get_current_user, get_user_items_collection
from app.models.user import UserInDB
from app.models.item import ItemInDB
from app.schemas.item import (
    ItemResponse,
    ItemInResponse,
    ItemsInResponse,
    ItemUploadRequest,
    GetIdsByListOfContentRequest,
)
from app.db.database import get_db
from motor.motor_asyncio import AsyncIOMotorCollection
from agents.state import ItemState, NodeAndConfidence
from app.db.serializers import MongoSerializer


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/upload",
    response_model=ItemsInResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_items(
    request: ItemUploadRequest,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """
    Upload multiple items for classification
    """
    if not request.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No item data providedto upload",
        )

    items_to_insert = [
        ItemInDB(content=item_data.content) for item_data in request.items
    ]

    result = await user_items_collection.insert_many(
        [
            item.model_dump(by_alias=True, context={"keep_objectid": True})
            for item in items_to_insert
        ]
    )
    logger.info(f"Successfully uploaded {len(result.inserted_ids)} items")

    return ItemsInResponse(
        items=[
            MongoSerializer.serialize_item_to_response(item) for item in items_to_insert
        ],
        count=len(result.inserted_ids),
        unclassified_count=len(result.inserted_ids),
    )


@router.get("/{taxonomy_id}/{item_id}", response_model=ItemInResponse)
async def get_item(
    taxonomy_id: str,
    item_id: str,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """Get item by ID"""
    item = await user_items_collection.find_one({"id": item_id})

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item = ItemInDB(**item)

    return ItemInResponse(
        item=MongoSerializer.serialize_item_to_response(item, taxonomy_id)
    )


@router.get("/many", response_model=ItemsInResponse)
async def get_items_by_ids(
    taxonomy_id: str,
    item_ids: str,  # Changed from List[str] to str
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """Get multiple items by their IDs"""

    # Parse comma-separated item_ids string into a list
    item_ids_list = [id.strip() for id in item_ids.split(",") if id.strip()]

    if not item_ids_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid item IDs provided",
        )

    query = {"_id": {"$in": [ObjectId(item_id) for item_id in item_ids_list]}}
    cursor = user_items_collection.find(query).sort("updated_at", -1)
    items = await cursor.to_list(length=None)

    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No items found",
        )

    items = [ItemInDB(**item) for item in items]
    items_response = [
        MongoSerializer.serialize_item_to_response(item, taxonomy_id) for item in items
    ]

    return ItemsInResponse(
        items=items_response,
        count=len(items_response),
        unclassified_count=len(items_response),
    )


@router.get("/list", response_model=ItemsInResponse)
async def list_items(
    taxonomy_id: str,
    skip: int = 0,
    limit: int = 100,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """List user's items"""
    if not taxonomy_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy ID is required",
        )
    print(f"taxonomy_id: {taxonomy_id}")
    total_count = await user_items_collection.count_documents({})
    unclassified_count = await user_items_collection.count_documents(
        {f"classified_as.{taxonomy_id}": {"$exists": False}}
    )

    cursor = user_items_collection.find({}).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    items = [ItemInDB(**item) for item in items]

    return ItemsInResponse(
        items=[
            MongoSerializer.serialize_item_to_response(item, taxonomy_id)
            for item in items
        ],
        count=total_count,
        unclassified_count=unclassified_count,
    )


@router.get("/batch/{batch_size}", response_model=ItemsInResponse)
async def get_unclassified_batch(
    taxonomy_id: str,
    batch_size: int,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """Get a batch of unclassified items"""
    if batch_size <= 0 or batch_size > 100:
        raise HTTPException(
            status_code=400, detail="Batch size must be between 1 and 100"
        )

    # Get unclassified items for this taxonomy
    query = {
        f"classified_as.{taxonomy_id}": {"$exists": False},
    }

    cursor = user_items_collection.find(query).limit(batch_size)
    items = await cursor.to_list(length=batch_size)
    items = [ItemInDB(**item) for item in items]

    return ItemsInResponse(
        items=[
            MongoSerializer.serialize_item_to_response(item, taxonomy_id)
            for item in items
        ],
        count=len(items),
        unclassified_count=0,
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> None:
    """Delete an item"""
    result = await user_items_collection.delete_one({"id": ObjectId(item_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_items(
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> None:
    """Delete all items for the current user"""
    await user_items_collection.delete_many({})


@router.post("/get-ids-by-list-of-content", response_model=list[str])
async def get_ids_by_list_of_content(
    request: GetIdsByListOfContentRequest,
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """Get item IDs by list of content"""

    items = await user_items_collection.find(
        {"content": {"$in": request.content_list}}
    ).to_list(length=None)

    items = [ItemInDB(**item) for item in items]
    item_ids = [str(item.id) for item in items]
    return item_ids


@router.get("/export-all", response_model=list[ItemInDB])
async def export_all_items(
    user_items_collection: AsyncIOMotorCollection = Depends(get_user_items_collection),
) -> Any:
    """Export all items for the current user"""
    items = await user_items_collection.find({}).to_list(length=None)
    return [ItemInDB(**item) for item in items]
