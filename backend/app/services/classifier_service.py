import logging
import traceback
from enum import Enum
from datetime import datetime
from typing import List, Optional, Union, overload, Literal

from motor.core import AgnosticDatabase
from pymongo import UpdateOne
from bson import ObjectId

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

from agents.state import (
    ItemState,
    ClassNodeState,
    Taxonomy,
    InterruptType,
    ItemUnderNode,
)
from agents.llm_factory import OpenAIModel, AnthropicModel, AIModel, string_to_ai_model

from agents.classify_items.classify_items_graph import (
    g as classify_g,
    ClassifyItemsOverallState,
)
from agents.create_initial_nodes.create_initial_nodes_graph import (
    g as initial_batch_g,
    CreateInitialNodesState,
)
from agents.examine_nodes.examine_nodes_graph import (
    g as examine_nodes_g,
    ExamineNodesState,
)

from app.models.node import NodeInDB
from app.models.item import ItemInDB
from app.websocket.manager import ConnectionManager
from app.db.serializers import MongoSerializer
from app.models.taxonomy import ClassifierState

logger = logging.getLogger(__name__)

# Constants
EXAMINE_THRESHOLD_SCORE = 0.6  # If the average confidence score of items classified to a node is less than this score, we examine the node.
MIN_ITEMS_TO_EXAMINE = 10  # If the number of items classified to a node is less than this number, we skip the node.


class Status(Enum):
    COMPLETED = "completed"
    HUMAN_FEEDBACK = "human_feedback"
    NODE_EXAMINATION = "node_examination"
    ERROR = "error"


class SnapshotKey(Enum):
    # Classify items graph
    NODES = "nodes"
    ITEMS = "items"

    # Examine nodes graph
    NEW_CHILD_NODES = "new_child_nodes"
    UPDATED_ITEMS = "updated_items"


