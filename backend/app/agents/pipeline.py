"""LangGraph financial pipeline.

Story 3.3 pipeline: categorization → education.
Story 6.2: added checkpointer support for failure recovery.
Story 8.1: inserted pattern_detection node between categorization and education.
Story 8.3: inserted triage node between pattern_detection and education.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.categorization.node import categorization_node
from app.agents.education.node import education_node
from app.agents.pattern_detection.node import pattern_detection_node
from app.agents.state import FinancialPipelineState
from app.agents.triage.node import triage_node


def build_pipeline(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph = StateGraph(FinancialPipelineState)
    graph.add_node("categorization", categorization_node)
    graph.add_node("pattern_detection", pattern_detection_node)
    graph.add_node("triage", triage_node)
    graph.add_node("education", education_node)
    graph.set_entry_point("categorization")
    graph.add_edge("categorization", "pattern_detection")
    graph.add_edge("pattern_detection", "triage")
    graph.add_edge("triage", "education")
    graph.add_edge("education", END)
    return graph.compile(checkpointer=checkpointer)


# Default pipeline without checkpointing (backwards-compatible)
financial_pipeline = build_pipeline()


def resume_pipeline(
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
) -> dict:
    """Resume a pipeline from its last checkpoint.

    Builds a new graph with the given checkpointer, then invokes it
    with the same thread_id. LangGraph automatically resumes from the
    last successful node.

    Returns the final pipeline state dict.
    """
    graph = build_pipeline(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(None, config)
