"""
Tests for nodes endpoints.
"""

import pytest
from httpx import AsyncClient
from bson import ObjectId
from app.models.user import UserInDB
from app.models.taxonomy import TaxonomyInDB
from app.models.node import NodeInDB


@pytest.mark.unit
class TestNodesEndpoints:
    """Test nodes endpoints."""

    async def test_list_nodes(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        auth_headers: dict,
    ):
        """Test listing nodes for a taxonomy."""
        response = await client.get(
            f"/api/v1/nodes/?taxonomy_id={test_taxonomy.id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "count" in data
        assert data["count"] == len(test_nodes)
        assert len(data["nodes"]) == len(test_nodes)

        # Verify node structure
        node = data["nodes"][0]
        assert "id" in node
        assert "node_id" in node
        assert "label" in node
        assert "description" in node
        assert "parent_node_id" in node

    async def test_list_nodes_no_taxonomy_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing nodes without taxonomy_id."""
        response = await client.get("/api/v1/nodes/", headers=auth_headers)

        assert response.status_code == 422  # Validation error

    async def test_list_nodes_invalid_taxonomy_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test listing nodes with invalid taxonomy ID."""
        response = await client.get(
            "/api/v1/nodes/?taxonomy_id=invalid-id", headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid taxonomy ID" in response.json()["detail"]

    async def test_list_nodes_unauthorized_taxonomy(
        self, client: AsyncClient, test_user: UserInDB, mock_db
    ):
        """Test listing nodes for taxonomy not owned by user."""
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

        # Create taxonomy for other user
        other_taxonomy_id = str(ObjectId())
        await mock_db.taxonomies.insert_one(
            {
                "_id": ObjectId(other_taxonomy_id),
                "user_id": other_user_id,
                "name": "Other Taxonomy",
                "aspect": "other",
            }
        )

        # Try to access with test user's token
        from app.core.security import create_access_token

        test_token = create_access_token(subject=str(test_user.id))
        test_headers = {"Authorization": f"Bearer {test_token}"}

        response = await client.get(
            f"/api/v1/nodes/?taxonomy_id={other_taxonomy_id}", headers=test_headers
        )

        assert response.status_code == 404
        assert "Taxonomy not found" in response.json()["detail"]

    async def test_get_node(
        self, client: AsyncClient, test_nodes: list[NodeInDB], auth_headers: dict
    ):
        """Test getting a specific node."""
        node_id = str(test_nodes[0].id)
        response = await client.get(f"/api/v1/nodes/{node_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "node" in data
        node = data["node"]
        assert node["id"] == node_id
        assert node["label"] == test_nodes[0].label
        assert node["description"] == test_nodes[0].description

    async def test_get_node_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test getting non-existent node."""
        fake_id = str(ObjectId())
        response = await client.get(f"/api/v1/nodes/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert "Node not found" in response.json()["detail"]

    async def test_get_node_invalid_id(self, client: AsyncClient, auth_headers: dict):
        """Test getting node with invalid ID."""
        response = await client.get("/api/v1/nodes/invalid-id", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid node ID" in response.json()["detail"]

    async def test_update_node(
        self,
        client: AsyncClient,
        test_nodes: list[NodeInDB],
        auth_headers: dict,
        mock_db,
    ):
        """Test updating a node."""
        node_id = str(test_nodes[0].id)
        update_data = {
            "label": "Updated Electronics",
            "description": "Updated description for electronics",
        }

        response = await client.patch(
            f"/api/v1/nodes/{node_id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        node = data["node"]
        assert node["label"] == "Updated Electronics"
        assert node["description"] == "Updated description for electronics"

        # Verify in database
        db_node = await mock_db.nodes.find_one({"_id": test_nodes[0].id})
        assert db_node["label"] == "Updated Electronics"

    async def test_update_node_partial(
        self, client: AsyncClient, test_nodes: list[NodeInDB], auth_headers: dict
    ):
        """Test partial update of a node."""
        node_id = str(test_nodes[0].id)
        update_data = {"label": "Partially Updated"}

        response = await client.patch(
            f"/api/v1/nodes/{node_id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        node = data["node"]
        assert node["label"] == "Partially Updated"
        assert node["description"] == test_nodes[0].description  # Unchanged

    async def test_update_node_unauthorized(
        self,
        client: AsyncClient,
        test_nodes: list[NodeInDB],
        test_user: UserInDB,
        mock_db,
    ):
        """Test updating node not owned by user."""
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

        # Try to update test user's node
        node_id = str(test_nodes[0].id)
        update_data = {"label": "Unauthorized Update"}

        response = await client.patch(
            f"/api/v1/nodes/{node_id}", json=update_data, headers=other_headers
        )

        assert response.status_code == 404
        assert "Node not found" in response.json()["detail"]

    async def test_delete_node(
        self,
        client: AsyncClient,
        test_nodes: list[NodeInDB],
        auth_headers: dict,
        mock_db,
    ):
        """Test deleting a node."""
        node_id = str(test_nodes[2].id)  # Delete the leaf node (Laptops)

        response = await client.delete(f"/api/v1/nodes/{node_id}", headers=auth_headers)

        assert response.status_code == 204

        # Verify node is deleted
        db_node = await mock_db.nodes.find_one({"_id": test_nodes[2].id})
        assert db_node is None

    async def test_delete_node_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test deleting non-existent node."""
        fake_id = str(ObjectId())

        response = await client.delete(f"/api/v1/nodes/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert "Node not found" in response.json()["detail"]

    async def test_get_nodes_needing_examination(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        auth_headers: dict,
        mock_db,
    ):
        """Test getting nodes that need examination."""
        # Update one node to need examination
        await mock_db.nodes.update_one(
            {"_id": test_nodes[2].id}, {"$set": {"needs_examination": True}}
        )

        response = await client.get(
            f"/api/v1/nodes/needing-examination?taxonomy_id={test_taxonomy.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) >= 1

        # Verify the node that needs examination is in the list
        node_ids = [node["id"] for node in data["nodes"]]
        assert str(test_nodes[2].id) in node_ids
