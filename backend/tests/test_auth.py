"""
Tests for authentication endpoints.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from app.core.security import create_refresh_token
from tests.conftest import create_test_jwt


@pytest.mark.unit
class TestAuthEndpoints:
    """Test authentication endpoints."""

    async def test_google_login(self, client: AsyncClient, mock_google_oauth):
        """Test Google OAuth login URL generation."""
        response = await client.get("/api/v1/auth/google/login")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]

    async def test_google_callback_new_user(
        self, client: AsyncClient, mock_db, mock_google_oauth
    ):
        """Test Google OAuth callback for new user."""
        # Simulate callback with code
        response = await client.get("/api/v1/auth/google/callback?code=test-auth-code")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify user was created
        user = await mock_db.users.find_one({"email": "test@example.com"})
        assert user is not None
        assert user["google_id"] == "google-123"
        assert user["name"] == "Test User"

    async def test_google_callback_existing_user(
        self, client: AsyncClient, test_user, mock_db, mock_google_oauth
    ):
        """Test Google OAuth callback for existing user."""
        # Update mock to return existing user's data
        mock_google_oauth.return_value.authorize_access_token.return_value = {
            "access_token": "google-access-token",
            "userinfo": {
                "id": test_user.google_id,
                "email": test_user.email,
                "name": "Updated Name",
                "picture": "https://example.com/new-picture.jpg",
            },
        }

        response = await client.get("/api/v1/auth/google/callback?code=test-auth-code")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Verify user was updated
        user = await mock_db.users.find_one({"_id": test_user.id})
        assert user["name"] == "Updated Name"
        assert user["picture"] == "https://example.com/new-picture.jpg"

    async def test_google_callback_error(self, client: AsyncClient, mock_google_oauth):
        """Test Google OAuth callback error handling."""
        # Mock OAuth error
        mock_google_oauth.return_value.authorize_access_token.side_effect = Exception(
            "OAuth error"
        )

        response = await client.get("/api/v1/auth/google/callback?code=test-auth-code")

        assert response.status_code == 400
        assert "Failed to authenticate with Google" in response.json()["detail"]

    async def test_refresh_token_valid(self, client: AsyncClient, test_user, mock_db):
        """Test refreshing access token with valid refresh token."""
        refresh_token = create_refresh_token(subject=str(test_user.id))

        response = await client.post(
            "/api/v1/auth/refresh", params={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Test refreshing with invalid refresh token."""
        response = await client.post(
            "/api/v1/auth/refresh", params={"refresh_token": "invalid-token"}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    async def test_refresh_token_expired(self, client: AsyncClient, test_user):
        """Test refreshing with expired refresh token."""
        expired_token = create_test_jwt(str(test_user.id), expired=True)

        response = await client.post(
            "/api/v1/auth/refresh", params={"refresh_token": expired_token}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"

    async def test_refresh_token_user_not_found(self, client: AsyncClient, mock_db):
        """Test refreshing token for non-existent user."""
        # Create token for non-existent user
        refresh_token = create_refresh_token(subject="non-existent-user-id")

        response = await client.post(
            "/api/v1/auth/refresh", params={"refresh_token": refresh_token}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User not found or inactive"

    async def test_refresh_token_inactive_user(
        self, client: AsyncClient, test_user, mock_db
    ):
        """Test refreshing token for inactive user."""
        # Make user inactive
        await mock_db.users.update_one(
            {"_id": test_user.id}, {"$set": {"is_active": False}}
        )

        refresh_token = create_refresh_token(subject=str(test_user.id))

        response = await client.post(
            "/api/v1/auth/refresh", params={"refresh_token": refresh_token}
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User not found or inactive"
