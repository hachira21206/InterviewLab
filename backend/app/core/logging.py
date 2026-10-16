import logging
import re
import traceback
from typing import Any

# Sensitive patterns to redact from all log streams
REDACTION_PATTERNS = [
    (re.compile(r"gsk_[a-zA-Z0-9_\-]{10,}", re.IGNORECASE), "[REDACTED_GROQ_API_KEY]"),
    (re.compile(r"AIza[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED_GEMINI_API_KEY]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password|secret|token)\s*[:=]\s*['\"]?[^\s'\",]+['\"]?", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"postgresql(?:\+[a-zA-Z0-9_]+)?://([^:]+):([^@]+)@", re.IGNORECASE), r"postgresql://\1:[REDACTED_PASSWORD]@"),
]

def redact_sensitive_text(value: str) -> str:
    for pattern, replacement in REDACTION_PATTERNS:
        value = pattern.sub(replacement, value)
    return value

class SensitiveDataFilter(logging.Filter):
    """
    Log filter that masks sensitive credentials such as API keys,
    passwords, and authorization tokens before records are written.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        
        if record.args:
            if isinstance(record.args, dict):
                cleaned_dict = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        v = redact_sensitive_text(v)
                    cleaned_dict[k] = v
                record.args = cleaned_dict
            elif isinstance(record.args, (list, tuple)):
                new_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        arg = redact_sensitive_text(arg)
                    new_args.append(arg)
                record.args = tuple(new_args) if isinstance(record.args, tuple) else new_args

        # Formatter normally renders exc_info after filters have run, which would
        # bypass message/argument redaction. Render it here, sanitize it, and
        # remove the raw exception tuple before any handler can emit it.
        if record.exc_info:
            rendered_exception = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = redact_sensitive_text(rendered_exception)
            record.exc_info = None

        return True

class HealthCheckFilter(logging.Filter):
    """
    Silences noisy repetitive health check requests from uvicorn access logs.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "/api/v1/health" in msg:
            return False
        return True

def setup_logging(debug: bool = False):
    """
    Configures standard production-ready structured logging.
    """
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Attach sensitive data filter to all handlers
    sensitive_filter = SensitiveDataFilter()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(sensitive_filter)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.addFilter(sensitive_filter)
        root_logger.addHandler(handler)

    # Silence health check spam in uvicorn access log
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(HealthCheckFilter())
