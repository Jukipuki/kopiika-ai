"""Phase B placeholder tests for the AgentCore backend.

Per ADR-0004, AgentCore Runtime is a container fabric — implementation
lives in story ``10.4a-runtime``. This file exists so the Phase B story has
a landing pad and so a reviewer scanning ``backend/tests/agents/chat/``
sees the deferred surface at a glance.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Phase B — story 10.4a-runtime")


def test_agentcore_backend_create_session():
    # Phase B: calls bedrock-agentcore-control:CreateSession and returns the
    # AWS-assigned session id. Failure → ChatSessionCreationError.
    ...


def test_agentcore_backend_invoke():
    # Phase B: calls bedrock-agentcore:InvokeAgentRuntime, same exception
    # translation table as DirectBedrockBackend.
    ...


def test_agentcore_backend_terminate_session_idempotent_on_404():
    # Phase B: ResourceNotFoundException from DeleteSession is swallowed
    # with an INFO log; any other ClientError raises ChatSessionTerminationFailed.
    ...
