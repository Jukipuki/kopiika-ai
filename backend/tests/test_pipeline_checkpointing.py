"""Tests for LangGraph pipeline checkpointing and resume (Story 6.2, AC #1, #2).

Task 9.1: Pipeline checkpoints categorization state before an education failure.
Task 9.2: resume_pipeline() resumes from the last checkpoint, skipping completed nodes.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.circuit_breaker import CircuitBreakerOpenError
from app.agents.pipeline import build_pipeline, resume_pipeline
from app.agents.state import FinancialPipelineState


def _make_pipeline_state(thread_id: str) -> FinancialPipelineState:
    """Minimal valid pipeline state for checkpointing tests."""
    return {
        "job_id": thread_id,
        "user_id": "test-user",
        "upload_id": "test-upload",
        "transactions": [
            {
                "id": "txn-1",
                "mcc": 5411,
                "description": "SILPO",
                "amount": -10000,
                "date": "2024-01-01",
            }
        ],
        "categorized_transactions": [],
        "errors": [],
        "step": "categorization",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
        "literacy_level": "beginner",
        "completed_nodes": [],
        "failed_node": None,
        "pattern_findings": [],
    }


# ---------------------------------------------------------------------------
# Task 9.2: resume_pipeline() API contract
# ---------------------------------------------------------------------------


class TestResumePipelineFunction:
    def test_resume_pipeline_invokes_graph_with_none_and_thread_id(self):
        """resume_pipeline calls graph.invoke(None, {configurable: {thread_id}}).

        Passing None tells LangGraph to resume from the existing checkpoint
        rather than starting a fresh run with new input state.
        """
        checkpointer = MagicMock()
        thread_id = "test-thread-abc"

        with patch("app.agents.pipeline.build_pipeline") as mock_build:
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {"status": "done", "insight_cards": []}
            mock_build.return_value = mock_graph

            result = resume_pipeline(checkpointer, thread_id)

        mock_build.assert_called_once_with(checkpointer=checkpointer)
        mock_graph.invoke.assert_called_once_with(
            None,
            {"configurable": {"thread_id": thread_id}},
        )
        assert result == {"status": "done", "insight_cards": []}

    def test_resume_pipeline_passes_checkpointer_to_build(self):
        """resume_pipeline must compile the graph with the provided checkpointer."""
        checkpointer = MagicMock()

        with patch("app.agents.pipeline.build_pipeline") as mock_build:
            mock_build.return_value = MagicMock()
            mock_build.return_value.invoke.return_value = {}

            resume_pipeline(checkpointer, "some-thread")

        _, kwargs = mock_build.call_args
        assert kwargs["checkpointer"] is checkpointer


# ---------------------------------------------------------------------------
# Task 9.1: Checkpoint preserves categorization results on education failure
# ---------------------------------------------------------------------------


class TestPipelineCheckpointing:
    def test_checkpoint_exists_after_education_node_failure(self):
        """A checkpoint is saved after education fails so the run can be resumed."""
        from langgraph.checkpoint.memory import MemorySaver

        memory = MemorySaver()
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        def mock_cat(state):
            completed = list(state.get("completed_nodes", []))
            completed.append("categorization")
            return {
                **state,
                "categorized_transactions": [
                    {
                        "transaction_id": "txn-1",
                        "category": "groceries",
                        "confidence_score": 1.0,
                        "flagged": False,
                    }
                ],
                "completed_nodes": completed,
                "failed_node": None,
            }

        def mock_edu_fail(state):
            raise CircuitBreakerOpenError("anthropic")

        with (
            patch("app.agents.pipeline.categorization_node", side_effect=mock_cat),
            patch("app.agents.pipeline.education_node", side_effect=mock_edu_fail),
        ):
            graph = build_pipeline(checkpointer=memory)
            with pytest.raises(Exception):
                graph.invoke(_make_pipeline_state(thread_id), config)

        # A checkpoint must exist — this is what enables retry-resume
        checkpoint_tuple = memory.get_tuple(config)
        assert checkpoint_tuple is not None

    def test_checkpoint_retains_categorized_transactions_after_education_failure(self):
        """The checkpoint after an education failure includes categorized_transactions.

        These results must survive so resume_pipeline can persist them to the DB
        without re-running the categorization agent.
        """
        from langgraph.checkpoint.memory import MemorySaver

        memory = MemorySaver()
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        expected_cat = [
            {
                "transaction_id": "txn-1",
                "category": "groceries",
                "confidence_score": 1.0,
                "flagged": False,
            }
        ]

        def mock_cat(state):
            completed = list(state.get("completed_nodes", []))
            completed.append("categorization")
            return {
                **state,
                "categorized_transactions": expected_cat,
                "completed_nodes": completed,
                "failed_node": None,
            }

        def mock_edu_fail(state):
            raise CircuitBreakerOpenError("anthropic")

        with (
            patch("app.agents.pipeline.categorization_node", side_effect=mock_cat),
            patch("app.agents.pipeline.education_node", side_effect=mock_edu_fail),
        ):
            graph = build_pipeline(checkpointer=memory)
            with pytest.raises(Exception):
                graph.invoke(_make_pipeline_state(thread_id), config)

        checkpoint_tuple = memory.get_tuple(config)
        assert checkpoint_tuple is not None
        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        assert "categorized_transactions" in channel_values
        assert channel_values["categorized_transactions"] == expected_cat

    def test_resume_skips_completed_categorization_node(self):
        """On resume after education failure, categorization_node does NOT run again.

        LangGraph loads the checkpoint (state after successful categorization)
        and resumes only from the education node.
        """
        from langgraph.checkpoint.memory import MemorySaver

        memory = MemorySaver()
        thread_id = str(uuid.uuid4())

        cat_runs: list[bool] = []
        edu_runs: list[bool] = []
        edu_attempt = [0]

        def mock_cat(state):
            cat_runs.append(True)
            completed = list(state.get("completed_nodes", []))
            completed.append("categorization")
            return {
                **state,
                "categorized_transactions": [
                    {
                        "transaction_id": "txn-1",
                        "category": "groceries",
                        "confidence_score": 1.0,
                        "flagged": False,
                    }
                ],
                "completed_nodes": completed,
                "failed_node": None,
            }

        def mock_edu(state):
            edu_runs.append(True)
            edu_attempt[0] += 1
            if edu_attempt[0] == 1:
                raise CircuitBreakerOpenError("anthropic")
            completed = list(state.get("completed_nodes", []))
            completed.append("education")
            return {
                **state,
                "insight_cards": [],
                "completed_nodes": completed,
                "failed_node": None,
            }

        config = {"configurable": {"thread_id": thread_id}}

        # Run 1: categorization succeeds, education fails
        with (
            patch("app.agents.pipeline.categorization_node", side_effect=mock_cat),
            patch("app.agents.pipeline.education_node", side_effect=mock_edu),
        ):
            graph = build_pipeline(checkpointer=memory)
            with pytest.raises(Exception):
                graph.invoke(_make_pipeline_state(thread_id), config)

        # Resume: only education should execute again
        with (
            patch("app.agents.pipeline.categorization_node", side_effect=mock_cat),
            patch("app.agents.pipeline.education_node", side_effect=mock_edu),
        ):
            result = resume_pipeline(memory, thread_id=thread_id)

        assert len(cat_runs) == 1, "Categorization must not run on resume (was already checkpointed)"
        assert len(edu_runs) == 2, "Education ran once (failed) and once on resume (succeeded)"
        assert "education" in result.get("completed_nodes", [])
