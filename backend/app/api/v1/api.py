from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    taxonomies,
    items,
    nodes,
    classification,
    websocket,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(taxonomies.router, prefix="/taxonomies", tags=["taxonomies"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(
    classification.router, prefix="/classification", tags=["classification"]
)
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
