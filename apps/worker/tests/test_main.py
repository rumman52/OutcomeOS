from unittest.mock import MagicMock, patch

from outcomeos_worker.main import Settings, check_database


def test_default_database_url_does_not_embed_credentials() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql://localhost:5432/outcomeos"


def test_check_database_executes_probe() -> None:
    connection = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = connection
    with patch("outcomeos_worker.main.psycopg.connect", return_value=context) as connect:
        check_database("postgresql://example")
    connect.assert_called_once_with("postgresql://example", connect_timeout=2)
    connection.execute.assert_called_once_with("SELECT 1")
