import os
from dotenv import load_dotenv

# Load .env file - this must happen before any other imports that might use env vars
load_dotenv(override=True)

LOG_LEVEL = os.getenv("LOG_LEVEL")
if LOG_LEVEL is None:
    raise Exception("LOG_LEVEL environment variable is not set")

if os.getenv("LANGGRAPH_STUDIO") == "true":
    raise Exception(
        "LANGGRAPH_STUDIO is set to true. This is not allowed in production."
    )

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.database import init_db, close_db
from app.websocket.manager import connection_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()
    await connection_manager.disconnect_all()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for OAuth
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=False,  # Set to True in production with HTTPS
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=LOG_LEVEL,
    )
