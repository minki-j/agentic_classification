from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
import httpx
from urllib.parse import urlencode

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.database import get_db
from app.models.user import UserInDB
from app.schemas.auth import Token, GoogleAuthUrl, RefreshTokenRequest
from motor.core import AgnosticDatabase


router = APIRouter()

# Configure OAuth
config = Config(
    environ={
        "GOOGLE_CLIENT_ID": settings.GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": settings.GOOGLE_CLIENT_SECRET,
    }
)

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# @router.get("/google/login", response_model=GoogleAuthUrl)
# async def google_login(request: Request) -> Any:
#     """Get Google OAuth login URL"""
#     redirect_uri = settings.GOOGLE_REDIRECT_URI
#     google_client = oauth.create_client("google")
#     redirect_response = await google_client.authorize_redirect(request, redirect_uri)  # type: ignore
#     return {"auth_url": str(redirect_response.headers.get("Location"))}


@router.get("/google/login/redirect")
async def google_login_redirect(request: Request) -> Any:
    """Redirect to Google OAuth login"""
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    google_client = oauth.create_client("google")
    return await google_client.authorize_redirect(request, redirect_uri)  # type: ignore


@router.get("/google/callback")
async def google_callback(
    request: Request, db: AgnosticDatabase = Depends(get_db)
) -> Any:
    """Handle Google OAuth callback"""
    try:
        google_client = oauth.create_client("google")
        token = await google_client.authorize_access_token(request)  # type: ignore
    except Exception as e:
        # Redirect to frontend with error
        error_params = urlencode({"error": "authentication_failed: " + str(e)})
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?{error_params}"
        )

    # Get user info from Google
    user_info = token.get("userinfo")
    if not user_info:
        # Fetch user info if not in token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            user_info = response.json()

    # Check if user exists using 'sub' field (OpenID Connect subject identifier)
    # This is Google's unique identifier for the user
    existing_user = await db.users.find_one({"google_id": user_info["sub"]})

    if existing_user:
        # Update user info
        await db.users.update_one(
            {"_id": existing_user["_id"]},
            {
                "$set": {
                    "name": user_info.get("name", existing_user["name"]),
                    "picture": user_info.get("picture", existing_user.get("picture")),
                }
            },
        )
        user_id = str(existing_user["_id"])
    else:
        # Create new user
        new_user = UserInDB(
            email=user_info["email"],
            name=user_info.get("name", user_info["email"].split("@")[0]),
            google_id=user_info["sub"],
            picture=user_info.get("picture"),
        )

        result = await db.users.insert_one(
            new_user.model_dump(by_alias=True, context={"keep_objectid": True})
        )
        print("New user created: result")
        user_id = str(result.inserted_id)

    # Create tokens
    access_token = create_access_token(subject=user_id)
    refresh_token = create_refresh_token(subject=user_id)

    # Redirect to frontend with tokens
    auth_params = urlencode(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?{auth_params}")


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest, db: AgnosticDatabase = Depends(get_db)
) -> Any:
    """Refresh access token using refresh token"""
    from app.core.security import verify_token
    from bson import ObjectId

    user_id = verify_token(request.refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # Verify user still exists and is active
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
        )

    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens
    access_token = create_access_token(subject=user_id)
    new_refresh_token = create_refresh_token(subject=user_id)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }
