# mypy: disable-error-code="no-untyped-def,unused-ignore"
# ruff: noqa: E501
from uuid import uuid4

import pytest

from outcomeos_api.jobs import Job, JobRunner, PermanentJobError, RetryableJobError


class _Mappings:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> "_Mappings":
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _Bind:
    class dialect:
        name = "sqlite"


class _Session:
    bind = _Bind()

    def __init__(self, rows: list[dict[str, object]], calls: list[dict[str, object]]) -> None:
        self.rows, self.calls = rows, calls

    def __enter__(self) -> "_Session":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> "_Session":
        return self

    def execute(self, _query: object, params: dict[str, object] | None = None) -> _Mappings:
        if params and "outcome" in params:
            self.calls.append(params)
            return _Mappings([])
        rows, self.rows = self.rows, []
        return _Mappings(rows)


def test_backoff_is_deterministic_and_bounded() -> None:
    runner = JobRunner(
        object(), lease_seconds=30, batch_size=4, max_attempts=5, backoff_base=3, backoff_max=10
    )
    assert [runner.backoff(n) for n in range(1, 6)] == [3, 6, 10, 10, 10]


def test_registry_denies_duplicate_kinds() -> None:
    runner = JobRunner(
        object(), lease_seconds=30, batch_size=4, max_attempts=5, backoff_base=3, backoff_max=10
    )
    runner.register("safe.v1", lambda _job: None)
    with pytest.raises(ValueError, match="unique"):
        runner.register("safe.v1", lambda _job: None)


def test_job_errors_expose_only_safe_codes() -> None:
    assert RetryableJobError("storage_unavailable").code == "storage_unavailable"
    assert PermanentJobError("unsupported_job_kind").code == "unsupported_job_kind"
    job = Job(uuid4(), uuid4(), uuid4(), "safe.v1", uuid4(), 1)
    assert job.attempt_count == 1


@pytest.mark.parametrize(
    "handler,attempt,outcome,error",
    [
        (lambda _job: None, 1, "succeeded", None),
        (
            lambda _job: (_ for _ in ()).throw(PermanentJobError("bad_input")),
            1,
            "dead",
            "bad_input",
        ),
        (
            lambda _job: (_ for _ in ()).throw(RetryableJobError("temporary")),
            1,
            "retry",
            "temporary",
        ),
        (
            lambda _job: (_ for _ in ()).throw(RetryableJobError("temporary")),
            3,
            "dead",
            "temporary",
        ),
        (
            lambda _job: (_ for _ in ()).throw(RuntimeError("private")),
            1,
            "retry",
            "handler_failure",
        ),
    ],
)
def test_runner_classifies_and_sanitizes_handler_outcomes(
    handler,
    attempt: int,
    outcome: str,
    error: str | None,  # type: ignore[no-untyped-def]
) -> None:
    ids = [uuid4() for _ in range(4)]
    rows = [
        {
            "id": ids[0],
            "tenant_id": ids[1],
            "event_id": ids[2],
            "kind": "safe.v1",
            "lease_token": ids[3],
            "attempt_count": attempt,
        }
    ]
    calls: list[dict[str, object]] = []
    sessions = lambda: _Session(rows, calls)  # noqa: E731
    runner = JobRunner(
        sessions, lease_seconds=30, batch_size=1, max_attempts=3, backoff_base=2, backoff_max=8
    )
    runner.register("safe.v1", handler)
    assert runner.run_once() == 1
    assert calls[0]["outcome"] == outcome
    assert calls[0]["error"] == error


def test_runner_dead_letters_unregistered_job_kind() -> None:
    ids = [uuid4() for _ in range(4)]
    rows = [
        {
            "id": ids[0],
            "tenant_id": ids[1],
            "event_id": ids[2],
            "kind": "unknown.v1",
            "lease_token": ids[3],
            "attempt_count": 1,
        }
    ]
    calls: list[dict[str, object]] = []
    runner = JobRunner(
        lambda: _Session(rows, calls),
        lease_seconds=30,
        batch_size=1,
        max_attempts=3,
        backoff_base=2,
        backoff_max=8,
    )
    assert runner.run_once() == 1
    assert calls[0]["outcome"] == "dead"
    assert calls[0]["error"] == "unsupported_job_kind"
