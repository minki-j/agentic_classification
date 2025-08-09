from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.schemas.user import UserResponse, UserInResponse, UserUpdate
from app.db.database import get_db
from motor.core import AgnosticDatabase
from pymongo import ReturnDocument


router = APIRouter()


@router.get("/me", response_model=UserInResponse)
async def read_user_me(
    current_user: UserInDB = Depends(get_current_user),
) -> Any:
    """Get current user info"""
    user_response = UserResponse(
        **current_user.model_dump(by_alias=False, context={"keep_objectid": False})
    )
    return UserInResponse(user=user_response)


@router.patch("/me", response_model=UserInResponse)
async def update_user_me(
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AgnosticDatabase = Depends(get_db),
) -> Any:
    """Update current user info"""
    update_data = user_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No user data provided to update")

    # Use find_one_and_update to update and return the updated document in one operation
    updated_user_doc = await db.users.find_one_and_update(
        {"_id": current_user.id},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,  # Return the document after update
    )

    if not updated_user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = UserInDB(**updated_user_doc)
    user_response = UserResponse(
        **updated_user.model_dump(by_alias=False, context={"keep_objectid": False})
    )
    return UserInResponse(user=user_response)
