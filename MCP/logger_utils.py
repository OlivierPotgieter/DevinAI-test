import json
import logging
import inspect
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Mapping

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv:
    load_dotenv()

# Allow overriding the log directory via environment variable.
_default_dir = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR = Path(os.getenv("MCP_LOG_DIR", _default_dir))
LOG_FILE = LOG_DIR / "app.log"

SENSITIVE_KEYS = {"token", "secret", "api_key", "access_token"}


def get_logger() -> logging.Logger:
    """Return a singleton logger writing to LOG_FILE in JSON lines."""
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("mcp_logger")
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger()


def _redact(value: Any) -> Any:
    """Recursively redact sensitive fields in mappings."""
    if isinstance(value, Mapping):
        return {
            k: "[REDACTED]" if k.lower() in SENSITIVE_KEYS else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def log_call(name: str, request: Any, response: Any) -> None:
    """Log a request/response pair in JSON format with redaction."""
    frame = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": module.__name__ if module else "__main__",
        "name": name,
        "request": _redact(request),
        "response": _redact(response),
    }
    logger.info(json.dumps(entry))
