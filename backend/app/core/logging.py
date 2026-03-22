import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """JSON log formatter that includes extra fields for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, str] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured extra fields (used by tenant.py security logging)
        for key in ("action", "user_id", "resource_type", "resource_id", "ip", "event"):
            value = getattr(record, key, None)
            if value is not None:
                log_data[key] = value

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> None:
    """Configure JSON structured logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)
    app_logger.propagate = False
