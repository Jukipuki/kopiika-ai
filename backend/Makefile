.PHONY: eval-rag eval-categorization

# Story 9.1: full RAG evaluation harness (requires seeded pgvector corpus
# and ANTHROPIC_API_KEY / OPENAI_API_KEY in env).
eval-rag:
	uv run pytest tests/eval/rag/ -v -m eval -s

# Story 11.1: categorization golden-set harness.
eval-categorization:
	uv run pytest tests/agents/categorization/test_golden_set.py -v -m integration -s
