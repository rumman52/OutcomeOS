from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from outcomeos_api.contracts.domain import (
    BasisPoints,
    ContractState,
    ContractVersion,
    EffectiveCandidate,
    FixedFee,
    RuleVersion,
    VersionState,
    document_digest,
    select_effective_contract,
    validate_timezone,
)
from outcomeos_api.domain import DomainError

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def test_canonical_digest_is_key_order_independent_and_change_sensitive() -> None:
    assert document_digest({"a": 1, "b": [2]}) == document_digest({"b": [2], "a": 1})
    assert document_digest({"a": 1}) != document_digest({"a": 2})


@pytest.mark.parametrize("value", [0, -1, 1.2, True])
def test_fixed_fee_rejects_non_positive_or_non_integer_values(value: object) -> None:
    with pytest.raises(DomainError):
        FixedFee(value, "USD")  # type: ignore[arg-type]


def test_basis_points_boundaries_and_floor_cap() -> None:
    assert BasisPoints(1, "usd").currency == "USD"
    assert BasisPoints(10_000, "USD", 0, 100).cap_minor == 100
    for value in (0, 10_001, 1.5):
        with pytest.raises(DomainError):
            BasisPoints(value, "USD")  # type: ignore[arg-type]
    with pytest.raises(DomainError):
        BasisPoints(100, "USD", 2, 1)
    with pytest.raises(DomainError):
        BasisPoints(100, "ZZZ")
    with pytest.raises(DomainError):
        BasisPoints(100, "USD", -1)
    assert validate_timezone("UTC") == "UTC"
    with pytest.raises(DomainError):
        validate_timezone("Not/A_Real_Zone")


def test_rule_publish_and_retire_are_immutable() -> None:
    definition = {"required_statuses": ["paid"]}
    draft = RuleVersion("r1", 1, "delivered_paid_order", definition)
    definition["required_statuses"].append("refunded")
    assert draft.definition["required_statuses"] == ("paid",)
    published = draft.publish()
    assert draft.digest is None and published.digest
    assert published.retire().state == "retired"
    with pytest.raises(DomainError):
        published.publish()


def proposed_version(identifier: str = "v1") -> ContractVersion:
    terms: dict[str, Any] = {"currency": "USD", "nested": {"states": ["paid"]}}
    version = ContractVersion(identifier, 1, terms, frozenset({"buyer", "seller"}), NOW)
    terms["nested"]["states"].append("refunded")
    nested = cast(dict[str, Any], version.terms["nested"])
    assert nested["states"] == ("paid",)
    return version.propose()


def test_activation_requires_exact_digest_acceptance_from_every_role() -> None:
    version = proposed_version()
    with pytest.raises(DomainError):
        version.accept("buyer", "u1", NOW, "wrong")
    version = version.accept("buyer", "u1", NOW, version.digest or "")
    with pytest.raises(DomainError):
        version.activate()
    version = version.accept("seller", "u2", NOW, version.digest or "").activate()
    assert version.state is VersionState.ACTIVE


def test_selection_is_exclusive_at_end_and_deterministic() -> None:
    active = proposed_version().accept("buyer", "u1", NOW, proposed_version().digest or "")
    active = active.accept("seller", "u2", NOW, active.digest or "").activate()
    active = ContractVersion(
        active.id,
        active.version,
        active.terms,
        active.required_roles,
        NOW,
        NOW + timedelta(hours=1),
        active.state,
        active.digest,
        active.acceptances,
    )
    candidate = EffectiveCandidate(active, "shop", "s1")
    assert select_effective_contract([candidate], "shop", "s1", NOW).version == active
    assert (
        select_effective_contract([candidate], "shop", "s1", NOW + timedelta(hours=1)).reason
        == "no_effective_contract"
    )
    assert (
        select_effective_contract([candidate, candidate], "shop", "s1", NOW).reason
        == "ambiguous_effective_contract"
    )


def test_selection_enforces_binding_interval_and_parent_state() -> None:
    active = proposed_version()
    active = active.accept("buyer", "u1", NOW, active.digest or "")
    active = active.accept("seller", "u2", NOW, active.digest or "").activate()
    suspended = EffectiveCandidate(active, "shop", "s1", ContractState.SUSPENDED)
    future = EffectiveCandidate(active, "shop", "s1", binding_start=NOW + timedelta(seconds=1))
    assert (
        select_effective_contract([suspended, future], "shop", "s1", NOW).reason
        == "no_effective_contract"
    )
