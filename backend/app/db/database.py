from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from motor.core import AgnosticDatabase

from app.core.config import settings


class Database:
    client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AgnosticDatabase] = None

    @property
    def db(self) -> AgnosticDatabase:
        if self._db is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        return self._db


db = Database()


async def init_db():
    """Initialize database connection"""
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db._db = db.client[settings.MONGODB_DB_NAME]

    # Create indexes
    await create_indexes()

    print("Connected to MongoDB")


async def close_db():
    """Close database connection"""
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB")


async def create_indexes():
    """Create necessary indexes for optimal performance"""
    database = db.db

    # User indexes
    await database.users.create_index("email", unique=True)
    await database.users.create_index("google_id", unique=True, sparse=True)

    # Taxonomy indexes
    await database.taxonomies.create_index("user_id")
    await database.taxonomies.create_index([("user_id", 1), ("name", 1)], unique=True)

    # Note: Node indexes are created per taxonomy collection, not here
    # Each nodes_{taxonomy_id} collection will have its own indexes

    print("Database indexes created")


def get_db() -> AgnosticDatabase:
    """Get database instance"""
    return db.db


def get_user_items_collection(user_id: str):
    """Get the items collection for a specific user"""
    return db.db[f"items_{user_id}"]


def get_taxonomy_nodes_collection(taxonomy_id: str):
    """Get the nodes collection for a specific taxonomy"""
    return db.db[f"nodes_{taxonomy_id}"]


# Not used at the moment because we need to pull all nodes every time and there are not that many nodes.
async def create_taxonomy_nodes_indexes(taxonomy_id: str):
    """Create indexes for a taxonomy-specific nodes collection"""
    nodes_collection = get_taxonomy_nodes_collection(taxonomy_id)

    # Create indexes
    await nodes_collection.create_index("node_id", unique=True)
    await nodes_collection.create_index("parent_node_id")

    print(f"Indexes created for nodes_{taxonomy_id}")
