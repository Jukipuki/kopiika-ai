import json
import logging
import sys
from datetime import UTC, datetime

# Standard LogRecord attributes to exclude from extra field capture
_LOG_RECORD_BUILTIN_ATTRS: frozenset[str] = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
})


class JsonFormatter(logging.Formatter):
    """JSON log formatter that includes extra fields for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        # Derive service from logger name: strip "app." prefix, drop module filename
        # e.g. "app.agents.categorization.node" → "agents.categorization"
        name = record.name
        if name.startswith("app."):
            service = name[4:].rsplit(".", 1)[0]
        else:
            service = name

        log_data: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": service,
            "message": record.getMessage(),
        }

        # Capture all extra fields passed via extra={} — exclude builtins and private attrs
        for key, value in record.__dict__.items():
            if key not in _LOG_RECORD_BUILTIN_ATTRS and not key.startswith("_"):
                if key not in log_data:
                    log_data[key] = value

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """Configure JSON structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)
    app_logger.propagate = False
