from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from outcomeos_api.contracts.service import ContractCommandError, ContractService
from outcomeos_api.db import AuthenticatedPrincipal


class Repo:
    def __init__(self) -> None:
        self.prior: dict[str, object] | None = None
        self.conflict = False
        self.aggregate: dict[str, object] | None = {"id": uuid4()}
        self.locked: dict[str, object] | None = {"state": "active", "lock_version": 2}
        self.version_row: dict[str, object] | None = None
        self.records: list[dict[str, object]] = []
        self.remembered: list[tuple[str, str, dict[str, object]]] = []

    def command_result(self, _key: str, _digest: str) -> dict[str, object] | None:
        if self.conflict:
            raise ValueError
        return self.prior

    def remember(self, key: str, digest: str, response: dict[str, object]) -> None:
        self.remembered.append((key, digest, response))

    def record(self, **values: object) -> None:
        self.records.append(values)

    def one(self, _table: str, _identifier: UUID) -> dict[str, object] | None:
        return self.aggregate

    def lock_contract(
        self, _identifier: UUID, _lock: int | None = None
    ) -> dict[str, object] | None:
        return self.locked

    def version(self, *_args: object) -> dict[str, object] | None:
        return self.version_row


def result(*, scalar: object = None, scalars: list[object] | None = None) -> MagicMock:
    value = MagicMock()
    value.scalar_one.return_value = scalar
    value.scalar_one_or_none.return_value = scalar
    value.scalars.return_value = scalars or []
    return value


@pytest.fixture
def service() -> ContractService:
    session = MagicMock()
    principal = AuthenticatedPrincipal(uuid4(), uuid4(), uuid4())
    value = ContractService(session, principal, actor_type="api_key")
    value.repo = cast(Any, Repo())
    return value


def test_idempotent_commands_and_conflict(service: ContractService) -> None:
    repo = service.repo
    assert isinstance(repo, Repo)
    repo.prior = {"id": "original"}
    assert service.create_contract("key") == {"id": "original"}
    cast(Any, service.session).execute.assert_not_called()
    repo.prior = None
    created = service.create_contract("new")
    assert created["state"] == "draft"
    assert repo.records[-1]["actor_type"] == "api_key"
    repo.conflict = True
    with pytest.raises(ContractCommandError, match="idempotency_conflict"):
        service.create_contract("new")


def test_rule_lifecycle_and_validation(service: ContractService) -> None:
    repo = service.repo
    assert isinstance(repo, Repo)
    assert service.create_rule("rule", "Qualified")["name"] == "Qualified"
    service.session.execute.return_value = result(scalar=1)
    rule_id = uuid4()
    draft = service.create_rule_version(
        "version",
        rule_id,
        {"template_id": "qualified_lead_accepted", "definition": {"schema_version": 1}},
    )
    assert draft["version"] == 1
    with pytest.raises(ContractCommandError, match="invalid_rule_definition"):
        service.create_rule_version(
            "bad",
            rule_id,
            {"template_id": "qualified_lead_accepted", "definition": {"secret": "x"}},
        )
    repo.version_row = {
        "state": "draft",
        "definition": {"schema_version": 1},
        "version": 1,
        "template_id": "qualified_lead_accepted",
    }
    assert service.transition_rule("publish", rule_id, uuid4(), "publish")["state"] == "published"
    repo.version_row = {
        "state": "published",
        "definition": {"schema_version": 1},
        "version": 1,
        "template_id": "qualified_lead_accepted",
    }
    assert service.transition_rule("retire", rule_id, uuid4(), "retire")["state"] == "retired"
    repo.version_row = {"state": "retired", "definition": {}, "version": 1}
    with pytest.raises(ContractCommandError, match="invalid_lifecycle"):
        service.transition_rule("again", rule_id, uuid4(), "retire")


def contract_body() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "display_name": "Agreement",
        "description": None,
        "required_party_roles": ["buyer"],
        "rule_version_id": uuid4(),
        "contract_timezone": "UTC",
        "currency": "USD",
        "pricing_model": "fixed_fee",
        "fixed_fee_minor": 100,
        "rate_basis_points": None,
        "floor_minor": None,
        "cap_minor": None,
        "anchor_event_type": "order.paid",
        "attribution_window_seconds": 1,
        "evaluation_window_seconds": 2,
        "finalization_window_seconds": 3,
        "effective_start": now,
        "effective_end": now + timedelta(days=1),
        "terms": {"schema_version": 1},
    }


def test_contract_version_validation_and_creation(service: ContractService) -> None:
    cast(Any, service.session).execute.side_effect = [
        result(scalar="published"),
        result(scalar=1),
        result(),
    ]
    created = service.create_contract_version("v", uuid4(), contract_body())
    assert created["version"] == 1
    for field, value in (("currency", "ZZZ"), ("contract_timezone", "Mars/Nowhere")):
        body = contract_body()
        body[field] = value
        with pytest.raises(ContractCommandError, match="invalid_contract_terms"):
            service.create_contract_version(field, uuid4(), body)
    body = contract_body()
    body["fixed_fee_minor"] = 0
    with pytest.raises(ContractCommandError, match="invalid_contract_terms"):
        service.create_contract_version("price", uuid4(), body)


def test_contract_version_lifecycle_authority_and_api_key_denial(service: ContractService) -> None:
    repo = service.repo
    assert isinstance(repo, Repo)
    version_id, contract_id = uuid4(), uuid4()
    terms = {"schema_version": 1}
    repo.version_row = {
        "state": "draft",
        "terms": terms,
        "digest": None,
        "version": 1,
        "required_party_roles": ["buyer"],
    }
    proposed = service.transition_contract_version("p", contract_id, version_id, "propose")
    digest = proposed["digest"]
    repo.version_row = {
        "state": "proposed",
        "terms": terms,
        "digest": digest,
        "version": 1,
        "required_party_roles": ["buyer"],
    }
    with pytest.raises(ContractCommandError, match="human_principal_required"):
        service.transition_contract_version(
            "a",
            contract_id,
            version_id,
            "accept",
            digest=str(digest),
            party_role="buyer",
            human=False,
        )
    service.session.execute.return_value = result(scalar=1)
    accepted = service.transition_contract_version(
        "human",
        contract_id,
        version_id,
        "accept",
        digest=str(digest),
        party_role="buyer",
        human=True,
    )
    assert accepted["digest"] == digest
    service.session.execute.return_value = result(scalars=["buyer"])
    assert (
        service.transition_contract_version("active", contract_id, version_id, "activate")["state"]
        == "active"
    )


def test_contract_state_authority_and_binding_commands(service: ContractService) -> None:
    repo = service.repo
    assert isinstance(repo, Repo)
    contract_id = uuid4()
    assert service.transition_contract("s", contract_id, "suspend", 2)["state"] == "suspended"
    repo.locked = {"state": "suspended", "lock_version": 3}
    assert service.transition_contract("r", contract_id, "resume", 3)["state"] == "active"
    authority = service.provision_authority("grant", contract_id, "buyer", uuid4())
    assert authority["party_role"] == "buyer"
    now = datetime.now(UTC)
    binding = service.create_binding(
        "binding",
        contract_id,
        {
            "source_type": "shop",
            "source_id": "canonical-1",
            "effective_start": now,
            "effective_end": None,
        },
    )
    assert binding["source_id"] == "canonical-1"
    repo.locked = None
    with pytest.raises(ContractCommandError, match="concurrency_conflict"):
        service.transition_contract("conflict", contract_id, "terminate", 99)
