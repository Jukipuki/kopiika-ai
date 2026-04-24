HALT — architectural mismatch between story spec and actual AgentCore API.

I'm stopping before writing any infrastructure code because AC #1 as written is not implementable against the real AWS AgentCore API. Here's what I verified:

Provider probe (AC #1 step 1 — completed): terraform providers schema -json on hashicorp/aws 5.100.0 (Terraform 1.14.7). The only Bedrock resources are aws_bedrock_* (Guardrail, Custom Model, Inference Profile, etc.) and aws_bedrockagent_* (Bedrock Agents — the legacy service, not AgentCore). There is no native aws_bedrockagentcore_runtime resource. So Path A is unavailable → Path B. ✅ That part matches the story.

The real problem is Path B itself. I ran aws bedrock-agentcore-control create-agent-runtime help (CLI v2.34.35, which despite TD-081 does support the subcommand — TD-081 is stale). The required arguments are:

--agent-runtime-name (string)
--agent-runtime-artifact (required, tagged union of containerConfiguration.containerUri OR codeConfiguration.s3)
--role-arn
--network-configuration
There is no --foundation-model / --model-arn parameter. AgentCore Runtime is not a model-managed endpoint — it is a Lambda-like container fabric: you build a container image (or S3 code bundle) containing your agent code (model invocations, tool calls, memory, etc.), push it to ECR, and AgentCore hosts and invokes that container on each InvokeAgentRuntime call. The model call happens inside your container, not in AgentCore.

The story was written under the assumption that AgentCore = "a managed Sonnet endpoint you pass a runtime ID to". That's actually how Bedrock Agents (the aws_bedrockagent_agent resource) works, not AgentCore Runtime.

Concrete consequences if I try to ship AC #1 as written:

AC #1 Path B says aws bedrock-agentcore create-agent-runtime ... with the foundation-model ARN from models.yaml:chat_default.bedrock — the CLI will reject this with a "missing required --agent-runtime-artifact" error. The null_resource would never apply.
AC #2's IAM role (bedrock-agentcore.amazonaws.com principal with bedrock:InvokeModel on the chat-default inference profile) is still correct — but the grant is consumed by the container code, not by AgentCore control plane.
AC #7's ChatSessionHandler.send_turn calls InvokeAgentRuntime expecting the runtime to invoke Sonnet and return the response. But absent a container, there is no handler to invoke — the call will 404 / return empty.
Three ways forward — I need you to pick one:

Pivot to bedrock-agent (legacy Bedrock Agents) — the aws_bedrockagent_agent resource IS model-based (you pass foundation_model = "..." and optionally an action group + prompt template). This matches the story's mental model almost exactly. Cost: re-read Story 9.4's decision doc — it might have picked AgentCore specifically because Agents has limitations Agents-based chat wouldn't accept. Re-spec AC #1–#4 around aws_bedrockagent_agent + aws_bedrockagent_agent_alias.

Ship AgentCore properly (container-based) — out of scope for a single story. Would need: a new backend/agentcore_container/ package with the handler loop, a Dockerfile, an ECR repo (new Terraform), a build-and-push pipeline, the container IAM role, etc. Probably becomes Story 10.4a + 10.4a-container (split).

Defer the runtime provisioning + drop AgentCore for chat — ship only the backend ChatSessionHandler code calling bedrock:InvokeModel directly (same path Celery batch agents use today) with a light wrapper preserving the 4-method public API so downstream stories (10.4b/10.4c/10.5/10.6a) still have a stable interface. Note: this invalidates architecture.md §AgentCore Deployment Model (L1628-L1635), so the decision-doc would need an amendment. Effectively: chat == batch path with a session-lifecycle layer on top.

Some smaller findings I'll note regardless of the path picked:

No structlog in the codebase — the story references structlog.contextvars.bind_contextvars at upload_service.py, but upload_service.py uses stdlib logging. Will match stdlib-logger pattern with extra={} dict (matches app/core/logging.py's JSON formatter).
tiktoken is not in pyproject.toml (needs adding).
TD-081 is stale — AWS CLI 2.34.35 does support bedrock-agentcore / bedrock-agentcore-control subcommands.
