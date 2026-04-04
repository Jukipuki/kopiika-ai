"""LangGraph financial pipeline.

Story 3.3 pipeline: categorization → education.
"""

from langgraph.graph import END, StateGraph

from app.agents.categorization.node import categorization_node
from app.agents.education.node import education_node
from app.agents.state import FinancialPipelineState


def build_pipeline() -> StateGraph:
    graph = StateGraph(FinancialPipelineState)
    graph.add_node("categorization", categorization_node)
    graph.add_node("education", education_node)
    graph.set_entry_point("categorization")
    graph.add_edge("categorization", "education")
    graph.add_edge("education", END)
    return graph.compile()


financial_pipeline = build_pipeline()
