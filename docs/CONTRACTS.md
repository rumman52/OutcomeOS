# Performance contracts and outcome rules

Milestone 3 Part 1 defines provider-neutral commercial metadata; it does not evaluate an outcome
or calculate a fee.

Contracts have a stable tenant-owned aggregate (`draft`, `active`, `suspended`, `terminated`) and
numbered terms versions (`draft`, `proposed`, `active`, `superseded`, `withdrawn`). Proposal binds
canonical JSON to a SHA-256 digest. Every required party role must acknowledge that exact version
and digest before activation. Suspension excludes a contract from new selections and termination
is terminal; neither operation deletes history.

An acknowledgement records product consent. **It is not a qualified electronic signature and is
not a representation or guarantee of legal enforceability.** Deployments need jurisdiction-specific
legal review and any legally required signing process.

Outcome rules have stable tenant-owned identities and immutable numbered definitions. Definitions
are bounded, allowlisted JSON for the `delivered_paid_order`, `attended_booking`,
`qualified_lead_accepted`, and `paid_activated_subscription` templates. Versions progress from
`draft` to `published` to `retired`. Retirement prevents new use without changing history.

Pricing metadata is exact: a fixed fee is a positive integer count of currency minor units; a
percentage is 1–10,000 integer basis points with optional non-negative minor-unit floor and cap.
The pricing currency must equal the contract currency. No fee calculation exists in Part 1.

Source bindings use tenant, provider-neutral source type and source identity. Effective selection
uses the trusted canonical event's `occurred_at` and half-open effective intervals. It returns one
active unsuspended version, `no_effective_contract`, or fails closed with
`ambiguous_effective_contract`; callers never supply an internal contract UUID.

Revision `20260815_0008` descends from `20260815_0007`. It adds composite tenant foreign keys,
checks, selection/list indexes, forced RLS policies, and triggers protecting proposed, published,
accepted, and active history. Its downgrade removes only Part 1 objects.

## Management API and transaction behavior

Authenticated management is exposed below `/api/v1/contracts` and `/api/v1/outcome-rules`.
Stable aggregates, exact numbered versions, source bindings, and lifecycle commands are tenant
scoped in SQL; list operations use an ID cursor, deterministic ordering, and a bounded 1–100
limit. Request models forbid extra fields, so callers cannot inject a tenant, actor, digest, or
authorization decision. Human access tokens are signature/issuer/audience verified through OIDC
and resolved through persisted identity and membership records. API keys require `data:write`, but
are deliberately rejected by the acceptance command. Acceptance additionally requires a persisted
`contract_party_authorities` row for that exact contract, role, and principal.

Every command requires `Idempotency-Key`. Revision `20260815_0009`, which additively descends from
immutable revision `20260815_0008`, stores a tenant-scoped request digest and original response;
reusing a key with different input fails with `idempotency_conflict`. The domain write, bounded
append-only audit record, sanitized domain-outbox record, and idempotency result share one database
transaction. Exceptions roll back all four. The outbox does not contain terms, provider payloads,
credentials, or PII.

Contract rows are locked for activation and lifecycle changes. `lock_version` supports optimistic
concurrency and the existing partial unique index permits only one active version. Activation
supersedes the prior version while holding the aggregate lock. A PostgreSQL exclusion constraint
rejects overlapping half-open source-binding intervals for the same tenant and canonical source.
