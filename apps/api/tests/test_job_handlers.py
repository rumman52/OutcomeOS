# mypy: disable-error-code="no-untyped-call,no-untyped-def,unused-ignore"
import hashlib
import json
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from outcomeos_api.imports import CSV_V1_HEADERS, CsvLimits
from outcomeos_api.jobs.service import (
    Job,
    PermanentJobError,
    canonical_event_handler,
    csv_import_handler,
    reconciliation_handler,
)
from outcomeos_api.storage import ObjectHead, ObjectPage


class Result:
    def __init__(self, value=None):  # type: ignore[no-untyped-def]
        self.value = value

    def mappings(self) -> "Result":
        return self

    def one_or_none(self):  # type: ignore[no-untyped-def]
        return self.value


class Session:
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def __init__(self, values: list[object]) -> None:
        self.values = values

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def execute(self, query, _params=None):  # type: ignore[no-untyped-def]
        sql = str(query)
        if sql.startswith("SELECT") and "set_config" not in sql:
            return Result(self.values.pop(0))
        return Result()


def job() -> Job:
    return Job(uuid4(), uuid4(), uuid4(), "kind.v1", uuid4(), 1)


def canonical_payload() -> tuple[dict[str, object], bytes]:
    envelope = {"safe": True}
    digest = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    ).digest()
    return {"safe": True, "payload_digest": digest.hex()}, digest


def test_canonical_handler_accepts_verified_envelope() -> None:
    payload, digest = canonical_payload()
    canonical_event_handler(lambda: Session([{"payload": payload, "payload_digest": digest}]))(
        job()
    )


@pytest.mark.parametrize(
    "row,code",
    [
        (None, "canonical_event_missing"),
        ({"payload": "not-an-object", "payload_digest": b"x" * 32}, "canonical_envelope_invalid"),
        (
            {"payload": {"safe": True, "payload_digest": "0" * 64}, "payload_digest": b"x" * 32},
            "canonical_digest_invalid",
        ),
    ],
)
def test_canonical_handler_permanently_rejects_corrupt_records(row: object, code: str) -> None:
    with pytest.raises(PermanentJobError, match=code):
        canonical_event_handler(lambda: Session([row]))(job())


def csv_body() -> bytes:
    row = (
        "evt-1,order.created,2026-08-15T00:00:00Z,order,ord-1,true,false,"
        'purpose,{},{},100,USD,"{""safe"":true}"\n'
    )
    return ((",".join(CSV_V1_HEADERS)) + "\n" + row).encode()


class Storage:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, _tenant, _key):  # type: ignore[no-untyped-def]
        return self.body

    def head(self, _tenant, _key):  # type: ignore[no-untyped-def]
        return ObjectHead(len(self.body), hashlib.sha256(self.body).hexdigest())

    def put_if_absent(self, *_args):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def delete(self, *_args):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def test_csv_handler_verifies_digest_and_finishes_counts_idempotently() -> None:
    item = job()
    import_id = uuid4()
    body = csv_body()
    session = Session(
        [
            {"payload": {"import_id": str(import_id)}},
            {
                "object_key": "imports/file.csv",
                "object_digest": hashlib.sha256(body).digest(),
                "state": "uploaded",
            },
        ]
    )
    csv_import_handler(lambda: session, Storage(body), CsvLimits(10000, 10, 20, 1000))(item)
    assert session.values == []


def test_csv_handler_rejects_missing_control_and_digest_mismatch() -> None:
    item = job()
    handler = csv_import_handler(lambda: Session([None]), Storage(b""), CsvLimits(100, 10, 20, 10))
    with pytest.raises(PermanentJobError, match="csv_control_event_missing"):
        handler(item)
    import_id = uuid4()
    handler = csv_import_handler(
        lambda: Session(
            [
                {"payload": {"import_id": str(import_id)}},
                {"object_key": "file", "object_digest": b"x" * 32, "state": "uploaded"},
            ]
        ),
        Storage(csv_body()),
        CsvLimits(10000, 10, 20, 1000),
    )
    with pytest.raises(PermanentJobError, match="csv_digest_mismatch"):
        handler(item)


class ReconResult(Result):
    def scalars(self) -> "ReconResult":
        return self

    def all(self) -> list[object]:
        return list(self.value or [])

    def __iter__(self):
        return iter(self.value or [])


class ReconSession(Session):
    def __init__(self, run_id) -> None:  # type: ignore[no-untyped-def]
        super().__init__([])
        self.run_id = run_id

    def execute(self, query, _params=None):  # type: ignore[no-untyped-def]
        sql = str(query)
        if "SELECT payload FROM canonical_events" in sql:
            return ReconResult({"payload": {"run_id": str(self.run_id)}})
        return ReconResult([])


class ReconStorage(Storage):
    def list_page(self, _tenant, *, cursor=None, limit=100):  # type: ignore[no-untyped-def]
        assert cursor is None and limit == 100
        return ObjectPage((), None)


def test_reconciliation_completes_bounded_tenant_scan_with_safe_summary() -> None:
    run_id = uuid4()
    reconciliation_handler(lambda: ReconSession(run_id), ReconStorage(b""))(job())


def test_reconciliation_rejects_invalid_control_event() -> None:
    class Invalid(ReconSession):
        def execute(self, query, _params=None):  # type: ignore[no-untyped-def]
            if "SELECT payload FROM canonical_events" in str(query):
                return ReconResult({"payload": {}})
            return ReconResult([])

    with pytest.raises(PermanentJobError, match="reconciliation_control_invalid"):
        reconciliation_handler(lambda: Invalid(uuid4()), ReconStorage(b""))(job())
