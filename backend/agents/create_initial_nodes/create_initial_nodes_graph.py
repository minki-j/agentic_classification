from pydantic import BaseModel, Field
from typing import Annotated

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langgraph.graph import START, END, StateGraph, add_messages
from langgraph.types import Command, interrupt
from langgraph.config import get_stream_writer

from agents.common import get_checkpointer
from agents.llm_factory import LLMFactory, AIModel
from agents.utils import (
    format_batch_items,
    format_class_nodes,
    abbreviate_node_ids,
    restore_abbreviated_node_ids,
)
from agents.state import ClassNodeState, Taxonomy, ItemState, node_reducer, root_node


class CreateInitialNodesState(BaseModel):
    taxonomy: Taxonomy
    user_id: str
    llm: AIModel
    items: list[ItemState]
    nodes: Annotated[list[ClassNodeState], node_reducer] = Field(
        default_factory=lambda: [],
    )
    use_human_in_the_loop: bool
    message_history: Annotated[list[BaseMessage], add_messages] = Field(
        default_factory=list
    )
    is_valid: bool = Field(
        default=False,
        description="Whether the taxonomy is validated by the validator node.",
    )
    abbreviated_id_to_original_map: dict[str, str] = Field(
        default_factory=dict,
        description="A map of shortened node ids to their original node ids.",
    )


important_rules = [
    "This is not a classification task. You are creating a taxonomy. Don't try to put items in the examples of the class node unless it is a representative example.",
    "Often times, you may create multiple layers of nodes. Think if the final layer of nodes can capture the nuances of the class. If not, create more layers under them.",
    "Create at least 3 layers of nodes.",
    "Try to make the first layer of nodes cover high-level aspects, getting more detailed as you go deeper.",
    "Ideally, the first layer should not have more than 5 nodes.",
    "Don't include the nodes that are already in the taxonomy in your response.",
    "Follow the provided json output schema strictly.",
]
important_rules = (
    "Important Rules:\n- " + "\n- ".join(important_rules).strip()
    if important_rules
    else ""
)


async def init_message_history(state: CreateInitialNodesState):
    (
        abbreviated_nodes,
        abbreviated_id_to_original_map,
        original_id_to_abbreviated_map,
    ) = abbreviate_node_ids(state.nodes)

    input_messages = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(
                """
You are a classification agent. You will be given a list of items. Your goal is to create a taxonomy for the items. (Note that this is not a classification task. You are creating a taxonomy.)

The taxonomy you'll create has the following aspect that you should focus on:
{taxonomy_aspect}

The taxonomy has a single root node. It can have many children nodes. Each node is where the items will be classified. The depth of node can go as deep as you want.

{important_rules}
    """.strip()
            ),
            HumanMessagePromptTemplate.from_template(
                """
You currently have the following nodes in the taxonomy:
{nodes}

And here are the items from which you'll create the taxonomy:
{items}

{important_rules}
    """.strip()
            ),
        ]
    ).format_messages(
        taxonomy_aspect=state.taxonomy.aspect,
        nodes=await format_class_nodes(
            nodes=abbreviated_nodes,
            user_id=state.user_id,
            num_examples=4,
            max_length=1000,
        ),
        items=format_batch_items(state.items, include_id=False),
        important_rules=important_rules,
    )

    return {
        "message_history": input_messages,
        "abbreviated_id_to_original_map": abbreviated_id_to_original_map,
    }


async def create_taxonomy(state: CreateInitialNodesState):
    writer = get_stream_writer()

    if len(state.message_history) == 2:
        writer(
            {
                "message": f"'{state.llm.value}' is examining {len(state.items)} items and creating the starting point of your categorization hierarchy!"
            }
        )

    class NodeSchema(BaseModel):
        id: str = Field(
            description="A random 4 character and number string that is used to identify the node.",
        )
        parent_node_id: str
        label: str
        description: str

    class Schema(BaseModel):
        nodes: list[NodeSchema] = Field(description="List of nodes to create")

    llm = LLMFactory()
    response: Schema = await llm.ainvoke(
        model=state.llm,
        prompts=state.message_history,
        output_schema=Schema,
    )

    nodes: list[ClassNodeState] = [
        ClassNodeState(**node.model_dump()) for node in response.nodes
    ]

    # remove nodes that are already in the taxonomy
    nodes = [node for node in nodes if node.id not in [node.id for node in state.nodes]]

    restored_nodes = restore_abbreviated_node_ids(
        nodes, state.abbreviated_id_to_original_map
    )
    restored_nodes.append(
        ClassNodeState(id="REPLACE_ALL", parent_node_id="", label="", description="")
    )

    return {
        "nodes": restored_nodes,
        "message_history": [
            AIMessage(content="\n".join([node.model_dump_json() for node in nodes]))
        ],
    }


async def validator(state: CreateInitialNodesState):
    writer = get_stream_writer()
    if not state.taxonomy.rules:
        writer({"message": "No rules provided. Skipping validation."})
        return {
            "is_valid": True,
        }

    writer(
        {
            "message": f"Validating generated taxonomy with {len(state.taxonomy.rules)} rules:<br>- "
            + "<br>- ".join(state.taxonomy.rules)
        }
    )

    class Schema(BaseModel):
        think_out_loud: str = Field(
            description="Think out loud and explain your reasoning."
        )
        is_valid: bool = Field(description="Whether the taxonomy is valid.")

    llm = LLMFactory()
    response: Schema = await llm.ainvoke(
        model=state.llm,
        prompts=state.message_history
        + [
            HumanMessage(
                content=f"""
Check if the taxonomy follows the checklist below.

{"- " + "\n- ".join(state.taxonomy.rules)}
"""
            )
        ],
        output_schema=Schema,
    )

    return {
        "is_valid": response.is_valid,
        "message_history": [
            HumanMessage(
                content=f"""
The taxonomy is invalid. Here is the reasoning:
{response.think_out_loud}

Please address the issues and return a valid nodes.
""".strip()
            )
        ]
        if not response.is_valid
        else [],
    }


def handle_validation_result(state: CreateInitialNodesState):
    writer = get_stream_writer()

    if not state.is_valid:
        if state.use_human_in_the_loop:
            message_from_user = interrupt(
                {
                    "get_user_message": "The validator said the taxonomy is invalid. You can add message if you need to."
                }
            )
            if message_from_user.lower() in ["pass"]:
                return Command(goto=END)
            else:
                return Command(goto=create_taxonomy.__name__)
        else:
            writer({"message": "Validation didn't pass. Modifying taxonomy..."})
            return Command(goto=create_taxonomy.__name__)

    writer({"message": "Validation completed! All good!"})
    return Command(goto=END)


g = StateGraph(CreateInitialNodesState)
g.add_edge(START, init_message_history.__name__)

g.add_node(init_message_history)
g.add_edge(init_message_history.__name__, create_taxonomy.__name__)

g.add_node(create_taxonomy)
g.add_edge(create_taxonomy.__name__, validator.__name__)

g.add_node(validator)
g.add_edge(validator.__name__, handle_validation_result.__name__)

g.add_node(handle_validation_result, destinations=(create_taxonomy.__name__, END))

g = g.compile(checkpointer=get_checkpointer())

with open("./agents/diagrams/create_initial_nodes.png", "wb") as f:
    f.write(g.get_graph().draw_mermaid_png())
