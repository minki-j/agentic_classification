"""
MongoDB serialization utilities for handling complex Pydantic models.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from bson import ObjectId
from pydantic import BaseModel
from agents.state import NodeAndConfidence, ItemState, ClassNodeState
from app.models.item import ItemInDB, ClassifiedAs
from app.schemas.item import ItemResponse
from app.schemas.taxonomy import TaxonomyResponse
from app.models.node import NodeInDB
from app.schemas.node import NodeCreate
from app.models.taxonomy import TaxonomyInDB

T = TypeVar("T", bound=BaseModel)


class MongoSerializer:
    """
    DB(objectId _id)        ->   serialize     ->   state/response(str id)
    state/request(str id)   ->   deserialize   ->   DB(objectId _id)

    DB(contains classification results for all taxonomies) -> serialize -> response(contains classification results for current taxonomy)
    """

    # -----------------------------
    # Helper methods
    # -----------------------------

    @staticmethod
    def serialize_id(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize the ObjectId to a string."""
        if "_id" in obj and obj["_id"] and isinstance(obj["_id"], ObjectId):
            obj["id"] = str(obj["_id"])
            del obj["_id"]
        return obj

    # -----------------------------
    # Item
    # -----------------------------

    @staticmethod
    def serialize_item_to_response(
        item: ItemInDB, taxonomy_id: Optional[str] = None
    ) -> ItemResponse:
        """Convert a MongoDB document to an ItemResponse that is ready to be sent to the frontend."""
        item_dict = item.model_dump(by_alias=False, context={"keep_objectid": False})

        # If taxonomy_id is not provided, remove the 'classified_as' field so that ItemResponse uses its default value.
        if not taxonomy_id:
            del item_dict["classified_as"]
            return ItemResponse(**item_dict)

        if taxonomy_id in item_dict["classified_as"]:
            item_dict["classified_as"] = [
                ClassifiedAs(**ca)
                for ca in item_dict["classified_as"].get(taxonomy_id, [])
            ]
        else:
            item_dict["classified_as"] = []

        return ItemResponse(**item_dict)

    @staticmethod
    def serialize_item_to_state(item_doc: ItemInDB, taxonomy_id: str) -> ItemState:
        """Convert a MongoDB document to an ItemState."""
        item_dict = item_doc.model_dump(
            by_alias=False, context={"keep_objectid": False}
        )

        if taxonomy_id in item_dict["classified_as"]:
            item_dict["classified_as"] = [
                NodeAndConfidence(**ca)
                for ca in item_dict["classified_as"].get(taxonomy_id, [])
            ]
        else:
            item_dict["classified_as"] = []

        return ItemState(**item_dict)

    @staticmethod
    def deserialize_item_from_state(
        item: ItemState, taxonomy_id: str
    ) -> Dict[str, Any]:
        """Convert an Item instance to a MongoDB-compatible dictionary."""
        item_dict = item.model_dump()

        # Convert NodeAndConfidence objects to dictionaries
        new_classified_as = {}
        new_classified_as[taxonomy_id] = [
            ClassifiedAs(**nc.model_dump()).model_dump()
            for nc in (item.classified_as or [])
        ]
        item_dict["classified_as"] = new_classified_as

        return item_dict

    # -----------------------------
    # Node
    # -----------------------------

    @staticmethod
    def serialize_node_to_state(node: NodeInDB) -> ClassNodeState:
        """Convert a MongoDB document to a ClassNodeState."""
        node_dict = node.model_dump(by_alias=False, context={"keep_objectid": False})
        return ClassNodeState(**node_dict)

    @staticmethod
    def deserialize_node_from_state(node: ClassNodeState) -> Dict[str, Any]:
        """Convert a ClassNodeState to a MongoDB-compatible dictionary."""
        node = NodeInDB(**node.model_dump())

        return node.model_dump(by_alias=True, context={"keep_objectid": True})

    @staticmethod
    def deserialize_node_from_request(node: NodeCreate) -> Dict[str, Any]:
        """Convert a ClassNodeState to a MongoDB-compatible dictionary."""
        node_dict = node.model_dump(by_alias=True, context={"keep_objectid": True})
        node_in_db = NodeInDB(**node_dict)

        return node_in_db.model_dump(by_alias=True, context={"keep_objectid": True})

    # -----------------------------
    # Taxonomy
    # -----------------------------

    @staticmethod
    def serialize_taxonomy_to_response(
        taxonomy: TaxonomyInDB,
    ) -> TaxonomyResponse:
        """Convert a MongoDB document to a TaxonomyResponse that is ready to be sent to the frontend."""

        return TaxonomyResponse(
            **taxonomy.model_dump(by_alias=False, context={"keep_objectid": False})
        )
