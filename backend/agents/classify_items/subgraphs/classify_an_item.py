from pydantic import BaseModel, Field, create_model
from typing import Annotated, Any
import operator

from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langgraph.graph import START, StateGraph
from langgraph.types import Command, Send
from langgraph.config import get_stream_writer

from agents.llm_factory import LLMFactory, AIModel
from agents.state import (
    ItemState,
    ConfidenceLevel,
    NodeAndConfidence,
    ClassifyItemsOverallState,
    ClassificationReturnState,
)
from agents.utils import (
    format_children_nodes_from_parent_node_ids,
    format_single_item,
    has_children_nodes,
    get_model_count_dict,
    choose_top_node_ids_from_classification_results,
    abbreviate_node_ids,
)


class ClassifySubGraphState(ClassifyItemsOverallState):
    parent_node_id: str
    current_item: ItemState
    classification_results: Annotated[list[Any], operator.add] = Field(
        default_factory=list,
        description="A list of FinalJudge objects",
    )
    classified_node_ids: list[str] = Field(default_factory=list)


important_notes = [
    "An item can be classified into multiple nodes horizontally.",
    "If the item doesn't belong to any of the children nodes, don't try to shoehorn it into a node. Return an empty list.",
    "You should examine all the children nodes one by one, judging whether the item belongs to the node or not.",
]
important_notes = "- " + "\n- ".join(important_notes).strip()


def spawn_classifications(state: ClassifySubGraphState):
    model_count_dict = get_model_count_dict(state.models, state.total_invocations)
    return Command(
        goto=[
            Send(
                node=classify.__name__,
                arg=ClassifyInternalState(
                    **state.model_dump(),
                    model=model,
                ),
            )
            for model, count in model_count_dict.items()
            for _ in range(count)
        ],
    )


class ClassifyInternalState(ClassifySubGraphState):
    model: AIModel
    parent_node_id: str


