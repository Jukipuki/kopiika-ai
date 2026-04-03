"""LangGraph financial pipeline.

Story 3.1 pipeline: categorization only.
Future stories (3.x) will add pattern_detection, triage, education nodes.
"""

from langgraph.graph import END, StateGraph

from app.agents.categorization.node import categorization_node
from app.agents.state import FinancialPipelineState


def build_pipeline() -> StateGraph:
    graph = StateGraph(FinancialPipelineState)
    graph.add_node("categorization", categorization_node)
    graph.set_entry_point("categorization")
    graph.add_edge("categorization", END)
    return graph.compile()


financial_pipeline = build_pipeline()
