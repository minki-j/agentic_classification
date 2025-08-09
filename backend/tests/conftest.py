"""
Pytest configuration and shared fixtures for API tests.
"""

import asyncio
import pytest
from typing import AsyncGenerator, Dict, Any
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from mongomock_motor import AsyncMongoMockClient
from fastapi import FastAPI
from jose import jwt
from datetime import datetime, timedelta
from bson import ObjectId

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import UserInDB
from app.db.database import get_db
from app.api.v1.api import api_router
from app.models.taxonomy import TaxonomyInDB
from app.models.node import NodeInDB
from agents.state import ItemState, Example, ItemUnderNode, NodeAndConfidence


# Override settings for testing
settings.MONGODB_DB_NAME = "test_taxonomy_agent"
settings.SECRET_KEY = "test-secret-key"
settings.GOOGLE_CLIENT_ID = "test-client-id"
settings.GOOGLE_CLIENT_SECRET = "test-client-secret"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Create a mock MongoDB database for testing."""
    client = AsyncMongoMockClient()
    db = client[settings.MONGODB_DB_NAME]
    yield db
    client.close()


@pytest.fixture
def app(mock_db: AsyncIOMotorDatabase) -> FastAPI:
    """Create a FastAPI app instance for testing."""
    from main import app as _app

    # Override database dependency
    async def override_get_db():
        return mock_db

    _app.dependency_overrides[get_db] = override_get_db
    return _app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(mock_db: AsyncIOMotorDatabase) -> UserInDB:
    """Create a test user in the database."""
    user = UserInDB(
        email="test@example.com",
        name="Test User",
        google_id="google-123",
        picture="https://example.com/picture.jpg",
        is_active=True,
        is_superuser=False,
    )

    result = await mock_db.users.insert_one(user.model_dump(by_alias=True))
    user_doc = await mock_db.users.find_one({"_id": result.inserted_id})
    return UserInDB(**user_doc)


@pytest.fixture
async def superuser(mock_db: AsyncIOMotorDatabase) -> UserInDB:
    """Create a superuser for testing."""
    user = UserInDB(
        email="admin@example.com",
        name="Admin User",
        google_id="google-admin-123",
        is_active=True,
        is_superuser=True,
    )

    result = await mock_db.users.insert_one(user.model_dump(by_alias=True))
    user_doc = await mock_db.users.find_one({"_id": result.inserted_id})
    return UserInDB(**user_doc)


@pytest.fixture
def auth_headers(test_user: UserInDB) -> Dict[str, str]:
    """Create authentication headers with a valid access token."""
    access_token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def superuser_headers(superuser: UserInDB) -> Dict[str, str]:
    """Create authentication headers for superuser."""
    access_token = create_access_token(subject=str(superuser.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def test_taxonomy(
    mock_db: AsyncIOMotorDatabase, test_user: UserInDB
) -> TaxonomyInDB:
    """Create a test taxonomy."""
    taxonomy = TaxonomyInDB(
        user_id=str(test_user.id),
        name="Test Taxonomy",
        aspect="category",
    )

    result = await mock_db.taxonomies.insert_one(taxonomy.model_dump(by_alias=True))
    taxonomy_doc = await mock_db.taxonomies.find_one({"_id": result.inserted_id})
    return TaxonomyInDB(**taxonomy_doc)


@pytest.fixture
async def test_nodes(
    mock_db: AsyncIOMotorDatabase, test_taxonomy: TaxonomyInDB, test_user: UserInDB
) -> list[NodeInDB]:
    """Create test nodes for a taxonomy."""
    nodes = [
        NodeInDB(
            node_id="node1",
            taxonomy_id=str(test_taxonomy.id),
            user_id=str(test_user.id),
            parent_node_id="q3iu",  # ROOT_NODE_ID
            label="Electronics",
            description="Electronic devices and gadgets",
            exemplary_items=[
                Example(content="Smartphone"),
                Example(content="Laptop"),
                Example(content="Tablet"),
            ],
            items=[
                ItemUnderNode(item_id="item1", confidence_score=0.9),
                ItemUnderNode(item_id="item2", confidence_score=0.85),
            ],
        ),
        NodeInDB(
            node_id="node2",
            taxonomy_id=str(test_taxonomy.id),
            user_id=str(test_user.id),
            parent_node_id="node1",
            label="Smartphones",
            description="Mobile phones with smart capabilities",
            exemplary_items=[
                Example(content="iPhone 15"),
                Example(content="Samsung Galaxy S24"),
            ],
            items=[
                ItemUnderNode(item_id="item1", confidence_score=0.95),
                ItemUnderNode(item_id="item3", confidence_score=0.9),
            ],
        ),
        NodeInDB(
            node_id="node3",
            taxonomy_id=str(test_taxonomy.id),
            user_id=str(test_user.id),
            parent_node_id="node1",
            label="Laptops",
            description="Portable computers",
            exemplary_items=[
                Example(content="MacBook Pro"),
                Example(content="Dell XPS"),
            ],
            items=[
                ItemUnderNode(item_id="item2", confidence_score=0.9),
            ],
        ),
    ]

    # Insert nodes
    node_docs = []
    for node in nodes:
        result = await mock_db.nodes.insert_one(node.model_dump(by_alias=True))
        node_docs.append(await mock_db.nodes.find_one({"_id": result.inserted_id}))

    return [NodeInDB(**doc) for doc in node_docs]


@pytest.fixture
async def test_items(
    mock_db: AsyncIOMotorDatabase, test_user: UserInDB
) -> list[ItemState]:
    """Create test items for classification."""
    items = [
        ItemState(
            id="item1",
            content="iPhone 15 Pro Max 256GB",
            classified_as=[],
        ),
        ItemState(
            id="item2",
            content="MacBook Pro 16-inch M3",
            classified_as=[NodeAndConfidence(node_id="node3", confidence_score=0.9)],
        ),
        ItemState(
            id="item3",
            content="Samsung Galaxy S24 Ultra",
            classified_as=[],
        ),
        ItemState(
            id="item4",
            content="Gaming headset with RGB lighting",
            classified_as=[],
        ),
    ]

    collection_name = f"items_{str(test_user.id)}"
    for item in items:
        await mock_db[collection_name].insert_one(item.model_dump())

    return items


@pytest.fixture
def mock_google_oauth(mocker):
    """Mock Google OAuth responses."""
    # Mock the OAuth client
    mock_client = mocker.patch("app.api.v1.endpoints.auth.oauth.create_client")
    mock_authorize = mocker.AsyncMock()
    mock_authorize.headers = {
        "Location": "https://accounts.google.com/oauth/authorize?..."
    }
    mock_client.return_value.authorize_redirect = mocker.AsyncMock(
        return_value=mock_authorize
    )

    # Mock token exchange
    mock_token = {
        "access_token": "google-access-token",
        "userinfo": {
            "id": "google-123",
            "email": "test@example.com",
            "name": "Test User",
            "picture": "https://example.com/picture.jpg",
        },
    }
    mock_client.return_value.authorize_access_token = mocker.AsyncMock(
        return_value=mock_token
    )

    return mock_client


@pytest.fixture
def mock_classifier_service(mocker):
    """Mock the classifier service for background tasks."""
    mock_service = mocker.patch("app.api.v1.endpoints.classification.ClassifierService")
    mock_instance = mocker.Mock()
    mock_service.return_value = mock_instance

    # Mock methods
    mock_instance.classify_batch = mocker.AsyncMock()
    mock_instance.examine_nodes = mocker.AsyncMock()

    return mock_instance


# Utility functions for testing
def create_test_jwt(user_id: str, expired: bool = False) -> str:
    """Create a test JWT token."""
    if expired:
        expire = datetime.utcnow() - timedelta(minutes=30)
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)

    data = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def assert_datetime_recent(dt: datetime, seconds: int = 5) -> bool:
    """Assert that a datetime is recent (within the last N seconds)."""
    now = datetime.utcnow()
    diff = abs((now - dt).total_seconds())
    return diff < seconds
