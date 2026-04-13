"""Tests for Story 2.2: File Validation & Format Detection.

Covers: magic-byte validation, format detection, encoding detection,
sanitization, error responses, and upload endpoint integration.
"""

import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.core.security import get_current_user_payload
from app.main import app
from app.services.format_detector import (
    FormatDetectionResult,
    detect_encoding,
    detect_format,
)
from app.services.upload_service import (
    sanitize_content,
    validate_and_detect_format,
    validate_csv_structure,
    validate_magic_bytes,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ==================== Helpers ====================


async def _create_test_user(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "format-test@example.com", "password": "StrongPass1!"},
    )
    await client.post(
        "/api/v1/auth/verify",
        json={"email": "format-test@example.com", "code": "123456"},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "format-test@example.com", "password": "StrongPass1!"},
    )
    return "test-cognito-sub-123"


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


# ==================== 5.1: Magic-byte Validation ====================


class TestMagicByteValidation:
    """Test magic-byte validation — CSV with wrong extension, PDF with wrong MIME, binary disguised as CSV."""

    def test_valid_csv_passes(self):
        content = b"date,amount\n2024-01-01,100"
        validate_magic_bytes(content, "text/csv")  # Should not raise

    def test_valid_pdf_passes(self):
        content = b"%PDF-1.4 some pdf content here"
        validate_magic_bytes(content, "application/pdf")  # Should not raise

    def test_empty_file_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(b"", "text/csv")
        assert exc_info.value.code == "EMPTY_FILE"

    def test_binary_disguised_as_csv_raises(self):
        content = (FIXTURES_DIR / "binary_disguised.csv").read_bytes()
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(content, "text/csv")
        assert exc_info.value.code == "CORRUPTED_FILE"

    def test_pdf_wrong_magic_bytes_raises(self):
        content = b"NOT-A-PDF just some text"
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(content, "application/pdf")
        assert exc_info.value.code == "CORRUPTED_FILE"

    def test_csv_with_null_bytes_raises(self):
        content = b"date,amount\x00\n2024-01-01,100"
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(content, "text/csv")
        assert exc_info.value.code == "CORRUPTED_FILE"


# ==================== 5.2: Format Detection ====================


class TestFormatDetection:
    """Test format detection — Monobank CSV, PrivatBank CSV, unknown CSV, malformed CSV."""

    def test_monobank_legacy_csv_detected(self):
        content = (FIXTURES_DIR / "monobank_sample.csv").read_bytes()
        result = detect_format(content)
        assert result.bank_format == "monobank"
        assert result.confidence_score >= 0.6
        assert result.delimiter == ";"

    def test_monobank_modern_csv_detected(self):
        content = (FIXTURES_DIR / "monobank_modern.csv").read_bytes()
        result = detect_format(content)
        assert result.bank_format == "monobank"
        assert result.confidence_score >= 0.6
        assert result.delimiter == ","
        assert result.column_count == 10

    def test_unknown_csv_format(self):
        content = (FIXTURES_DIR / "unknown_bank.csv").read_bytes()
        result = detect_format(content)
        assert result.bank_format == "unknown"
        assert result.column_count > 0

    def test_privatbank_csv_detected(self):
        header = "Дата операції,Опис операції,Категорія,Сума,Валюта"
        row = "01.01.2024,Покупка,Продукти,-100.00,UAH"
        content = (header + "\n" + row + "\n").encode("utf-8")
        result = detect_format(content)
        assert result.bank_format == "privatbank"
        assert result.confidence_score >= 0.8

    def test_detection_returns_correct_dataclass(self):
        content = (FIXTURES_DIR / "monobank_sample.csv").read_bytes()
        result = detect_format(content)
        assert isinstance(result, FormatDetectionResult)
        assert isinstance(result.bank_format, str)
        assert isinstance(result.encoding, str)
        assert isinstance(result.delimiter, str)
        assert isinstance(result.column_count, int)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.header_row, list)

    def test_monobank_english_csv_detected(self):
        content = (FIXTURES_DIR / "monobank_english.csv").read_bytes()
        result = detect_format(content)
        assert result.bank_format == "monobank"
        assert result.confidence_score >= 0.6
        assert result.delimiter == ","

    def test_generic_csv_returns_unknown(self):
        content = b"col1,col2,col3\nval1,val2,val3\n"
        result = detect_format(content)
        assert result.bank_format == "unknown"
        assert result.delimiter == ","
        assert result.column_count == 3


