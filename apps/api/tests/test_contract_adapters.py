from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from outcomeos_api.config import Settings
from outcomeos_api.contracts import api
from outcomeos_api.contracts.repositories import ContractRepository
from outcomeos_api.db import AuthenticatedPrincipal


class Chained:
    def __init__(self, value: object) -> None:
        self.value = value

    def mappings(self) -> Chained:
        return self

    def one_or_none(self) -> object:
        return self.value

    def all(self) -> object:
        return self.value


def test_repository_scopes_queries_and_records_actor_and_time() -> None:
    session = MagicMock()
    tenant, identifier = uuid4(), uuid4()
    repository = ContractRepository(session, tenant)
    session.execute.return_value = Chained({"id": identifier})
    assert dict(cast(Any, repository.one("performance_contracts", identifier))) == {
        "id": identifier
    }
    assert dict(
        cast(
            Any,
            repository.version("performance_contract_versions", "contract_id", identifier, uuid4()),
        )
    ) == {"id": identifier}
    with pytest.raises(ValueError):
        repository.one("users", identifier)
    with pytest.raises(ValueError):
        repository.version("users", "id", identifier, identifier)

    session.execute.return_value = Chained([{"id": identifier}])
    assert len(repository.list("outcome_rules", after=None, limit=10)) == 1
    assert len(repository.bindings(identifier)) == 1
    session.execute.return_value = Chained({"state": "active"})
    assert dict(cast(Any, repository.lock_contract(identifier))) == {"state": "active"}

    session.execute.return_value = Chained(None)
    assert repository.command_result("key", "digest") is None
    session.execute.return_value = Chained({"request_digest": "digest", "response": {"ok": 1}})
    assert repository.command_result("key", "digest") == {"ok": 1}
    with pytest.raises(ValueError, match="idempotency_conflict"):
        repository.command_result("key", "other")
    repository.remember("key", "digest", {"ok": 1})
    repository.record(
        event_type="contract_created",
        aggregate_type="performance_contract",
        aggregate_id=identifier,
        actor_id=uuid4(),
        actor_type="api_key",
        metadata={"new_state": "draft", "raw_payload": "must-not-persist"},
    )
    audit_params = session.execute.call_args_list[-2].args[1]
    outbox_params = session.execute.call_args_list[-1].args[1]
    assert audit_params["now"].tzinfo is UTC
    assert "raw_payload" not in audit_params["metadata"]
    assert outbox_params["actor_type"] == "api_key"


class Session:
    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class Service:
    def __init__(self, _session: object, _principal: object, *, actor_type: str) -> None:
        self.actor_type = actor_type

    def __getattr__(self, name: str) -> Callable[..., dict[str, object]]:
        def call(*args: object, **kwargs: object) -> dict[str, object]:
            return {
                "operation": name,
                "args": [str(value) for value in args],
                "actor_type": self.actor_type,
                **kwargs,
            }

        return call


class Repository:
    def __init__(self, _session: object, _tenant: UUID) -> None:
        pass

    def list(self, table: str, **_kwargs: object) -> Sequence[dict[str, str]]:
        return [{"table": table}]

    def one(self, table: str, _identifier: UUID) -> dict[str, str] | None:
        return None if table == "missing" else {"table": table}

    def version(self, table: str, *_args: object) -> dict[str, str]:
        return {"table": table}

    def bindings(self, _identifier: UUID) -> Sequence[dict[str, str]]:
        return [{"source_id": "one"}]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    monkeypatch.setattr(api, "principal_for_api_key", lambda *_args, **_kwargs: principal)
    monkeypatch.setattr(api, "ContractService", Service)
    monkeypatch.setattr(api, "ContractRepository", Repository)

    @contextmanager
    def transaction(session: object, _principal: object) -> Iterator[object]:
        yield session

    monkeypatch.setattr(api, "tenant_transaction", transaction)
    application = FastAPI()
    application.include_router(api.contracts_router(Settings(app_env="test"), Session))
    return TestClient(application)


def headers() -> dict[str, str]:
    return {"Authorization": "Bearer oos_live_programmatic", "Idempotency-Key": "key"}


def version_body() -> dict[str, object]:
    return {
        "display_name": "Agreement",
        "required_party_roles": ["buyer"],
        "rule_version_id": str(uuid4()),
        "contract_timezone": "UTC",
        "currency": "USD",
        "pricing_model": "fixed_fee",
        "fixed_fee_minor": 100,
        "anchor_event_type": "order.paid",
        "attribution_window_seconds": 1,
        "evaluation_window_seconds": 1,
        "finalization_window_seconds": 1,
        "effective_start": datetime.now(UTC).isoformat(),
        "terms": {},
    }


def test_api_mutation_routes_and_api_key_authority_denial(client: TestClient) -> None:
    contract, version, rule, rule_version = (uuid4() for _ in range(4))
    requests = [
        ("/api/v1/contracts", None),
        (f"/api/v1/contracts/{contract}/versions", version_body()),
        (f"/api/v1/contracts/{contract}/versions/{version}/propose", None),
        (f"/api/v1/contracts/{contract}/versions/{version}/activate", None),
        (f"/api/v1/contracts/{contract}/suspend", None),
        ("/api/v1/outcome-rules", {"name": "Rule"}),
        (
            f"/api/v1/outcome-rules/{rule}/versions",
            {"template_id": "qualified_lead_accepted", "definition": {}},
        ),
        (f"/api/v1/outcome-rules/{rule}/versions/{rule_version}/publish", None),
        (
            f"/api/v1/contracts/{contract}/source-bindings",
            {
                "source_type": "shop",
                "source_id": "one",
                "effective_start": datetime.now(UTC).isoformat(),
            },
        ),
    ]
    for path, body in requests:
        response = client.post(path, headers=headers(), json=body)
        assert response.status_code in {200, 201}, response.text
        assert response.json()["actor_type"] == "api_key"
    denied = client.post(
        f"/api/v1/contracts/{contract}/party-authorities",
        headers=headers(),
        json={"party_role": "buyer", "principal_id": str(uuid4())},
    )
    assert denied.status_code == 403


def test_api_reads_pagination_validation_and_auth_denial(client: TestClient) -> None:
    contract, version, rule = uuid4(), uuid4(), uuid4()
    for path in (
        "/api/v1/contracts?limit=10",
        f"/api/v1/contracts/{contract}",
        f"/api/v1/contracts/{contract}/versions/{version}",
        "/api/v1/outcome-rules?limit=10",
        f"/api/v1/outcome-rules/{rule}",
        f"/api/v1/outcome-rules/{rule}/versions/{version}",
        f"/api/v1/contracts/{contract}/source-bindings",
    ):
        assert client.get(path, headers=headers()).status_code == 200
    assert client.get("/api/v1/contracts?limit=101", headers=headers()).status_code == 422
    assert client.get("/api/v1/contracts").status_code == 403
