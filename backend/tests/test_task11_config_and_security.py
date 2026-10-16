import pytest
import os
import re
import io
import logging
from types import SimpleNamespace
from pathlib import Path
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import SensitiveDataFilter, REDACTION_PATTERNS
from app.main import app, unhandled_exception_handler

client = TestClient(app)

def test_production_config_debug_must_be_false():
    """Production mode must reject DEBUG=True fail-fast."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DEBUG=True,
            FRONTEND_ORIGINS=["https://app.example.com"],
            POSTGRES_PASSWORD="safe-test-password",
            AI_PROVIDER="groq",
            GROQ_API_KEY="gsk_safe_test_key_1234567890",
        )
    assert "DEBUG không được bật trong môi trường production" in str(exc_info.value)

def test_production_config_rejects_wildcard_cors():
    """Production mode must strictly reject wildcard '*' in FRONTEND_ORIGINS."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DEBUG=False,
            FRONTEND_ORIGINS=["*"],
            POSTGRES_PASSWORD="safe-test-password",
            AI_PROVIDER="groq",
            GROQ_API_KEY="gsk_safe_test_key_1234567890",
        )
    assert "FRONTEND_ORIGINS không được dùng wildcard '*'" in str(exc_info.value)

def test_production_config_requires_groq_api_key_when_groq_provider():
    """Production mode with groq provider must fail-fast if GROQ_API_KEY is missing or placeholder."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DEBUG=False,
            FRONTEND_ORIGINS=["https://app.example.com"],
            POSTGRES_PASSWORD="safe-test-password",
            AI_PROVIDER="groq",
            GROQ_API_KEY=""
        )
    assert "GROQ_API_KEY phải được thiết lập" in str(exc_info.value)

def test_production_config_valid():
    """Valid production config succeeds cleanly."""
    cfg = Settings(
        APP_ENV="production",
        DEBUG=False,
        FRONTEND_ORIGINS=["https://app.example.com"],
        POSTGRES_PASSWORD="safe-test-password",
        AI_PROVIDER="groq",
        GROQ_API_KEY="gsk_safe_test_key_1234567890",
    )
    assert cfg.APP_ENV == "production"
    assert cfg.DEBUG is False
    assert cfg.FRONTEND_ORIGINS == ["https://app.example.com"]

@pytest.mark.parametrize("missing_field", ["FRONTEND_ORIGINS", "POSTGRES_PASSWORD", "AI_PROVIDER"])
def test_production_config_requires_explicit_fields(missing_field):
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DEBUG": False,
        "FRONTEND_ORIGINS": ["https://app.example.com"],
        "POSTGRES_PASSWORD": "safe-test-password",
        "AI_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_safe_test_key_1234567890",
    }
    values.pop(missing_field)
    with pytest.raises(ValidationError) as exc_info:
        Settings(**values)
    assert missing_field in str(exc_info.value)

def test_production_config_rejects_fake_provider():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APP_ENV="production",
            DEBUG=False,
            FRONTEND_ORIGINS=["https://app.example.com"],
            POSTGRES_PASSWORD="safe-test-password",
            AI_PROVIDER="fake",
        )
    assert "production chỉ hỗ trợ AI_PROVIDER='groq'" in str(exc_info.value)

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("POSTGRES_PASSWORD", "CHANGE_ME_TO_STRONG_PASSWORD"),
        ("GROQ_API_KEY", "gsk_your_real_groq_api_key_here"),
    ],
)
def test_production_config_rejects_placeholder_secrets(field, value):
    values = {
        "_env_file": None,
        "APP_ENV": "production",
        "DEBUG": False,
        "FRONTEND_ORIGINS": ["https://app.example.com"],
        "POSTGRES_PASSWORD": "safe-test-password",
        "AI_PROVIDER": "groq",
        "GROQ_API_KEY": "gsk_safe_test_key_1234567890",
    }
    values[field] = value
    with pytest.raises(ValidationError):
        Settings(**values)

def test_frontend_origins_parsing():
    """Comma-separated and JSON string FRONTEND_ORIGINS parse properly."""
    cfg1 = Settings(FRONTEND_ORIGINS="http://localhost:3000,https://app.example.com")
    assert cfg1.FRONTEND_ORIGINS == ["http://localhost:3000", "https://app.example.com"]

    cfg2 = Settings(FRONTEND_ORIGINS='["http://localhost:3000", "https://test.example.com"]')
    assert cfg2.FRONTEND_ORIGINS == ["http://localhost:3000", "https://test.example.com"]

def test_database_url_encodes_special_character_password():
    cfg = Settings(
        _env_file=None,
        POSTGRES_USER="special_user",
        POSTGRES_PASSWORD="p@ss/word%:safe",
        POSTGRES_HOST="postgres",
        POSTGRES_DB="special_db",
        DATABASE_URL=None,
    )
    url = cfg.get_database_url()
    assert "p%40ss%2Fword%25%3Asafe" in url
    assert "p@ss/word%:safe" not in url

def test_cors_preflight_allowed_origin():
    """CORS preflight request from allowed origin returns allow headers."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code in [200, 204]
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

