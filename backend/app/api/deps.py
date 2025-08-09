from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from bson import ObjectId

from app.core.security import verify_token
from app.db.database import get_db
from app.models.user import UserInDB
from motor.core import AgnosticDatabase


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"/api/v1/auth/google/login", auto_error=False
)


async def get_current_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    """Extract and verify user ID from JWT token"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = verify_token(token, token_type="access")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id), db: AgnosticDatabase = Depends(get_db)
) -> UserInDB:
    """Get current authenticated user"""

    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = UserInDB(**user_doc)

    return user


async def get_current_active_superuser(
    current_user: UserInDB = Depends(get_current_user),
) -> UserInDB:
    """Get current active superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


def get_user_items_collection(
    user_id: str = Depends(get_current_user_id), db: AgnosticDatabase = Depends(get_db)
):
    """Get the items collection for a specific user"""
    return db[f"items_{user_id}"]
