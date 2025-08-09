"""
Tests for items endpoints.
"""

import pytest
from httpx import AsyncClient
from bson import ObjectId
from app.models.user import UserInDB
from agents.state import ItemState, NodeAndConfidence


@pytest.mark.unit
class TestItemsEndpoints:
    """Test items endpoints."""

    async def test_upload_items(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test uploading multiple items."""
        items_data = {
            "items": [
                {"content": "iPhone 14 Pro"},
                {"content": "Samsung Galaxy S23"},
                {"content": "Google Pixel 8"},
            ]
        }

        response = await client.post(
            "/api/v1/items/upload", json=items_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["items_uploaded"] == 3
        assert data["total_items"] == 3
        assert "Successfully uploaded 3 items" in data["message"]

        # Verify items in database
        collection_name = f"items_{str(test_user.id)}"
        count = await mock_db[collection_name].count_documents({})
        assert count == 3

    async def test_upload_items_empty(self, client: AsyncClient, auth_headers: dict):
        """Test uploading empty items list."""
        items_data = {"items": []}

        response = await client.post(
            "/api/v1/items/upload", json=items_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["items_uploaded"] == 0
        assert data["total_items"] == 0

    async def test_list_items(
        self, client: AsyncClient, test_items: list[ItemState], auth_headers: dict
    ):
        """Test listing user's items."""
        response = await client.get("/api/v1/items/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "unclassified_count" in data
        assert data["count"] == len(test_items)
        assert data["unclassified_count"] == 3  # Only item2 is classified

    async def test_list_items_unclassified_only(
        self, client: AsyncClient, test_items: list[ItemState], auth_headers: dict
    ):
        """Test listing only unclassified items."""
        response = await client.get(
            "/api/v1/items/?only_unclassified=true", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3  # item1, item3, item4 are unclassified

        # Verify all returned items are unclassified
        for item in data["items"]:
            assert len(item["classified_as"]) == 0

    async def test_list_items_pagination(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test pagination when listing items."""
        # Add more items
        collection_name = f"items_{str(test_user.id)}"
        for i in range(10):
            await mock_db[collection_name].insert_one(
                {
                    "id": f"test-item-{i}",
                    "content": f"Test Item {i}",
                    "classified_as": [],
                }
            )

        # Get first page
        response = await client.get(
            "/api/v1/items/?skip=0&limit=5", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["count"] == 14  # 4 test items + 10 new ones

    async def test_get_item(
        self, client: AsyncClient, test_items: list[ItemState], auth_headers: dict
    ):
        """Test getting a specific item."""
        item_id = test_items[0].id
        response = await client.get(f"/api/v1/items/{item_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "item" in data
        item = data["item"]
        assert item["id"] == item_id
        assert item["content"] == test_items[0].content

    async def test_get_item_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test getting non-existent item."""
        response = await client.get(
            "/api/v1/items/non-existent-id", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_delete_item(
        self,
        client: AsyncClient,
        test_items: list[ItemState],
        test_user: UserInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test deleting an item."""
        item_id = test_items[0].id
        response = await client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify item is deleted
        collection_name = f"items_{str(test_user.id)}"
        item = await mock_db[collection_name].find_one({"id": item_id})
        assert item is None

    async def test_delete_item_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test deleting non-existent item."""
        response = await client.delete(
            "/api/v1/items/non-existent-id", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_delete_all_items(
        self,
        client: AsyncClient,
        test_items: list[ItemState],
        test_user: UserInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test deleting all items."""
        response = await client.delete("/api/v1/items/", headers=auth_headers)

        assert response.status_code == 204

        # Verify all items are deleted
        collection_name = f"items_{str(test_user.id)}"
        count = await mock_db[collection_name].count_documents({})
        assert count == 0

    async def test_get_unclassified_batch(
        self, client: AsyncClient, test_items: list[ItemState], auth_headers: dict
    ):
        """Test getting a batch of unclassified items."""
        response = await client.get("/api/v1/items/batch/2", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["unclassified_count"] == 3

        # Verify all returned items are unclassified
        for item in data["items"]:
            assert len(item["classified_as"]) == 0

    async def test_get_unclassified_batch_invalid_size(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting batch with invalid size."""
        # Test batch size too small
        response = await client.get("/api/v1/items/batch/0", headers=auth_headers)
        assert response.status_code == 400
        assert "between 1 and 100" in response.json()["detail"]

        # Test batch size too large
        response = await client.get("/api/v1/items/batch/101", headers=auth_headers)
        assert response.status_code == 400
        assert "between 1 and 100" in response.json()["detail"]

    async def test_items_isolation_between_users(
        self,
        client: AsyncClient,
        test_items: list[ItemState],
        test_user: UserInDB,
        mock_db,
    ):
        """Test that items are isolated between users."""
        # Create another user
        other_user = UserInDB(
            email="other@example.com",
            name="Other User",
            google_id="google-other",
            is_active=True,
            is_superuser=False,
        )
        result = await mock_db.users.insert_one(other_user.model_dump(by_alias=True))
        other_user_id = str(result.inserted_id)

        # Create headers for other user
        from app.core.security import create_access_token

        other_token = create_access_token(subject=other_user_id)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # List items as other user
        response = await client.get("/api/v1/items/", headers=other_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0  # Other user should have no items
        assert data["unclassified_count"] == 0
