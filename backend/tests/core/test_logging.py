"""Tests for structured JSON logging (Story 6.4)."""

import json
import logging

from app.core.logging import JsonFormatter


def _make_record(**extras) -> logging.LogRecord:
    """Create a LogRecord with optional extra fields set as attributes."""
    record = logging.LogRecord(
        name="app.tasks.processing_tasks",
        level=logging.INFO,
        pathname="processing_tasks.py",
        lineno=52,
        msg="test message",
        args=(),
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return record


class TestJsonFormatterExtraFields:
    """Task 1.1: JsonFormatter captures ALL extra fields, not just hardcoded ones."""

    def test_captures_job_id(self):
        formatter = JsonFormatter()
        record = _make_record(job_id="abc-123")
        output = json.loads(formatter.format(record))
        assert output["job_id"] == "abc-123"

    def test_captures_step(self):
        formatter = JsonFormatter()
        record = _make_record(step="categorization")
        output = json.loads(formatter.format(record))
        assert output["step"] == "categorization"

    def test_captures_duration_ms(self):
        formatter = JsonFormatter()
        record = _make_record(duration_ms=1234)
        output = json.loads(formatter.format(record))
        assert output["duration_ms"] == 1234

    def test_captures_multiple_extra_fields(self):
        formatter = JsonFormatter()
        record = _make_record(job_id="j1", step="education", duration_ms=500)
        output = json.loads(formatter.format(record))
        assert output["job_id"] == "j1"
        assert output["step"] == "education"
        assert output["duration_ms"] == 500

    def test_excludes_builtin_logrecord_attrs(self):
        """Standard LogRecord builtins (args, lineno, filename) must NOT appear in JSON."""
        formatter = JsonFormatter()
        record = _make_record()
        output = json.loads(formatter.format(record))
        for builtin in ("args", "lineno", "filename", "funcName", "processName", "threadName"):
            assert builtin not in output, f"Builtin '{builtin}' should not be in JSON output"

    def test_excludes_private_attrs(self):
        """Attributes starting with _ should not appear in JSON."""
        formatter = JsonFormatter()
        record = _make_record(_internal="secret")
        output = json.loads(formatter.format(record))
        assert "_internal" not in output


class TestJsonFormatterServiceField:
    """Task 1.2: service field derived from record.name."""

    def test_service_present_in_output(self):
        formatter = JsonFormatter()
        record = _make_record()
        output = json.loads(formatter.format(record))
        assert "service" in output

    def test_service_strips_app_prefix_and_module(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="app.agents.categorization.node",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["service"] == "agents.categorization"

    def test_service_api_path(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="app.api.v1.uploads",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["service"] == "api.v1"

    def test_service_tasks_path(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="app.tasks.processing_tasks",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["service"] == "tasks"

    def test_service_non_app_prefix(self):
        """If record.name doesn't start with 'app.', use as-is."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="celery.worker",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        output = json.loads(formatter.format(record))
        assert output["service"] == "celery.worker"


class TestJsonFormatterExcInfo:
    """exc_info is serialized as 'exception' string."""

    def test_exc_info_serialized_as_exception_string(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = _make_record()
            record.exc_info = sys.exc_info()

        output = json.loads(formatter.format(record))
        assert "exception" in output
        assert isinstance(output["exception"], str)
        assert "ValueError" in output["exception"]
        assert "test error" in output["exception"]


class TestJsonFormatterBaseFields:
    """Verify standard base fields are always present."""

    def test_has_timestamp(self):
        formatter = JsonFormatter()
        record = _make_record()
        output = json.loads(formatter.format(record))
        assert "timestamp" in output

    def test_has_level(self):
        formatter = JsonFormatter()
        record = _make_record()
        output = json.loads(formatter.format(record))
        assert output["level"] == "INFO"

    def test_has_message(self):
        formatter = JsonFormatter()
        record = _make_record()
        output = json.loads(formatter.format(record))
        assert output["message"] == "test message"
