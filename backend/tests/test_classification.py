"""
Tests for classification endpoints.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from app.models.user import UserInDB
from app.models.taxonomy import TaxonomyInDB
from app.models.node import NodeInDB
from agents.state import ItemState


@pytest.mark.unit
class TestClassificationEndpoints:
    """Test classification endpoints."""

    async def test_classify_batch(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        test_items: list[ItemState],
        auth_headers: dict,
        mock_classifier_service,
    ):
        """Test starting batch classification."""
        classification_data = {
            "taxonomy_id": str(test_taxonomy.id),
            "batch_size": 2,
            "models": ["gpt-4o-mini"],
            "majority_threshold": 0.5,
            "total_invocations": 10,
        }

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "running"
        assert data["items_remaining"] == 3  # 3 unclassified items
        assert "Classification started" in data["message"]

        # Verify classifier service was called
        mock_classifier_service.classify_batch.assert_called_once()
        call_args = mock_classifier_service.classify_batch.call_args
        assert call_args.kwargs["taxonomy_id"] == str(test_taxonomy.id)
        assert call_args.kwargs["batch_size"] == 2

    async def test_classify_batch_no_nodes(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test classification when taxonomy has no nodes."""
        # Create taxonomy without nodes
        taxonomy = TaxonomyInDB(
            user_id=str(test_user.id),
            name="Empty Taxonomy",
            aspect="test",
        )
        result = await mock_db.taxonomies.insert_one(taxonomy.model_dump(by_alias=True))
        taxonomy_id = str(result.inserted_id)

        classification_data = {"taxonomy_id": taxonomy_id, "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "No nodes found" in response.json()["detail"]

    async def test_classify_batch_no_unclassified_items(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        test_user: UserInDB,
        auth_headers: dict,
        mock_db,
    ):
        """Test classification when no unclassified items exist."""
        # Mark all items as classified
        collection_name = f"items_{str(test_user.id)}"
        await mock_db[collection_name].update_many(
            {},
            {
                "$set": {
                    "classified_as": [{"node_id": "node1", "confidence_score": 0.9}]
                }
            },
        )

        classification_data = {"taxonomy_id": str(test_taxonomy.id), "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "No unclassified items found" in response.json()["detail"]

    async def test_classify_batch_invalid_taxonomy(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test classification with non-existent taxonomy."""
        from bson import ObjectId

        fake_id = str(ObjectId())

        classification_data = {"taxonomy_id": fake_id, "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Taxonomy not found" in response.json()["detail"]

    async def test_examine_nodes(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        auth_headers: dict,
        mock_classifier_service,
    ):
        """Test starting node examination."""
        examination_data = {
            "taxonomy_id": str(test_taxonomy.id),
            "force_examine_node_ids": ["node2", "node3"],
        }

        response = await client.post(
            "/api/v1/classification/examine",
            json=examination_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "running"
        assert "Node examination started" in data["message"]

        # Verify classifier service was called
        mock_classifier_service.examine_nodes.assert_called_once()
        call_args = mock_classifier_service.examine_nodes.call_args
        assert call_args.kwargs["taxonomy_id"] == str(test_taxonomy.id)
        assert call_args.kwargs["force_node_ids"] == ["node2", "node3"]

    async def test_examine_nodes_no_nodes(
        self, client: AsyncClient, test_user: UserInDB, auth_headers: dict, mock_db
    ):
        """Test examination when taxonomy has no nodes."""
        # Create taxonomy without nodes
        taxonomy = TaxonomyInDB(
            user_id=str(test_user.id),
            name="Empty Taxonomy",
            aspect="test",
        )
        result = await mock_db.taxonomies.insert_one(taxonomy.model_dump(by_alias=True))
        taxonomy_id = str(result.inserted_id)

        examination_data = {"taxonomy_id": taxonomy_id}

        response = await client.post(
            "/api/v1/classification/examine",
            json=examination_data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "No nodes found" in response.json()["detail"]

    async def test_get_classification_status(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_items: list[ItemState],
        test_user: UserInDB,
        auth_headers: dict,
        mock_classifier_service,
    ):
        """Test getting classification session status."""
        # First start a classification
        classification_data = {"taxonomy_id": str(test_taxonomy.id), "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        session_id = response.json()["session_id"]

        # Get status
        response = await client.get(
            f"/api/v1/classification/status/{session_id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "running"
        assert "progress" in data
        progress = data["progress"]
        assert progress["total_items"] == 4
        assert progress["classified_items"] == 1
        assert progress["unclassified_items"] == 3

    async def test_get_classification_status_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test getting status for non-existent session."""
        response = await client.get(
            "/api/v1/classification/status/nonexistent",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"

    async def test_get_classifier_config(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
    ):
        """Test getting classifier configuration."""
        response = await client.get(
            f"/api/v1/classification/config/{str(test_taxonomy.id)}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check default values
        assert data["default_majority_threshold"] == 0.5
        assert data["default_batch_size"] == 10
        assert data["default_total_invocations"] == 20
        assert data["default_initial_batch_size"] == 50
        assert data["use_human_in_the_loop"] is False
        assert data["node_ids_not_to_examine"] == []
        assert data["examined_node_ids"] == []
        assert "gpt-4o-mini" in data["default_models"]

    async def test_update_classifier_config(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
    ):
        """Test updating classifier configuration."""
        update_data = {
            "default_batch_size": 20,
            "use_human_in_the_loop": True,
            "default_models": ["gpt-4o", "claude-3-5-sonnet-latest"],
        }

        response = await client.put(
            f"/api/v1/classification/config/{str(test_taxonomy.id)}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check updated values
        assert data["default_batch_size"] == 20
        assert data["use_human_in_the_loop"] is True
        assert data["default_models"] == ["gpt-4o", "claude-3-5-sonnet-latest"]

        # Check unchanged values remain default
        assert data["default_majority_threshold"] == 0.5
        assert data["default_total_invocations"] == 20

    async def test_update_classifier_config_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test updating config for non-existent taxonomy."""
        update_data = {"default_batch_size": 20}

        response = await client.put(
            "/api/v1/classification/config/nonexistent",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Taxonomy not found"

    async def test_get_classification_status_unauthorized(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_user: UserInDB,
        auth_headers: dict,
        mock_classifier_service,
        mock_db,
    ):
        """Test getting status for another user's session."""
        # Start classification
        classification_data = {"taxonomy_id": str(test_taxonomy.id), "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        session_id = response.json()["session_id"]

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

        # Try to get status with other user's token
        response = await client.get(
            f"/api/v1/classification/status/{session_id}", headers=other_headers
        )

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]

    async def test_cancel_session(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        auth_headers: dict,
        mock_classifier_service,
    ):
        """Test canceling a classification session."""
        # Start classification
        classification_data = {"taxonomy_id": str(test_taxonomy.id), "batch_size": 10}

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        session_id = response.json()["session_id"]

        # Cancel session
        response = await client.delete(
            f"/api/v1/classification/session/{session_id}", headers=auth_headers
        )

        assert response.status_code == 204

    async def test_cancel_session_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test canceling non-existent session."""
        response = await client.delete(
            "/api/v1/classification/session/non-existent-session", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    async def test_classification_with_custom_models(
        self,
        client: AsyncClient,
        test_taxonomy: TaxonomyInDB,
        test_nodes: list[NodeInDB],
        test_items: list[ItemState],
        auth_headers: dict,
        mock_classifier_service,
    ):
        """Test classification with custom model configuration."""
        classification_data = {
            "taxonomy_id": str(test_taxonomy.id),
            "batch_size": 5,
            "models": ["gpt-4o-mini", "claude-3-5-haiku"],
            "majority_threshold": 0.7,
            "total_invocations": 20,
        }

        response = await client.post(
            "/api/v1/classification/classify",
            json=classification_data,
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify custom parameters were passed
        call_args = mock_classifier_service.classify_batch.call_args
        assert call_args.kwargs["models"] == ["gpt-4o-mini", "claude-3-5-haiku"]
        assert call_args.kwargs["majority_threshold"] == 0.7
        assert call_args.kwargs["total_invocations"] == 20