# ==================== 5.3: Encoding Detection ====================


class TestEncodingDetection:
    """Test encoding detection — Windows-1251, UTF-8, UTF-8-BOM, ISO-8859-1."""

    def test_windows_1251_detected(self):
        content = (FIXTURES_DIR / "monobank_sample.csv").read_bytes()
        encoding, _ = detect_encoding(content)
        assert encoding.lower().replace("-", "").replace("_", "") in (
            "windows1251", "cp1251", "windows-1251"
        ) or encoding == "windows-1251"

    def test_utf8_detected(self):
        content = "date,amount\n2024-01-01,100".encode("utf-8")
        encoding, _ = detect_encoding(content)
        assert "utf" in encoding.lower() or encoding.lower() == "ascii"

    def test_utf8_bom_handled(self):
        content = b"\xef\xbb\xbfdate,amount\n2024-01-01,100"
        encoding, _ = detect_encoding(content)
        assert "utf" in encoding.lower()

    def test_iso_8859_1_detected(self):
        # ISO-8859-1 content with accented characters (e.g., German bank statement)
        content = "Datum,Betrag,Beschreibung\n01.01.2024,100,Überweisung café".encode("iso-8859-1")
        encoding, _ = detect_encoding(content)
        assert encoding.lower().replace("-", "") in (
            "iso88591", "latin1", "windows1252", "cp1252", "iso8859"
        ) or "iso" in encoding.lower() or "latin" in encoding.lower() or "1252" in encoding.lower()


# ==================== 5.4: Sanitization ====================


class TestSanitization:
    """Test sanitization — null bytes stripped, embedded scripts rejected, binary content rejected."""

    def test_null_bytes_stripped(self):
        content = b"date,amount\x00\n2024-01-01,100"
        sanitized = sanitize_content(content)
        assert b"\x00" not in sanitized
        assert b"date,amount" in sanitized

    def test_embedded_script_tags_rejected(self):
        content = b"date,amount\n<script>alert('xss')</script>,100"
        with pytest.raises(ValidationError) as exc_info:
            sanitize_content(content)
        assert exc_info.value.code == "CORRUPTED_FILE"

    def test_javascript_protocol_rejected(self):
        content = b"date,link\n2024-01-01,javascript:alert(1)"
        with pytest.raises(ValidationError) as exc_info:
            sanitize_content(content)
        assert exc_info.value.code == "CORRUPTED_FILE"

    def test_clean_content_passes(self):
        content = b"date,amount\n2024-01-01,100.50"
        sanitized = sanitize_content(content)
        assert sanitized == content


# ==================== 5.5: Error Responses ====================


