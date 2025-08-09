"""
Tests for taxonomy endpoints.
"""

import pytest
from httpx import AsyncClient
from bson import ObjectId
from app.models.user import UserInDB
from app.models.taxonomy import TaxonomyInDB


@pytest.mark.unit
class TestTaxonomyEndpoints:
    """Test taxonomy endpoints."""

    async def test_create_taxonomy(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test creating a new taxonomy."""
        taxonomy_data = {"name": "Product Categories", "aspect": "type"}

        response = await client.post(
            "/api/v1/taxonomies/", json=taxonomy_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert "taxonomy" in data
        taxonomy = data["taxonomy"]
        assert taxonomy["name"] == "Product Categories"
        assert taxonomy["aspect"] == "type"
        assert taxonomy["user_id"] == str(test_user.id)
        assert "id" in taxonomy
        assert "created_at" in taxonomy
        assert "updated_at" in taxonomy

        # Verify in database
        db_taxonomy = await mock_db.taxonomies.find_one(
            {"_id": ObjectId(taxonomy["id"])}
        )
        assert db_taxonomy is not None
        assert db_taxonomy["name"] == "Product Categories"

    async def test_create_taxonomy_duplicate_name(
        self, client: AsyncClient, test_taxonomy: TaxonomyInDB, auth_headers: dict
    ):
        """Test creating taxonomy with duplicate name."""
        taxonomy_data = {
            "name": test_taxonomy.name,  # Same name as existing
            "aspect": "different_aspect",
        }

        response = await client.post(
            "/api/v1/taxonomies/", json=taxonomy_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_list_taxonomies(
        self,
        client: AsyncClient,
        test_user: UserInDB,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test listing user's taxonomies."""
        # Create additional taxonomies
        for i in range(3):
            await mock_db.taxonomies.insert_one(
                {
                    "user_id": str(test_user.id),
                    "name": f"Taxonomy {i}",
                    "aspect": f"aspect_{i}",
                    "created_at": test_taxonomy.created_at,
                    "updated_at": test_taxonomy.updated_at,
                }
            )

        response = await client.get("/api/v1/taxonomies/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "taxonomies" in data
        assert "count" in data
        assert data["count"] == 4  # test_taxonomy + 3 new ones
        assert len(data["taxonomies"]) == 4

    async def test_list_taxonomies_pagination(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test pagination when listing taxonomies."""
        # Create 10 taxonomies
        for i in range(10):
            await mock_db.taxonomies.insert_one(
                {
                    "user_id": str(test_user.id),
                    "name": f"Taxonomy {i}",
                    "aspect": f"aspect_{i}",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )

        # Get first page
        response = await client.get(
            "/api/v1/taxonomies/?skip=0&limit=5", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["taxonomies"]) == 5
        assert data["count"] == 10

        # Get second page
        response = await client.get(
            "/api/v1/taxonomies/?skip=5&limit=5", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["taxonomies"]) == 5

    async def test_get_taxonomy(
        self, client: AsyncClient, test_taxonomy: TaxonomyInDB, auth_headers: dict
    ):
        """Test getting a specific taxonomy."""
        response = await client.get(
            f"/api/v1/taxonomies/{test_taxonomy.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "taxonomy" in data
        taxonomy = data["taxonomy"]
        assert taxonomy["id"] == str(test_taxonomy.id)
        assert taxonomy["name"] == test_taxonomy.name
        assert taxonomy["aspect"] == test_taxonomy.aspect

    async def test_get_taxonomy_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting non-existent taxonomy."""
        fake_id = str(ObjectId())
        response = await client.get(
            f"/api/v1/taxonomies/{fake_id}", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_get_taxonomy_invalid_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting taxonomy with invalid ID."""
        response = await client.get(
            "/api/v1/taxonomies/invalid-id", headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid taxonomy ID" in response.json()["detail"]

    async def test_update_taxonomy(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test updating a taxonomy."""
        update_data = {"name": "Updated Name", "aspect": "updated_aspect"}

        response = await client.patch(
            f"/api/v1/taxonomies/{test_taxonomy.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        taxonomy = data["taxonomy"]
        assert taxonomy["name"] == "Updated Name"
        assert taxonomy["aspect"] == "updated_aspect"

        # Verify in database
        db_taxonomy = await mock_db.taxonomies.find_one({"_id": test_taxonomy.id})
        assert db_taxonomy["name"] == "Updated Name"
        assert db_taxonomy["aspect"] == "updated_aspect"

    async def test_update_taxonomy_duplicate_name(
        self,
        client: AsyncClient,
        test_user: UserInDB,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test updating taxonomy to duplicate name."""
        # Create another taxonomy
        other_taxonomy = await mock_db.taxonomies.insert_one(
            {
                "user_id": str(test_user.id),
                "name": "Other Taxonomy",
                "aspect": "other",
                "created_at": test_taxonomy.created_at,
                "updated_at": test_taxonomy.updated_at,
            }
        )

        update_data = {"name": "Other Taxonomy"}  # Try to use existing name

        response = await client.patch(
            f"/api/v1/taxonomies/{test_taxonomy.id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_delete_taxonomy(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list,
        auth_headers: dict,
        mock_db,
    ):
        """Test deleting a taxonomy and its associated data."""
        taxonomy_id = str(test_taxonomy.id)

        response = await client.delete(
            f"/api/v1/taxonomies/{taxonomy_id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify taxonomy is deleted
        db_taxonomy = await mock_db.taxonomies.find_one({"_id": test_taxonomy.id})
        assert db_taxonomy is None

        # Verify associated nodes are deleted
        nodes_count = await mock_db.nodes.count_documents({"taxonomy_id": taxonomy_id})
        assert nodes_count == 0

    async def test_delete_taxonomy_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test deleting non-existent taxonomy."""
        fake_id = str(ObjectId())

        response = await client.delete(
            f"/api/v1/taxonomies/{fake_id}", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_taxonomy_access_control(
        self, client: AsyncClient, test_taxonomy: TaxonomyInDB, mock_db
    ):
        """Test that users can only access their own taxonomies."""
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

        # Try to access test_taxonomy with other user's token
        response = await client.get(
            f"/api/v1/taxonomies/{test_taxonomy.id}", headers=other_headers
        )

        assert response.status_code == 404  # Should not find taxonomy


# Import datetime for the pagination test
from datetime import datetime
