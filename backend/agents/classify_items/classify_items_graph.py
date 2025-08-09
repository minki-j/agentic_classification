from langgraph.graph import START, END, StateGraph
from langgraph.types import Command, interrupt, Send
from langgraph.config import get_stream_writer

from agents.common import get_checkpointer
from agents.state import (
    ClassNodeState,
    ClassificationReturnState,
    ClassifyItemsOverallState,
    InterruptType,
)
from agents.classify_items.subgraphs.classify_an_item import (
    g as classify_an_item_graph,
    ClassifySubGraphState,
)


def spawn_next_batch(state: ClassifyItemsOverallState):
    if not state.items:
        # There will be no items when initializing the graph.
        return Command(goto=end_of_workflow.__name__)

    # TODO: we need a rate limiter in case there are too many items in a batch
    return Command(
        goto=[
            Send(
                node="classify_an_item_graph",
                arg=ClassifySubGraphState(
                    **state.model_dump(),
                    current_item=item,
                    parent_node_id=state.root_node_id,
                ),
            )
            for item in state.items
        ],
    )


def receive_classification_results(state: ClassificationReturnState):
    # This node is necessary to update the state with the results from the classify subgraph
    # We need this node separately from the handle_classification_results node because that node uses Command with Send which makes it complicated to update the state.
    # When using Send, you have to pass the state manually.
    # When using Command, the state update is not applied to the goto nodes immediately.
    writer = get_stream_writer()

    if state.classified_item and state.classified_item.classified_as:
        classified_nodes = [
            {
                "node_id": node_and_confidence.node_id,
                "confidence_score": node_and_confidence.confidence_score,
            }
            for node_and_confidence in state.classified_item.classified_as
        ]
        writer(
            {
                "update_data": {
                    "item_id": state.classified_item.id,
                    "classified_as": classified_nodes,
                }
            }
        )

    return {
        "items": state.classified_item,
        "cases_need_further_classification": state.cases_need_further_classification,
    }


def handle_classification_results(state: ClassifyItemsOverallState):
    if not state.cases_need_further_classification:
        return Command(goto=end_of_workflow.__name__)

    return Command(
        goto=[
            Send(
                node="classify_an_item_graph",
                arg=ClassifySubGraphState(
                    **state.model_dump(),
                    current_item=item,
                    parent_node_id=parent_node_id,
                ),
            )
            for case in state.cases_need_further_classification
            for parent_node_id, item in case.items()
        ],
        update={
            "cases_need_further_classification": "RESET",
        },
    )


def end_of_workflow(state: ClassifyItemsOverallState):
    if state.is_for_single_batch:
        return Command(goto=END)

    # When we want to keep classifying more items with next batch, we interrupt the graph here until we get new batch of items.
    interrupt(
        {
            InterruptType.NEXT_BATCH: "Items are all classified. Please provide next batch."
        }
    )
    return Command(goto=spawn_next_batch.__name__)


g = StateGraph(ClassifyItemsOverallState)
g.add_edge(START, spawn_next_batch.__name__)

g.add_node(
    spawn_next_batch,
    defer=True,
    destinations=("classify_an_item_graph", end_of_workflow.__name__),
)

g.add_node("classify_an_item_graph", classify_an_item_graph)

g.add_node(receive_classification_results, defer=True)
g.add_edge(
    receive_classification_results.__name__, handle_classification_results.__name__
)

g.add_node(handle_classification_results, defer=True)

g.add_node(
    end_of_workflow,
    defer=True,
    destinations=(
        spawn_next_batch.__name__,
        END,
    ),
)

g = g.compile(checkpointer=get_checkpointer())


with open("./agents/diagrams/classify_items.png", "wb") as f:
    f.write(g.get_graph(xray=True).draw_mermaid_png())
