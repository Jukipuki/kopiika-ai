"""Tests for Story 2.9: centralized CURRENCY_MAP in app.services.currency."""

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.currency import (
    CURRENCY_MAP,
    DEFAULT_CURRENCY_CODE,
    UNKNOWN_CURRENCY_CODE,
    CurrencyInfo,
    alpha_for_numeric,
    extract_raw_currency,
    resolve_currency,
)
from app.services.transaction_service import compute_dedup_hash


class TestCurrencyMapContents:
    """AC #4 — CURRENCY_MAP contains the full required set with correct ISO 4217 mappings."""

    def test_contains_required_codes(self):
        required = {"UAH", "USD", "EUR", "GBP", "PLN", "CHF", "JPY", "CZK", "TRY"}
        assert required.issubset(CURRENCY_MAP.keys())

    def test_iso_numeric_mappings(self):
        expected = {
            "UAH": 980,
            "USD": 840,
            "EUR": 978,
            "GBP": 826,
            "PLN": 985,
            "CHF": 756,
            "JPY": 392,
            "CZK": 203,
            "TRY": 949,
        }
        for alpha, numeric in expected.items():
            info = CURRENCY_MAP[alpha]
            assert isinstance(info, CurrencyInfo)
            assert info.numeric_code == numeric
            assert info.alpha_code == alpha
            assert isinstance(info.symbol, str) and info.symbol

    def test_default_and_unknown_constants(self):
        assert DEFAULT_CURRENCY_CODE == 980
        assert UNKNOWN_CURRENCY_CODE == 0
        # Unknown sentinel must not collide with any real ISO 4217 numeric.
        assert UNKNOWN_CURRENCY_CODE not in {info.numeric_code for info in CURRENCY_MAP.values()}


class TestResolveCurrency:
    """resolve_currency is case-insensitive, whitespace-tolerant, and returns None on miss."""

    def test_exact_match(self):
        info = resolve_currency("UAH")
        assert info is not None
        assert info.numeric_code == 980
        assert info.alpha_code == "UAH"

    def test_lowercase(self):
        info = resolve_currency("uah")
        assert info is not None
        assert info.alpha_code == "UAH"

    def test_whitespace_trimmed(self):
        info = resolve_currency(" UAH ")
        assert info is not None
        assert info.alpha_code == "UAH"

    def test_unknown_returns_none(self):
        assert resolve_currency("XYZ") is None

    def test_none_input_returns_none(self):
        assert resolve_currency(None) is None

    def test_new_currencies_resolve(self):
        for alpha in ("CHF", "JPY", "CZK", "TRY"):
            info = resolve_currency(alpha)
            assert info is not None
            assert info.alpha_code == alpha


class TestAlphaForNumeric:
    def test_known_numeric_returns_alpha(self):
        assert alpha_for_numeric(980) == "UAH"
        assert alpha_for_numeric(756) == "CHF"
        assert alpha_for_numeric(392) == "JPY"

    def test_unknown_numeric_returns_none(self):
        assert alpha_for_numeric(0) is None
        assert alpha_for_numeric(999) is None


class TestExtractRawCurrency:
    def test_ukrainian_key(self):
        assert extract_raw_currency({"Валюта": "CHF"}) == "CHF"

    def test_english_key_normalized(self):
        assert extract_raw_currency({"Currency": " jpy "}) == "JPY"

    def test_ukrainian_preferred_when_both(self):
        # Ukrainian key checked first — matches Monobank statements.
        assert extract_raw_currency({"Валюта": "TRY", "Currency": "USD"}) == "TRY"

    def test_empty_dict(self):
        assert extract_raw_currency({}) is None

    def test_none_input(self):
        assert extract_raw_currency(None) is None

    def test_missing_key(self):
        assert extract_raw_currency({"Other": "value"}) is None

    def test_non_string_ignored(self):
        assert extract_raw_currency({"Валюта": 123}) is None

    def test_whitespace_only_ignored(self):
        assert extract_raw_currency({"Валюта": "   "}) is None