def test_cors_preflight_disallowed_origin():
    """CORS preflight request from untrusted origin is not allowed."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://malicious-site.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.headers.get("access-control-allow-origin") != "https://malicious-site.com"

def test_sensitive_data_log_filter():
    """Sensitive data filter redacts API keys, tokens, and passwords."""
    filter_obj = SensitiveDataFilter()
    
    import logging
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Error calling Groq with key gsk_1234567890abcdef1234567890 and password=supersecretpass",
        args=(),
        exc_info=None
    )
    filter_obj.filter(record)
    assert "gsk_1234567890abcdef1234567890" not in record.msg
    assert "[REDACTED_GROQ_API_KEY]" in record.msg
    assert "supersecretpass" not in record.msg

def test_sensitive_data_filter_redacts_formatted_exception():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SensitiveDataFilter())
    logger = logging.getLogger("task11.exception-redaction")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    try:
        try:
            raise RuntimeError(
                "gsk_1234567890abcdef Bearer secret_token_123456789 "
                "password=supersecret postgresql://user:dbsecret@db/app"
            )
        except RuntimeError:
            logger.exception("Provider crashed")
    finally:
        logger.removeHandler(handler)

    output = stream.getvalue()
    for secret in ("gsk_1234567890abcdef", "secret_token_123456789", "supersecret", "dbsecret"):
        assert secret not in output
    assert "[REDACTED" in output

def test_unhandled_exception_returns_safe_json(monkeypatch):
    """The real global handler must not log or return the raw exception."""
    secret_marker = "RAW_SECRET_PATH_/secret/db"
    request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/boom"))
    captured = []
    monkeypatch.setattr(
        "app.main.logger.error",
        lambda message, *args, **kwargs: captured.append((message, args, kwargs)),
    )
    coroutine = unhandled_exception_handler(request, RuntimeError(secret_marker))
    with pytest.raises(StopIteration) as completed:
        coroutine.send(None)
    response = completed.value.value

    assert response.status_code == 500
    body = response.body.decode("utf-8")
    assert body == '{"detail":"Lỗi hệ thống nội bộ. Vui lòng thử lại sau."}'
    assert secret_marker not in body
    assert secret_marker not in repr(captured)
    assert "RuntimeError" in repr(captured)
    assert all("exc_info" not in kwargs for _, _, kwargs in captured)

def test_health_endpoints():
    """Health endpoints return standard healthy status without sensitive credentials."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "API is healthy"}

def test_dockerignore_protects_env_and_venv():
    """Backend .dockerignore strictly ignores .env and .venv."""
    dockerignore_path = Path(__file__).resolve().parent.parent / ".dockerignore"
    assert dockerignore_path.exists()
    content = dockerignore_path.read_text(encoding="utf-8")
    assert ".venv" in content
    assert ".env" in content
