import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from app.core.config import settings

def test_alembic_config_with_special_characters(monkeypatch):
    monkeypatch.setattr(settings, "POSTGRES_PASSWORD", "my@pass/word%test")
    monkeypatch.setattr(settings, "DATABASE_URL", None)
    
    # We will mock alembic.context so we can import env.py safely
    mock_context = MagicMock()
    mock_config = MagicMock()
    mock_config.get_main_option.return_value = "dummy"
    mock_context.config = mock_config
    mock_context.is_offline_mode.return_value = True
    mock_config.config_file_name = None

    # Capture what env.py sets in config.set_main_option
    set_options = {}
    def mock_set_main_option(name, value):
        set_options[name] = value
    mock_config.set_main_option = mock_set_main_option
    
    sys.modules.pop('migrations.env', None)
    with patch.dict('sys.modules', {'alembic': MagicMock(context=mock_context)}):
        from migrations import env

    # Verify that sqlalchemy.url is set correctly
    url_value = set_options.get("sqlalchemy.url")
    assert url_value is not None, "sqlalchemy.url was not set"
    
    # Ensure % is escaped to %% so ConfigParser won't crash
    # And password is url-encoded by SQLAlchemy!
    expected_encoded = "my%%40pass%%2Fword%%25test"
    assert expected_encoded in url_value
    
    # Let's actually test it with a real ConfigParser to prove it parses correctly!
    from configparser import ConfigParser
    parser = ConfigParser()
    parser.add_section("alembic")
    parser.set("alembic", "sqlalchemy.url", url_value)
    
    # This read should NOT raise InterpolationSyntaxError
    parsed_url = parser.get("alembic", "sqlalchemy.url")
    assert "my%40pass%2Fword%25test" in parsed_url
    assert parsed_url == url_value.replace("%%", "%")
