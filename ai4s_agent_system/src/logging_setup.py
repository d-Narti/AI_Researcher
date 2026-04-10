import logging
import json
import os
from typing import Optional
from datetime import datetime, timezone

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# Set LOG_FORMAT=json in environment to enable structured JSON logging
LOG_FORMAT_TYPE = os.getenv("LOG_FORMAT", "text").lower()

TEXT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for production/observability use."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        # Optional structured fields attached via LoggerAdapter or extra={}
        for field in ("request_id", "task_id", "agent", "step"):
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """Configure root logging once and return a module-specific logger.

    Supports two output formats controlled by the LOG_FORMAT env var:
      - text (default): human-readable, suitable for local development
      - json: structured JSON lines, suitable for log aggregation (Loki, CloudWatch, etc.)
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if LOG_FORMAT_TYPE == "json":
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter(TEXT_FORMAT))
        root.addHandler(handler)
        root.setLevel(LOG_LEVEL)
    return logging.getLogger(name or __name__)