class ClassifierService:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        taxonomy_id: str,
        user_id: str,
        db: Optional[AgnosticDatabase] = None,
    ):
        self.connection_manager = connection_manager
        self.taxonomy_id = taxonomy_id
        self.user_id = user_id
        self.db = db
        self.config_for_classify_items_graph = RunnableConfig(
            {
                "configurable": {"thread_id": taxonomy_id},
                "recursion_limit": 1000,
            }
        )
        self.config_for_examine_nodes_graph = RunnableConfig(
            {
                "configurable": {
                    "thread_id": f"{taxonomy_id}_{datetime.now().strftime('%m%d_%H%M%S')}"
                },
                "recursion_limit": 1000,
            }
        )  # examine node state is not persisted, so we need to update the config for each new examination

        # Default state variables
        self.majority_threshold = 0.5
        self.batch_size = 4
        self.total_invocations = 8
        self.initial_batch_size = 50
        self.use_human_in_the_loop = False
        self.node_ids_not_to_examine = []
        self.examined_node_ids = []
        self.models = [OpenAIModel.GPT_4O_MINI]

    @classmethod
    async def create(
        cls,
        connection_manager: ConnectionManager,
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
    ) -> "ClassifierService":
        """Factory method to create a ClassifierService instance with state loaded from DB"""
        instance = cls(connection_manager, taxonomy_id, user_id, db)
        await instance.load_state_from_db()
        return instance

    async def load_state_from_db(self):
        """Load classifier state from taxonomy document in database"""
        if self.db is None:
            return

        try:
            from bson import ObjectId

            taxonomy_doc = await self.db.taxonomies.find_one(
                {"_id": ObjectId(self.taxonomy_id)}
            )

            if taxonomy_doc and taxonomy_doc.get("classifier_state"):
                state_dict = taxonomy_doc["classifier_state"]
                state = ClassifierState(**state_dict)

                # Apply loaded state
                self.majority_threshold = state.majority_threshold
                self.batch_size = state.batch_size
                self.total_invocations = state.total_invocations
                self.initial_batch_size = state.initial_batch_size
                self.use_human_in_the_loop = state.use_human_in_the_loop
                self.node_ids_not_to_examine = state.node_ids_not_to_examine
                self.examined_node_ids = state.examined_node_ids

                # Convert model strings back to enum objects
                self.models = []
                for model_str in state.models:
                    try:
                        model = string_to_ai_model(model_str)
                        self.models.append(model)
                    except ValueError:
                        logger.warning(f"Unknown model in saved state: {model_str}")

                logger.info(f"Loaded classifier state for taxonomy {self.taxonomy_id}")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error loading classifier state from DB: {e}")

    async def save_state_to_db(self):
        """Save current classifier state to taxonomy document in database"""
        if self.db is None:
            return

        try:
            from bson import ObjectId

            # Convert models to strings for storage
            model_strings = [model.value for model in self.models]

            state = ClassifierState(
                majority_threshold=self.majority_threshold,
                batch_size=self.batch_size,
                total_invocations=self.total_invocations,
                initial_batch_size=self.initial_batch_size,
                use_human_in_the_loop=self.use_human_in_the_loop,
                node_ids_not_to_examine=self.node_ids_not_to_examine,
                examined_node_ids=self.examined_node_ids,
                models=model_strings,
            )

            await self.db.taxonomies.update_one(
                {"_id": ObjectId(self.taxonomy_id)},
                {
                    "$set": {
                        "classifier_state": state.model_dump(),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(f"Saved classifier state for taxonomy {self.taxonomy_id}")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error saving classifier state to DB: {e}")

    # =======================================================
    #                   Utility Functions
    # =======================================================

    @overload
    def get_snapshot_value(
        self,
        graph: CompiledStateGraph,
        key: Literal[SnapshotKey.NODES, SnapshotKey.NEW_CHILD_NODES],
        config: Optional[RunnableConfig] = None,
    ) -> list[ClassNodeState]: ...

    @overload
    def get_snapshot_value(
        self,
        graph: CompiledStateGraph,
        key: Literal[SnapshotKey.ITEMS, SnapshotKey.UPDATED_ITEMS],
        config: Optional[RunnableConfig] = None,
    ) -> list[ItemState]: ...

    def get_snapshot_value(
        self,
        graph: CompiledStateGraph,
        key: SnapshotKey,
        config: Optional[RunnableConfig] = None,
    ) -> Union[list[ClassNodeState], list[ItemState]]:
        use_config = config or self.config_for_classify_items_graph
        if use_config is None:
            raise ValueError("No config available. Initialize config first.")
        state = graph.get_state_history(use_config)
        latest_snapshot = next(state)
        return latest_snapshot.values.get(key.value, None)

    def _reached_end_of_classify_graph(self, graph: CompiledStateGraph) -> bool:
        if self.config_for_classify_items_graph is None:
            raise ValueError("Config not initialized. Call _initialize_config first.")
        state = graph.get_state_history(self.config_for_classify_items_graph)
        latest_snapshot = next(state)

        if len(latest_snapshot.interrupts) == 0:
            raise ValueError(f"Snapshot has no interrupts: {latest_snapshot}")

        return latest_snapshot.interrupts[0].value.get(
            InterruptType.NEXT_BATCH.value, False
        )

    def _reached_end_of_examine_nodes_graph(self, graph: CompiledStateGraph) -> bool:
        """Check if the graph is not interrupted"""
        if self.config_for_examine_nodes_graph is None:
            raise ValueError("Examine nodes config not initialized.")
        state = graph.get_state_history(self.config_for_examine_nodes_graph)
        latest_snapshot = next(state)

        return len(latest_snapshot.interrupts) == 0

    async def get_nodes_to_examine(
        self,
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
        force_node_ids: Optional[List[str]] = None,
    ) -> List[ClassNodeState]:
        """
        When items are classified to nodes, we need to check if there needs to be more branches to be created.
        Fetches nodes from database and evaluates them for examination.
        """
        # Get nodes from database
        nodes_collection = db[f"nodes_{taxonomy_id}"]
        nodes_cursor = nodes_collection.find({})
        nodes_docs = await nodes_cursor.to_list(length=None)

        # Convert to ClassNode objects
        nodes = []
        for node_doc in nodes_docs:
            node = ClassNodeState(
                id=node_doc["node_id"],
                parent_node_id=node_doc["parent_node_id"],
                label=node_doc["label"],
                description=node_doc["description"],
                items=node_doc.get("items", []),
            )
            nodes.append(node)

        # If force_node_ids is provided, return only those nodes
        if force_node_ids:
            return [n for n in nodes if n.id in force_node_ids]

        # Otherwise, evaluate nodes for examination
        nodes_to_examine = []

        for node in nodes:
            if node.id in self.node_ids_not_to_examine:
                continue
            if node.id in self.examined_node_ids:
                continue

            if not node.items:
                continue
            if len(node.items) < MIN_ITEMS_TO_EXAMINE:
                continue

            average_confidence_score = sum(
                item.confidence_score for item in node.items
            ) / len(node.items)

            if average_confidence_score <= EXAMINE_THRESHOLD_SCORE:
                nodes_to_examine.append(node)

        return nodes_to_examine

    async def _update_nodes_and_items_after_classification(
        self, taxonomy_id: str, db: AgnosticDatabase
    ):
        """Update nodes in database after classification without maintaining in-memory state"""
        classified_items = self.get_snapshot_value(classify_g, SnapshotKey.ITEMS)
        nodes_from_snapshot = self.get_snapshot_value(classify_g, SnapshotKey.NODES)
        items_collection = db[f"items_{self.user_id}"]
        nodes_collection = db[f"nodes_{taxonomy_id}"]

        if classified_items:
            # Bulk update items in database
            item_updates = []
            for item in classified_items:
                item_updates.append(
                    UpdateOne(
                        {"_id": ObjectId(item.id)},
                        {
                            "$set": MongoSerializer.deserialize_item_from_state(
                                item, taxonomy_id
                            )
                        },
                    )
                )
            await items_collection.bulk_write(item_updates)

            # Bulk update nodes in database
            node_to_items_dict = {}
            for item in classified_items:
                if item.classified_as:
                    for node_and_confidence in item.classified_as:
                        if node_and_confidence.node_id not in node_to_items_dict:
                            node_to_items_dict[node_and_confidence.node_id] = []
                        node_to_items_dict[node_and_confidence.node_id].append(
                            ItemUnderNode(
                                item_id=item.id,
                                confidence_score=node_and_confidence.confidence_score,
                            ).model_dump()
                        )

            if node_to_items_dict:
                node_updates = []
                for node_id, items in node_to_items_dict.items():
                    node_updates.append(
                        UpdateOne(
                            {"_id": ObjectId(node_id)},
                            {
                                "$push": {"items": {"$each": items}},
                                "$set": {"updated_at": datetime.utcnow()},
                            },
                        )
                    )
                await nodes_collection.bulk_write(node_updates)

        # Check for new nodes and insert them
        if nodes_from_snapshot:
            existing_nodes_cursor = nodes_collection.find({})
            existing_nodes_docs = await existing_nodes_cursor.to_list(length=None)
            existing_node_ids = [str(doc["_id"]) for doc in existing_nodes_docs]

            for node_from_snapshot in nodes_from_snapshot:
                if node_from_snapshot.id not in existing_node_ids:
                    # Insert new node
                    node = MongoSerializer.deserialize_node_from_state(
                        node_from_snapshot
                    )
                    await nodes_collection.insert_one(node)

    async def _update_nodes_after_examination(
        self, taxonomy_id: str, user_id: str, db: AgnosticDatabase
    ):
        """Update nodes in database after examination"""
        new_child_nodes = self.get_snapshot_value(
            examine_nodes_g,
            SnapshotKey.NEW_CHILD_NODES,
            self.config_for_examine_nodes_graph,
        )

        if not new_child_nodes:
            return

        nodes_collection = db[f"nodes_{taxonomy_id}"]

        # Check if new child nodes already exist
        new_child_node_ids = [node.id for node in new_child_nodes]
        existing_cursor = nodes_collection.find(
            {"node_id": {"$in": new_child_node_ids}}
        )
        existing_docs = await existing_cursor.to_list(length=None)

        if existing_docs:
            existing_ids = [doc["node_id"] for doc in existing_docs]
            raise ValueError(
                f"New child nodes already exist in the database: {existing_ids}. This is not allowed."
            )

        # Insert new child nodes
        for node in new_child_nodes:
            if node.id is None or node.id == "":
                raise ValueError(f"Node id is None or empty: {node}")

            node_db = NodeInDB(
                _id=ObjectId(node.id),
                parent_node_id=node.parent_node_id,
                label=node.label,
                description=node.description,
                items=node.items or [],
            )
            await nodes_collection.insert_one(node_db.model_dump(by_alias=True))

        # Update classify graph with new nodes
        if self.config_for_classify_items_graph:
            classify_g.update_state(
                self.config_for_classify_items_graph,
                {"nodes": new_child_nodes},
            )
        else:
            logger.warning("Config not initialized, skipping classify graph update")

        # Update items with new classifications
        updated_items = self.get_snapshot_value(
            examine_nodes_g,
            SnapshotKey.UPDATED_ITEMS,
            self.config_for_examine_nodes_graph,
        )

        for item in updated_items:
            if not item.classified_as:
                continue
            for node_and_confidence in item.classified_as:
                # Get current node from DB
                node_doc = await nodes_collection.find_one(
                    {"node_id": node_and_confidence.node_id}
                )

                if node_doc:
                    items_list = node_doc.get("items", [])
                    item_entry = ItemUnderNode(
                        item_id=item.id,
                        confidence_score=node_and_confidence.confidence_score,
                    )
                    if not any(i["item_id"] == item.id for i in items_list):
                        items_list.append(item_entry.model_dump())
                        await nodes_collection.update_one(
                            {
                                "node_id": node_and_confidence.node_id,
                            },
                            {
                                "$set": {
                                    "items": items_list,
                                    "updated_at": datetime.utcnow(),
                                }
                            },
                        )

    async def _update_and_return_for_examine_nodes_graph(
        self,
        nodes_to_examine: List[ClassNodeState],
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
    ) -> tuple[Status, List[ItemState]]:
        """Update after examination and return results"""
        self.examined_node_ids.extend([node.id for node in nodes_to_examine])

        # Save updated state to DB
        await self.save_state_to_db()

        await self._update_nodes_after_examination(taxonomy_id, user_id, db)

        updated_items = self.get_snapshot_value(
            examine_nodes_g,
            SnapshotKey.UPDATED_ITEMS,
            self.config_for_examine_nodes_graph,
        )

        # update config for examine nodes graph
        self._update_config_for_examine_nodes_graph()

        return Status.COMPLETED, updated_items

    def _update_config_for_examine_nodes_graph(self):
        current_time = datetime.now().strftime("%m%d_%H%M%S")
        self.config_for_examine_nodes_graph = RunnableConfig(
            {
                "configurable": {"thread_id": f"{self.taxonomy_id}_{current_time}"},
                "recursion_limit": 1000,
            }
        )

    def _check_if_graph_is_initialized(self, graph: CompiledStateGraph) -> bool:
        state = graph.get_state_history(self.config_for_classify_items_graph)
        try:
            next(state)
            return True
        except StopIteration:
            return False

    async def _send_classification_update(self, display_type: str, data: dict):
        """Send update from langgraph to frontend"""
        await self.connection_manager.send_classification_update(
            self.user_id,
            {
                "display_type": display_type,
                **data,
            },
        )

    # =======================================================
    #                   Main Functions
    # =======================================================
    # These functions are run as a background task by FastAPI

    async def create_initial_nodes(
        self,
        taxonomy_id: str,
        taxonomy: Taxonomy,
        items: List[ItemState],
        llm_name: str,
        user_id: str,
        db: AgnosticDatabase,
    ):
        """Create initial nodes for a taxonomy"""
        try:
            # Check if nodes already exist
            nodes_collection = db[f"nodes_{taxonomy_id}"]
            existing_count = await nodes_collection.count_documents({})
            if existing_count > 0:
                logger.warning("Nodes already exist. Skipping initial nodes creation.")
                raise Exception(f"Nodes already exist for taxonomy {taxonomy_id}")

            if not items:
                raise Exception("No items provided")

            config = RunnableConfig(
                {
                    "configurable": {
                        "thread_id": f"{taxonomy_id}_{datetime.now().strftime('%m%d_%H%M%S')}"
                    },
                    "recursion_limit": 1000,
                }
            )
            async for chunk in initial_batch_g.astream(
                CreateInitialNodesState(
                    taxonomy=taxonomy,
                    user_id=user_id,
                    llm=string_to_ai_model(llm_name),
                    items=items,
                    nodes=[
                        ClassNodeState(
                            id="RESET",
                            parent_node_id="",
                            label="",
                            description="",
                        )
                    ],
                    use_human_in_the_loop=self.use_human_in_the_loop,
                ),
                config=config,
                stream_mode="custom",
            ):
                if "message" not in chunk:
                    raise ValueError(
                        f"message key not found... this is not supported format fron create_initial_nodes graph: {chunk}"
                    )
                await self.connection_manager.send_initialization_update(
                    self.user_id,
                    {"message": chunk["message"]},
                )

            # Get the created nodes from graph snapshot
            nodes = self.get_snapshot_value(initial_batch_g, SnapshotKey.NODES, config)

            # Save nodes to database
            for node in nodes:
                await nodes_collection.insert_one(
                    MongoSerializer.deserialize_node_from_state(node)
                )

            # Send completion message
            await self.connection_manager.send_initialization_update(
                self.user_id,
                {"completed": True},
            )

        except Exception as e:
            traceback.print_exc()
            await self.connection_manager.send_error_message(
                self.user_id,
                {"title": "Error", "detail": str(e)},
            )

    async def init_classify_graph(
        self,
        taxonomy: Taxonomy,
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
        models: Optional[List[AIModel]] = None,
        majority_threshold: Optional[float] = None,
        total_invocations: Optional[int] = None,
        batch_size: Optional[int] = None,
    ):
        """Initialize the classification graph with nodes from database"""
        # Get nodes from database
        nodes_collection = db[f"nodes_{taxonomy_id}"]
        nodes_cursor = nodes_collection.find({})
        nodes_docs = await nodes_cursor.to_list(length=None)
        nodes = [NodeInDB(**node_doc) for node_doc in nodes_docs]

        nodes = [MongoSerializer.serialize_node_to_state(node) for node in nodes]

        if not nodes:
            raise ValueError("No nodes found. Please create initial nodes first.")

        await classify_g.ainvoke(
            ClassifyItemsOverallState(
                taxonomy=taxonomy,
                user_id=user_id,
                batch_size=batch_size or self.batch_size,
                models=models or self.models,
                majority_threshold=majority_threshold or self.majority_threshold,
                total_invocations=total_invocations or self.total_invocations,
                use_human_in_the_loop=self.use_human_in_the_loop,
                nodes=nodes,
            ),
            self.config_for_classify_items_graph,
        )

        await self._send_classification_update(
            display_type="toast",
            data={
                "title": "Classification graph initialized",
            },
        )

    async def classify_batch(
        self,
        taxonomy_id: str,
        taxonomy: Taxonomy,
        batch_size: int,
        user_id: str,
        db: AgnosticDatabase,
        models: Optional[List[AIModel]] = None,
        majority_threshold: Optional[float] = None,
        total_invocations: Optional[int] = None,
    ):
        """Classify a batch of items"""
        try:
            # Initialize classify graph if needed
            if not self._check_if_graph_is_initialized(classify_g):
                await self.init_classify_graph(
                    taxonomy,
                    taxonomy_id,
                    user_id,
                    db,
                    models,
                    majority_threshold,
                    total_invocations,
                )

            # Get unclassified items (items not classified to any node in this taxonomy)
            user_items_collection = db[f"items_{user_id}"]
            cursor = user_items_collection.find(
                {f"classified_as.{taxonomy_id}": {"$exists": False}}
            ).limit(batch_size)
            items = await cursor.to_list(length=batch_size)
            items = [ItemInDB(**item) for item in items]
            items = [
                MongoSerializer.serialize_item_to_state(item, taxonomy_id)
                for item in items
            ]
            if not items:
                raise Exception("No items left to classify. Please add more items.")

            nodes_collection = db[f"nodes_{taxonomy_id}"]
            nodes_cursor = nodes_collection.find({})
            nodes_docs = await nodes_cursor.to_list(length=None)
            nodes = [NodeInDB(**node_doc) for node_doc in nodes_docs]
            nodes = [MongoSerializer.serialize_node_to_state(node) for node in nodes]

            classificication_config = {}
            if models:
                classificication_config["models"] = models
            if majority_threshold:
                classificication_config["majority_threshold"] = majority_threshold
            if total_invocations:
                classificication_config["total_invocations"] = total_invocations

            # Update graph with items and nodes to classify
            classify_g.update_state(
                self.config_for_classify_items_graph,
                {
                    "items": items + [ItemState(id="REPLACE_ALL", content="")],
                    "nodes": nodes
                    + [
                        ClassNodeState(
                            id="REPLACE_ALL",
                            parent_node_id="",
                            label="",
                            description="",
                        )
                    ],
                    **classificication_config,
                },
            )

            await self._send_classification_update(
                display_type="classify_items",
                data={"item_ids_to_classify": [item.id for item in items]},
            )

            # Run classification
            async for chunk in classify_g.astream(
                Command(resume=""),
                config=self.config_for_classify_items_graph,
                stream_mode="custom",
            ):
                if "update_data" not in chunk:
                    raise ValueError(f"update_data not found in chunk: {chunk}")

                await self._send_classification_update(
                    display_type="classify_items",
                    data=chunk["update_data"],
                )

            # Check if classification completed
            if self._reached_end_of_classify_graph(classify_g):
                await self._update_nodes_and_items_after_classification(taxonomy_id, db)
                await self._send_classification_update(
                    display_type="none",
                    data={
                        "classification_completed": True,
                    },
                )
            else:
                # Human feedback needed
                await self._send_classification_update(
                    display_type="toast",
                    data={
                        "title": "Human feedback required to continue classification",
                    },
                )

        except Exception as e:
            traceback.print_exc()
            await self.connection_manager.send_error_message(
                self.user_id,
                {"title": "Error", "detail": str(e)},
            )
            await self._send_classification_update(
                display_type="none",
                data={
                    "classification_failed": True,
                },
            )

    async def examine_nodes(
        self,
        taxonomy_id: str,
        taxonomy: Taxonomy,
        user_id: str,
        db: AgnosticDatabase,
        models: Optional[List[AIModel]] = None,
        force_node_ids: Optional[List[str]] = None,
    ):
        """Examine nodes that need improvement"""
        try:
            # Send start message
            await self._send_classification_update(
                display_type="toast",
                data={
                    "title": "Starting node examination...",
                },
            )

            # Get nodes to examine
            nodes_to_examine = await self.get_nodes_to_examine(
                taxonomy_id, user_id, db, force_node_ids
            )

            if not nodes_to_examine:
                raise Exception("No nodes need examination")

            # Get items for examination
            user_items_collection = db[f"items_{user_id}"]
            cursor = user_items_collection.find({})
            items = await cursor.to_list(length=None)
            items = [ItemInDB(**item) for item in items]
            items = [
                MongoSerializer.serialize_item_to_state(item, taxonomy_id)
                for item in items
            ]

            # Build node to items mapping
            node_to_examine_items_dict = {}
            for node in nodes_to_examine:
                node_to_examine_items_dict[node.id] = []
                for item in items:
                    if item.classified_as:
                        if node.id in [nc.node_id for nc in item.classified_as]:
                            node_to_examine_items_dict[node.id].append(item)

            # Validate that all nodes have items to examine
            for node_id, items in node_to_examine_items_dict.items():
                if not items:
                    raise ValueError(f"Node '{node_id}' has no items to examine.")

            # Send nodes being examined
            await self._send_classification_update(
                display_type="toast",
                data={
                    "title": f"Examining nodes: {', '.join([n.label for n in nodes_to_examine])}",
                },
            )

            # Examine nodes using graph
            async for chunk in examine_nodes_g.astream(
                ExamineNodesState(
                    models=models or self.models,
                    total_invocations=self.total_invocations,
                    majority_threshold=self.majority_threshold,
                    batch_size=self.batch_size,
                    use_human_in_the_loop=self.use_human_in_the_loop,
                    nodes_to_examine=nodes_to_examine,
                    node_to_examine_items_dict=node_to_examine_items_dict,
                    taxonomy=taxonomy,
                ),
                self.config_for_examine_nodes_graph,
                stream_mode="custom",
            ):
                if "update_data" not in chunk:
                    raise ValueError(f"update_data not found in chunk: {chunk}")

                await self._send_classification_update(
                    display_type="examine_nodes",
                    data=chunk["update_data"],
                )

            # Check if examination completed
            if self._reached_end_of_examine_nodes_graph(examine_nodes_g):
                status, result = await self._update_and_return_for_examine_nodes_graph(
                    nodes_to_examine, taxonomy_id, user_id, db
                )

                if status is not Status.COMPLETED:
                    raise ValueError(f"Examination failed with status: {status}")

                # Update items in database
                for item in result:
                    await user_items_collection.update_one(
                        {"_id": ObjectId(item.id)},
                        {
                            "$set": MongoSerializer.deserialize_item_from_state(
                                item, taxonomy_id
                            )
                        },
                    )

                # Send completion message
                await self._send_classification_update(
                    display_type="toast",
                    data={
                        "title": f"Successfully examined {len(nodes_to_examine)} nodes",
                    },
                )
            else:
                # Human feedback needed
                await self._send_classification_update(
                    display_type="toast",
                    data={
                        "title": "Human feedback required to continue examination",
                    },
                )

        except Exception as e:
            traceback.print_exc()
            await self.connection_manager.send_error_message(
                self.user_id,
                {"title": "Error", "detail": str(e)},
            )

    # =======================================================
    #                   Resume Graphs
    # =======================================================

    async def resume_classify_graph_with_human_messages(
        self,
        message: str,
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
    ):
        """Resume classification after human feedback"""
        try:
            async for chunk in classify_g.astream(
                Command(resume=message),
                config=self.config_for_classify_items_graph,
                stream_mode="custom",
            ):
                if "update_data" not in chunk:
                    raise ValueError(f"update_data not found in chunk: {chunk}")

                await self._send_classification_update(
                    display_type="classify_items",
                    data=chunk["update_data"],
                )

            if self._reached_end_of_classify_graph(classify_g):
                await self._update_nodes_and_items_after_classification(taxonomy_id, db)
                await self._send_classification_update(
                    display_type="none",
                    data={
                        "classification_completed": True,
                    },
                )
                await self._send_classification_update(
                    display_type="toast",
                    data={
                        "title": "Classification completed",
                    },
                )

        except Exception as e:
            traceback.print_exc()
            await self.connection_manager.send_error_message(
                self.user_id,
                {"title": "Error", "detail": str(e)},
            )

    async def resume_examine_nodes_graph_with_human_messages(
        self,
        message: str,
        taxonomy_id: str,
        user_id: str,
        db: AgnosticDatabase,
    ):
        """Resume node examination after human feedback"""
        try:
            async for chunk in examine_nodes_g.astream(
                Command(resume=message),
                config=self.config_for_examine_nodes_graph,
                stream_mode="custom",
            ):
                if "update_data" not in chunk:
                    raise ValueError(f"update_data not found in chunk: {chunk}")

                await self._send_classification_update(
                    display_type="examine_nodes",
                    data=chunk["update_data"],
                )

            if self._reached_end_of_examine_nodes_graph(examine_nodes_g):
                # Get nodes that were being examined (we should track this)
                # For now, we'll need to get them from the graph state
                # This is a limitation of not keeping state - we might need to track examined nodes differently
                nodes_to_examine = []  # This would need to be retrieved from somewhere

                status, result = await self._update_and_return_for_examine_nodes_graph(
                    nodes_to_examine, taxonomy_id, user_id, db
                )

                # Update items in database
                user_items_collection = db[f"items_{user_id}"]
                for item in result:
                    await user_items_collection.update_one(
                        {"_id": ObjectId(item.id)},
                        {
                            "$set": MongoSerializer.deserialize_item_from_state(
                                item, taxonomy_id
                            )
                        },
                    )

                self._update_config_for_examine_nodes_graph()

        except Exception as e:
            traceback.print_exc()
            await self.connection_manager.send_error_message(
                self.user_id,
                {"title": "Error", "detail": str(e)},
            )