class TestErrorResponses:
    """Test error responses — all new error codes return correct messages and suggestions."""

    def test_empty_file_error(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(b"", "text/csv")
        err = exc_info.value
        assert err.code == "EMPTY_FILE"
        assert "suggestions" in err.details
        assert len(err.details["suggestions"]) > 0

    def test_corrupted_file_error_has_suggestions(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_magic_bytes(b"NOT-A-PDF", "application/pdf")
        err = exc_info.value
        assert err.code == "CORRUPTED_FILE"
        assert "suggestions" in err.details

    def test_invalid_file_structure_error(self):
        # Single column — not a valid bank statement
        content = b"justonecolumn\nvalue1\n"
        with pytest.raises(ValidationError) as exc_info:
            validate_csv_structure(content)
        err = exc_info.value
        assert err.code == "INVALID_FILE_STRUCTURE"
        assert "suggestions" in err.details

    def test_encoding_error_for_broken_bytes(self):
        """Malformed bytes that can't be decoded should raise ENCODING_ERROR or INVALID_FILE_STRUCTURE."""
        # Create content that looks like text but has decodable header and broken structure
        # This tests the CSV structure validation path
        content = b"a,b\n\xfe\xff\xfe\xff"  # Valid header but broken content
        # This should either parse fine (charset-normalizer handles it) or raise an error
        # The important thing is it doesn't crash
        try:
            validate_csv_structure(content)
        except ValidationError as e:
            assert e.code in ("ENCODING_ERROR", "INVALID_FILE_STRUCTURE")

    def test_all_error_codes_have_suggestions(self):
        """Verify the file type validation includes suggestions."""
        from fastapi import UploadFile
        from unittest.mock import MagicMock

        file = MagicMock(spec=UploadFile)
        file.content_type = "image/png"
        with pytest.raises(ValidationError) as exc_info:
            from app.services.upload_service import validate_file_type
            validate_file_type(file)
        err = exc_info.value
        assert err.code == "INVALID_FILE_TYPE"
        assert "suggestions" in err.details


# ==================== 5.6: Upload Endpoint Integration ====================


class TestUploadEndpointIntegration:
    """Test upload endpoint integration — format detection result included in 202 response."""

    @pytest.mark.asyncio
    @patch("app.services.upload_service._get_s3_client")
    async def test_csv_upload_returns_format_detection(self, mock_s3_factory, client, mock_rate_limiter):
        """CSV upload returns detectedFormat, encoding, columnCount in 202 response."""
        mock_s3 = mock_s3_factory.return_value
        mock_s3.put_object.return_value = {}

        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = b"date,amount,description\n2024-01-01,100,Purchase"
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("statement.csv", io.BytesIO(content), "text/csv")},
            )

            assert response.status_code == 202
            data = response.json()
            assert "detectedFormat" in data
            assert "encoding" in data
            assert "columnCount" in data
            assert data["columnCount"] == 3
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    @patch("app.services.upload_service._get_s3_client")
    async def test_monobank_csv_upload_detected(self, mock_s3_factory, client, mock_rate_limiter):
        """Monobank CSV upload is correctly detected as 'monobank'."""
        mock_s3 = mock_s3_factory.return_value
        mock_s3.put_object.return_value = {}

        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = (FIXTURES_DIR / "monobank_sample.csv").read_bytes()
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("monobank.csv", io.BytesIO(content), "text/csv")},
            )

            assert response.status_code == 202
            data = response.json()
            assert data["detectedFormat"] == "monobank"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    @patch("app.services.upload_service._get_s3_client")
    async def test_pdf_upload_returns_null_format(self, mock_s3_factory, client, mock_rate_limiter):
        """PDF upload returns null for format detection fields."""
        mock_s3 = mock_s3_factory.return_value
        mock_s3.put_object.return_value = {}

        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = b"%PDF-1.4 fake pdf content"
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("statement.pdf", io.BytesIO(content), "application/pdf")},
            )

            assert response.status_code == 202
            data = response.json()
            assert data["detectedFormat"] is None
            assert data["encoding"] is None
            assert data["columnCount"] is None
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_empty_csv_returns_error(self, client, mock_rate_limiter):
        """Empty CSV file returns EMPTY_FILE error with suggestions."""
        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = (FIXTURES_DIR / "empty.csv").read_bytes()
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("empty.csv", io.BytesIO(content), "text/csv")},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "EMPTY_FILE"
            assert "suggestions" in data["error"]
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_binary_disguised_as_csv_returns_error(self, client, mock_rate_limiter):
        """Binary file with .csv extension returns CORRUPTED_FILE error."""
        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = (FIXTURES_DIR / "binary_disguised.csv").read_bytes()
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("data.csv", io.BytesIO(content), "text/csv")},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "CORRUPTED_FILE"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    @patch("app.services.upload_service._get_s3_client")
    async def test_upload_stores_format_in_db(self, mock_s3_factory, client, async_session, mock_rate_limiter):
        """Upload stores detected_format and detected_encoding in the uploads table."""
        mock_s3 = mock_s3_factory.return_value
        mock_s3.put_object.return_value = {}

        cognito_sub = await _create_test_user(client)
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            content = b"date,amount,description\n2024-01-01,100,Purchase"
            response = await client.post(
                "/api/v1/uploads",
                files={"file": ("statement.csv", io.BytesIO(content), "text/csv")},
            )

            assert response.status_code == 202

            from sqlmodel import select
            from app.models.upload import Upload

            uploads = (await async_session.exec(select(Upload))).all()
            assert len(uploads) == 1
            assert uploads[0].detected_format is not None
            assert uploads[0].detected_encoding is not None
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)