class TestCurrencyUnknownMigration:
    """Structural + functional coverage for the `currency_unknown` constraint widen.

    Note: the migration itself uses plain `op.drop_constraint` + `op.create_check_constraint`,
    which does NOT run on SQLite — the project's test DB is built from `SQLModel.metadata.create_all()`
    and bypasses migrations (see `backend/alembic/env.py` and `tests/conftest.py`). This test
    therefore covers:
      1. The migration file statically includes `currency_unknown` in upgrade and excludes it from downgrade.
      2. The persisted model accepts a row with `uncategorized_reason="currency_unknown"` and
         `currency_code=UNKNOWN_CURRENCY_CODE` without error.
    """

    MIGRATION_PATH = (
        Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "n0o1p2q3r4s5_add_currency_unknown_to_uncategorized_reason.py"
    )

    def test_migration_file_exists(self):
        assert self.MIGRATION_PATH.is_file(), "Expected Story 2.9 migration file to exist"

    def test_upgrade_adds_currency_unknown_to_allowed_reasons(self):
        content = self.MIGRATION_PATH.read_text()
        # upgrade() must list currency_unknown alongside the existing reasons
        assert 'def upgrade()' in content
        assert '"currency_unknown"' in content.split('def downgrade()')[0]

    def test_downgrade_removes_currency_unknown(self):
        content = self.MIGRATION_PATH.read_text()
        downgrade_section = content.split('def downgrade()')[1]
        assert '"currency_unknown"' not in downgrade_section

    def test_revision_chain_is_correct(self):
        content = self.MIGRATION_PATH.read_text()
        assert 'revision: str = "n0o1p2q3r4s5"' in content
        assert 'down_revision: Union[str, Sequence[str], None] = "m9n0o1p2q3r4"' in content

    def test_api_literal_matches_migration_allowed_list(self):
        """The API's Literal type must be in lockstep with the migration's allowed list."""
        from typing import get_args

        from app.api.v1.transactions import FlaggedTransactionResponse

        reason_field = FlaggedTransactionResponse.model_fields["uncategorized_reason"]
        # The annotation is Optional[Literal[...]] → unwrap to get the Literal args.
        literal_values: set[str] = set()
        for arg in get_args(reason_field.annotation):
            literal_values.update(a for a in get_args(arg) if isinstance(a, str))

        assert literal_values == {
            "low_confidence",
            "parse_failure",
            "llm_unavailable",
            "currency_unknown",
        }

    def test_transaction_row_with_currency_unknown_reason_persists(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        try:
            user_id = uuid.uuid4()
            upload_id = uuid.uuid4()
            with Session(engine) as session:
                session.add(User(id=user_id, email="u@test.com", cognito_sub="sub", locale="en"))
                session.add(Upload(
                    id=upload_id, user_id=user_id, file_name="t.csv",
                    s3_key="k", file_size=1, mime_type="text/csv",
                ))
                session.flush()

                txn_date = datetime(2026, 4, 16)
                txn = Transaction(
                    user_id=user_id,
                    upload_id=upload_id,
                    date=txn_date,
                    description="Exotic",
                    amount=-9900,
                    currency_code=UNKNOWN_CURRENCY_CODE,
                    raw_data={"Валюта": "XYZ"},
                    is_flagged_for_review=True,
                    uncategorized_reason="currency_unknown",
                    dedup_hash=compute_dedup_hash(user_id, txn_date, -9900, "Exotic"),
                )
                session.add(txn)
                session.commit()

                fetched = session.exec(select(Transaction)).one()
                assert fetched.currency_code == 0
                assert fetched.uncategorized_reason == "currency_unknown"
                assert fetched.is_flagged_for_review is True
        finally:
            SQLModel.metadata.drop_all(engine)
            engine.dispose()
