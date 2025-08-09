from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.models.taxonomy import TaxonomyInDB
from app.schemas.taxonomy import (
    TaxonomyCreate,
    TaxonomyUpdate,
    TaxonomyInResponse,
    TaxonomiesInResponse,
)
from app.db.database import get_db
from app.db.serializers import MongoSerializer
from motor.core import AgnosticDatabase


router = APIRouter()


@router.post("", response_model=TaxonomyInResponse, status_code=status.HTTP_201_CREATED)
async def create_taxonomy(
    taxonomy_in: TaxonomyCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Create new taxonomy"""
    # Check if taxonomy with same name already exists for user
    existing = await db.taxonomies.find_one(
        {"user_id": str(current_user.id), "name": taxonomy_in.name}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Taxonomy with this name already exists",
        )

    taxonomy_db = TaxonomyInDB(
        user_id=str(current_user.id),
        **taxonomy_in.model_dump(),
    )

    await db.taxonomies.insert_one(
        taxonomy_db.model_dump(by_alias=True, context={"keep_objectid": True})
    )

    taxonomy_response = MongoSerializer.serialize_taxonomy_to_response(taxonomy_db)

    return TaxonomyInResponse(taxonomy=taxonomy_response)


@router.get("", response_model=TaxonomiesInResponse)
async def list_taxonomies(
    skip: int = 0,
    limit: int = 10,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """List user's taxonomies"""
    cursor = (
        db.taxonomies.find({"user_id": str(current_user.id)}).skip(skip).limit(limit)
    )
    taxonomies = [
        MongoSerializer.serialize_taxonomy_to_response(TaxonomyInDB(**taxonomy))
        for taxonomy in await cursor.to_list(length=limit)
    ]
    total_taxonomy_count = await db.taxonomies.count_documents(
        {"user_id": str(current_user.id)}
    )

    return TaxonomiesInResponse(
        taxonomies=taxonomies,
        count=total_taxonomy_count,
    )


@router.get("/{taxonomy_id}", response_model=TaxonomyInResponse)
async def get_taxonomy(
    taxonomy_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Get taxonomy by ID"""
    if not ObjectId.is_valid(taxonomy_id):
        raise HTTPException(status_code=400, detail="Invalid taxonomy ID")

    taxonomy = await db.taxonomies.find_one(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )

    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    taxonomy = MongoSerializer.serialize_taxonomy_to_response(TaxonomyInDB(**taxonomy))

    return TaxonomyInResponse(taxonomy=taxonomy)


@router.patch("/{taxonomy_id}", response_model=TaxonomyInResponse)
async def update_taxonomy(
    taxonomy_id: str,
    taxonomy_update: TaxonomyUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Update taxonomy"""
    if not ObjectId.is_valid(taxonomy_id):
        raise HTTPException(status_code=400, detail="Invalid taxonomy ID")

    update_data = taxonomy_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400, detail="No taxonomy data provided to update"
        )

    # Check if updating name and it already exists
    if "name" in update_data:
        existing = await db.taxonomies.find_one(
            {
                "user_id": str(current_user.id),
                "name": update_data["name"],
                "_id": {"$ne": ObjectId(taxonomy_id)},
            }
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Taxonomy with this name already exists",
            )

    updated_taxonomy = await db.taxonomies.find_one_and_update(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)},
        {"$set": update_data},
        return_document=True,
    )

    updated_taxonomy_response = MongoSerializer.serialize_taxonomy_to_response(
        TaxonomyInDB(**updated_taxonomy)
    )

    return TaxonomyInResponse(taxonomy=updated_taxonomy_response)


@router.delete("/{taxonomy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_taxonomy(
    taxonomy_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> None:
    """Delete taxonomy and all associated data"""
    if not ObjectId.is_valid(taxonomy_id):
        raise HTTPException(status_code=400, detail="Invalid taxonomy ID")

    # Find and delete taxonomy in one operation
    deleted_taxonomy = await db.taxonomies.find_one_and_delete(
        {"_id": ObjectId(taxonomy_id), "user_id": str(current_user.id)}
    )

    if not deleted_taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    # Drop the nodes collection for this taxonomy
    nodes_collection = db[f"nodes_{taxonomy_id}"]
    await nodes_collection.drop()

    # Note: Items are stored per user, not per taxonomy, so we don't delete them

    # Return 204 code
