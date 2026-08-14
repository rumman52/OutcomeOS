from unittest.mock import MagicMock

import pytest

from outcomeos_api.config import Settings
from outcomeos_api.worker import build_runner, main, run_once


def test_build_runner_registers_all_durable_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("outcomeos_api.worker.create_database_engine", lambda _url: MagicMock())
    monkeypatch.setattr("outcomeos_api.worker.create_session_factory", lambda _engine: object())
    monkeypatch.setattr("outcomeos_api.worker.S3ObjectStorage", lambda **_kwargs: MagicMock())
    runner = build_runner(Settings(app_env="test"))
    assert set(runner.handlers) == {
        "ingest.canonical_event.v1",
        "ingest.csv.v1",
        "reconcile.tenant.v1",
    }


def test_run_once_refuses_non_postgresql_worker() -> None:
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        run_once(Settings(app_env="test", persistence_backend="json_sandbox"))


def test_run_once_executes_built_postgresql_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = MagicMock()
    runner.run_once.return_value = 4
    monkeypatch.setattr("outcomeos_api.worker.build_runner", lambda _settings: runner)
    assert run_once(Settings(app_env="test")) == 4


def test_worker_cli_once_exits_after_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock()
    monkeypatch.setattr("outcomeos_api.worker.get_settings", lambda: Settings(app_env="test"))
    monkeypatch.setattr("outcomeos_api.worker.build_runner", lambda _settings: runner)
    monkeypatch.setattr("sys.argv", ["outcomeos-worker", "--once"])
    main()
    runner.run_once.assert_called_once_with()