async def classify(state: ClassifyInternalState):
    """
    This node classifies an item into one or more child nodes in a branch that has parent node with id `parent_node_id`. Note that it handles a single branch at a time. If there are multiple branches that need to be classified, this node may be called in parallel.
    """

    (
        abbreviated_nodes,
        abbreviated_id_to_original_map,
        original_id_to_abbreviated_map,
    ) = abbreviate_node_ids(state.nodes)

    abbreviated_parent_node_id = original_id_to_abbreviated_map[state.parent_node_id]

    formatted_nodes = await format_children_nodes_from_parent_node_ids(
        nodes=abbreviated_nodes,
        parent_node_ids=abbreviated_parent_node_id,
        user_id=state.user_id,
        num_examples=4,
        max_length=1000,
    )

    input_messages = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(
                """
You are a classification agent. You will be given an item and classify it into one or more child nodes in the taxonomy. 

This taxonomy is created for the following aspect:
{taxonomy_aspect}

Here are the child nodes you'll be classifying the item into. Note that there is a parent node in which the item is already classified into. You'll be classify the provided item into one or more children nodes. 

{nodes}

Important Notes!
{important_notes}
    """.strip()
            ),
            HumanMessagePromptTemplate.from_template(
                """
Here is the item you need to classify:
{item}

Important Notes!
{important_notes}
    """.strip()
            ),
        ]
    ).format_messages(
        taxonomy_aspect=state.taxonomy.aspect,
        nodes=formatted_nodes,
        item=format_single_item(state.current_item),
        important_notes=important_notes,
    )

    # Dynamically create field definitions for the ValidateScheduleResponse class
    children_node_labels = [
        node.label
        for node in state.nodes
        if node.parent_node_id == state.parent_node_id
    ]
    fields = {str(label): (ConfidenceLevel) for label in children_node_labels}

    JudgeForEachNode = create_model("JudgeForEachNode", **fields, __base__=BaseModel)  # type: ignore

    class FinalJudge(BaseModel):
        rationale: str = Field(
            description="Think carefully and holistically which nodes are the most appropriate for the item. You can choose more than one node if you think the item belongs to multiple nodes. If there is no node that the item belongs to, return empty string."
        )
        node_labels: list[str] = Field(
            description="The labels of the nodes that the item is classified as. If the item doesn't belong to any of the children nodes, return empty list."
        )
        node_ids: list[str] = Field(
            description="The ids of the nodes that the item is classified as. If the item doesn't belong to any of the children nodes, return empty list."
        )

    class Schema(BaseModel):
        does_belong_to_each_node: list[JudgeForEachNode] = Field(  # type: ignore
            description="Examine each child node one by one, judging whether the item belongs to the node or not."
        )
        final_judge: FinalJudge = Field(
            description="The final judge for the item. If the item doesn't belong to any of the children nodes, return empty list."
        )

    llm = LLMFactory()
    classification_result: Schema = await llm.ainvoke(
        model=state.model,
        prompts=input_messages,
        output_schema=Schema,
    )

    if classification_result is None:
        return Command(goto=end_of_workflow.__name__)

    # Sometimes, the model returns a wrong node_id for a node_label.
    # Check if the node_ids and node_labels are consistent with each other.
    correct_node_ids = []
    correct_node_labels = []
    for node_id, node_label in zip(
        classification_result.final_judge.node_ids,
        classification_result.final_judge.node_labels,
    ):
        label_with_the_node_id = next(
            (node.label for node in abbreviated_nodes if node.id == node_id), None
        )
        id_with_the_node_label = next(
            (node.id for node in abbreviated_nodes if node.label == node_label), None
        )

        if label_with_the_node_id is None or node_label != label_with_the_node_id:
            # The generated node id is incorrect
            if id_with_the_node_label is None:
                print(
                    "[Correct node_id]  No matching node id and label: ",
                    node_id,
                    node_label,
                )
                # the generated node label doesn't match with any node label
                continue
            else:
                print(
                    f"[Correct node_id] ({node_label}) {node_id} -> {id_with_the_node_label}"
                )
                # if the generated node id is incorrect, but we found a node with the generated label, we use the node id of that node
                correct_node_ids.append(id_with_the_node_label)
                correct_node_labels.append(node_label)
        else:
            # The node id is correct and matches with the node label
            correct_node_ids.append(node_id)
            correct_node_labels.append(node_label)

    correct_node_ids = [
        abbreviated_id_to_original_map[node_id] for node_id in correct_node_ids
    ]

    return {
        "classification_results": [
            FinalJudge(
                rationale=classification_result.final_judge.rationale,
                node_labels=correct_node_labels,
                node_ids=correct_node_ids,
            )
        ],
    }


def end_of_workflow(state: ClassifySubGraphState):
    writer = get_stream_writer()
    selected_node_and_confidence_score = (
        choose_top_node_ids_from_classification_results(
            state.classification_results, state.majority_threshold
        )
    )

    new_parent_node_ids = [
        node_id
        for node_id, _ in selected_node_and_confidence_score
        if has_children_nodes(state.nodes, node_id)
    ]
    cases_need_further_classification = [
        {parent_node_id: state.current_item} for parent_node_id in new_parent_node_ids
    ]

    writer(
        {
            "update_data": {
                "item_id": state.current_item.id,
                "new_parent_ids": new_parent_node_ids,
            }
        }
    )

    updated_current_item = ItemState(
        id=state.current_item.id,
        content=state.current_item.content,
        classified_as=[
            NodeAndConfidence(node_id=node_id, confidence_score=confidence_score)
            for node_id, confidence_score in selected_node_and_confidence_score
        ],
    )

    return Command(
        graph=Command.PARENT,
        goto=Send(
            node="receive_classification_results",
            arg=ClassificationReturnState(
                classified_item=updated_current_item,
                cases_need_further_classification=cases_need_further_classification,
            ),
        ),
    )


g = StateGraph(ClassifySubGraphState)
g.add_edge(START, spawn_classifications.__name__)

g.add_node(spawn_classifications, destinations=(classify.__name__,))

g.add_node(classify)
g.add_edge(classify.__name__, end_of_workflow.__name__)

g.add_node(end_of_workflow, defer=True)

g = g.compile()
