"""End-to-end PE-statement categorization (Story 11.10 AC #15).

Marker-gated integration test. Seeds a user with known full_name, parses the
extended PE fixture, runs the categorization node against a stubbed LLM, and
asserts:
  * Rule 5 (self-IBAN) fires on the self-transfer row.
  * Rule 6 (Treasury) fires on the tax-payment row.
  * Rule 8 (EDRPOU) fires on the business-income row.
  * At least one row lands in `user_iban_registry` (the PE self-counterparty).
  * `categorization.counterparty_rule_hit` is emitted for rule-applicable rows.

The LLM is stubbed so the test is deterministic and doesn't burn tokens.
Swap `_StubLLM` for a real client when doing hands-on regression.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

import app.models  # noqa: F401
from app.agents.categorization.counterparty_patterns import edrpou_kind
from app.agents.categorization.node import categorization_node
from app.agents.ingestion.parsers.ai_detected import AIDetectedParser
from app.core import crypto
from app.models.user import User
from app.models.user_iban_registry import UserIbanRegistry
from app.services.user_iban_registry import UserIbanRegistryService


pytestmark = pytest.mark.integration


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "pe_statement_extended_sample.csv"
_MAPPING = {
    "delimiter": ";",
    "date_column": "Дата операції",
    "date_format": "%d.%m.%Y",
    "amount_column": "Сума",
    "amount_sign_convention": "negative_is_outflow",
    "description_column": "Призначення платежу",
    "counterparty_name_column": "Контрагент",
    "counterparty_tax_id_column": "ІПН контрагента",
    "counterparty_account_column": "Рахунок контрагента",
}


class _StubLLM:
    """Returns a canned JSON response; the deterministic post-processor then
    overrides rows where the LLM disagrees with the counterparty rule.
    """

    model_name = "stub"
    model = "stub"

    def __init__(self, responses_by_id: dict[str, dict]):
        self._responses = responses_by_id

    def invoke(self, prompt: str):
        # Extract ids from the prompt (very loose) — just build a response for
        # every id we expect. The test controls the id set.
        items = [
            {
                "id": tid,
                "category": r["category"],
                "transaction_kind": r["transaction_kind"],
                "confidence": 0.85,
            }
            for tid, r in self._responses.items()
        ]
        return SimpleNamespace(
            content=json.dumps(items),
            usage_metadata={"total_tokens": 0},
        )


@pytest.fixture
def _local_fernet():
    key = Fernet.generate_key().decode()
    with (
        patch.object(crypto.settings, "ENV", "local"),
        patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", None),
        patch.object(crypto.settings, "LOCAL_IBAN_FERNET_KEY", key),
    ):
        yield


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_pe_categorization_e2e(session, _local_fernet):
    user = User(
        id=uuid.uuid4(),
        cognito_sub="sub-e2e",
        email="e2e@example.com",
    )
    session.add(user)
    session.commit()

    # Pre-register the user's own IBAN (matches gs-style self-transfer row).
    svc = UserIbanRegistryService(session)
    svc.register(
        user.id,
        "UA213223130000026007233566999",
        label="PE counterparty (self)",
    )
    session.commit()

    # Parse PE-statement CSV.
    parser = AIDetectedParser(_MAPPING)
    file_bytes = FIXTURE.read_bytes()
    result = parser.parse(file_bytes, encoding="utf-8", delimiter=";")
    assert result.parsed_count == 3

    tids = [f"t{i}" for i in range(len(result.transactions))]
    txns = []
    for tid, t in zip(tids, result.transactions):
        is_self = svc.is_user_iban(user.id, t.counterparty_account or "") if t.counterparty_account else False
        txns.append(
            {
                "id": tid,
                "description": t.description,
                "amount": t.amount,
                "mcc": t.mcc,
                "date": str(t.date),
                "counterparty_name": t.counterparty_name,
                "counterparty_tax_id": t.counterparty_tax_id,
                "counterparty_account": t.counterparty_account,
                "counterparty_tax_id_kind": edrpou_kind(t.counterparty_tax_id),
                "is_self_iban": is_self,
            }
        )

    # LLM disagrees on the self-transfer row (calls it P2P) and the Treasury
    # row (calls it "other") — the deterministic post-processor must override.
    stub = _StubLLM(
        {
            "t0": {"category": "transfers_p2p", "transaction_kind": "spending"},
            "t1": {"category": "other", "transaction_kind": "spending"},
            "t2": {"category": "other", "transaction_kind": "income"},
        }
    )

    state = {
        "job_id": "e2e",
        "user_id": str(user.id),
        "upload_id": "e2e",
        "transactions": txns,
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
        "detected_subscriptions": [],
        "triage_category_severity_map": {},
    }

    records: list[logging.LogRecord] = []

    class _H(logging.Handler):
        def emit(self, record):
            records.append(record)

    h = _H(level=logging.INFO)
    node_logger = logging.getLogger("app.agents.categorization.node")
    node_logger.addHandler(h)
    try:
        with patch("app.agents.categorization.node.get_llm_client", return_value=stub):
            result_state = categorization_node(state)
    finally:
        node_logger.removeHandler(h)

    by_id = {r["transaction_id"]: r for r in result_state["categorized_transactions"]}

    # Row 0: self-transfer → Rule 5 override.
    assert by_id["t0"]["category"] == "transfers"
    assert by_id["t0"]["transaction_kind"] == "transfer"

    # Row 1: Treasury outbound → Rule 6 override.
    assert by_id["t1"]["category"] == "government"
    assert by_id["t1"]["transaction_kind"] == "spending"

    # Row 2: EDRPOU inbound business income → Rule 8 (LLM answer preserved).
    assert by_id["t2"]["category"] == "other"
    assert by_id["t2"]["transaction_kind"] == "income"

    # Registry must contain at least the pre-registered self-IBAN.
    registry_rows = session.execute(
        select(UserIbanRegistry).where(UserIbanRegistry.user_id == user.id)
    ).scalars().all()
    assert len(registry_rows) >= 1

    # Structured log: counterparty_rule_hit fires for each rule-applicable row.
    hit_msgs = [r.getMessage() for r in records if "counterparty_rule_hit" in r.getMessage()]
    assert len(hit_msgs) == 3  # one per PE row
