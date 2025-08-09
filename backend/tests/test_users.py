"""
Tests for user endpoints.
"""

import pytest
from httpx import AsyncClient
from app.models.user import UserInDB


@pytest.mark.unit
class TestUserEndpoints:
    """Test user endpoints."""

    async def test_get_current_user(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict
    ):
        """Test getting current user information."""
        response = await client.get("/api/v1/users/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        user_data = data["user"]
        assert user_data["id"] == str(test_user.id)
        assert user_data["email"] == test_user.email
        assert user_data["name"] == test_user.name
        assert user_data["picture"] == test_user.picture
        assert user_data["is_active"] == test_user.is_active
        assert user_data["is_superuser"] == test_user.is_superuser

    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"

    async def test_update_current_user(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test updating current user information."""
        update_data = {
            "name": "Updated Name",
            "picture": "https://example.com/new-picture.jpg",
        }

        response = await client.patch(
            "/api/v1/users/me", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        user_data = data["user"]
        assert user_data["name"] == "Updated Name"
        assert user_data["picture"] == "https://example.com/new-picture.jpg"

        # Verify database was updated
        db_user = await mock_db.users.find_one({"_id": test_user.id})
        assert db_user["name"] == "Updated Name"
        assert db_user["picture"] == "https://example.com/new-picture.jpg"

    async def test_update_current_user_partial(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test partial update of current user."""
        update_data = {"name": "Partial Update"}

        response = await client.patch(
            "/api/v1/users/me", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        user_data = data["user"]
        assert user_data["name"] == "Partial Update"
        assert user_data["picture"] == test_user.picture  # Should remain unchanged

    async def test_update_current_user_empty(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict
    ):
        """Test updating user with empty data."""
        response = await client.patch("/api/v1/users/me", json={}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        user_data = data["user"]
        # All fields should remain unchanged
        assert user_data["name"] == test_user.name
        assert user_data["picture"] == test_user.picture

    async def test_update_current_user_unauthorized(self, client: AsyncClient):
        """Test updating user without authentication."""
        update_data = {"name": "Unauthorized Update"}

        response = await client.patch("/api/v1/users/me", json=update_data)

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_superuser_access(
        self, client: AsyncClient, superuser: UserInDB, superuser_headers: dict
    ):
        """Test superuser can access their own information."""
        response = await client.get("/api/v1/users/me", headers=superuser_headers)

        assert response.status_code == 200
        data = response.json()
        user_data = data["user"]
        assert user_data["is_superuser"] is True
        assert user_data["email"] == superuser.email
