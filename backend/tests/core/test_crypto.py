"""Unit tests for app.core.crypto (Story 11.10 AC #14)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core import crypto
from app.core.crypto import CryptoConfigError, decrypt_iban, encrypt_iban


@pytest.fixture
def local_fernet_settings():
    key = Fernet.generate_key().decode()
    with (
        patch.object(crypto.settings, "ENV", "local"),
        patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", None),
        patch.object(crypto.settings, "LOCAL_IBAN_FERNET_KEY", key),
    ):
        yield key


class TestLocalFernetFallback:
    def test_round_trip(self, local_fernet_settings):
        iban = "UA213223130000026007233566001"
        ct = encrypt_iban(iban)
        assert ct.startswith(b"\x02")
        assert decrypt_iban(ct) == iban

    def test_distinct_ciphertexts_on_repeat(self, local_fernet_settings):
        iban = "UA213223130000026007233566001"
        a = encrypt_iban(iban)
        b = encrypt_iban(iban)
        assert a != b

    def test_rejects_empty_plaintext(self, local_fernet_settings):
        with pytest.raises(ValueError):
            encrypt_iban("")

    def test_rejects_non_local_env_without_kms(self):
        with (
            patch.object(crypto.settings, "ENV", "staging"),
            patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", None),
            patch.object(crypto.settings, "LOCAL_IBAN_FERNET_KEY", Fernet.generate_key().decode()),
        ):
            with pytest.raises(CryptoConfigError):
                encrypt_iban("UA00")

    def test_missing_local_fernet_key(self):
        with (
            patch.object(crypto.settings, "ENV", "local"),
            patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", None),
            patch.object(crypto.settings, "LOCAL_IBAN_FERNET_KEY", None),
        ):
            with pytest.raises(CryptoConfigError):
                encrypt_iban("UA00")

    def test_fallback_emits_warn_log(self, local_fernet_settings):
        import logging

        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        h = _Capture(level=logging.WARNING)
        logger = logging.getLogger("app.core.crypto")
        logger.addHandler(h)
        try:
            encrypt_iban("UA00")
        finally:
            logger.removeHandler(h)
        assert any("fernet_fallback_used" in r.getMessage() for r in records)


class TestKmsPath:
    def test_round_trip_with_mock_kms(self):
        # GCM nonce uniqueness for the AES-256 DEK path — exercise via a fake KMS.
        dek = b"0" * 32
        dek_ct = b"fake-kms-blob"

        class FakeKms:
            def generate_data_key(self, KeyId, KeySpec):
                assert KeySpec == "AES_256"
                return {"Plaintext": dek, "CiphertextBlob": dek_ct}

            def decrypt(self, CiphertextBlob):
                assert CiphertextBlob == dek_ct
                return {"Plaintext": dek}

        fake = FakeKms()
        with (
            patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", "arn:aws:kms:eu-central-1:1:key/abc"),
            patch.object(crypto, "_kms_client", return_value=fake),
        ):
            iban = "UA213223130000026007233566001"
            ct1 = encrypt_iban(iban)
            ct2 = encrypt_iban(iban)
            assert ct1.startswith(b"\x01")
            # Distinct nonces → distinct ciphertexts (GCM requirement).
            assert ct1 != ct2
            assert decrypt_iban(ct1) == iban
            assert decrypt_iban(ct2) == iban


class TestMalformedInputs:
    def test_decrypt_empty(self, local_fernet_settings):
        with pytest.raises(ValueError):
            decrypt_iban(b"")

    def test_decrypt_unknown_prefix(self, local_fernet_settings):
        with pytest.raises(ValueError):
            decrypt_iban(b"\xff" + b"garbage")
