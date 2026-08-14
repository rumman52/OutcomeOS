from uuid import uuid4

import pytest

from outcomeos_api.jobs import Job, JobRunner, PermanentJobError, RetryableJobError


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
