# Canonical event catalog

Canonical envelopes are provider-neutral, tenant-scoped and schema-versioned. Version 1 is defined in `outcomeos_api.events.schemas`. Producers must provide an aware occurrence time, receipt time, provider identity, subject, SHA-256 digest, consent purpose and sanitized payload. Raw payloads may be retained only by authorized policy using a tenant-scoped object key and digest.

Initial namespaced types are `lead.captured`, `lead.qualified`, `order.created`, `order.confirmed`, `fulfillment.delivered`, `order.returned`, `booking.created`, `booking.attended`, `booking.no_show`, `account.activated`, `payment.succeeded`, `payment.refunded`, `outcome.verified`, `outcome.billable`, `dispute.opened`, `dispute.resolved`, and `invoice.paid`.

Durable receipt, normalization, outbox processing, replay, reconciliation, and CSV ingestion are
implemented for pre-production verification; no live provider integration is implied.
# Persistence boundary

Canonical event envelopes may be persisted by the Milestone 2 foundation with a tenant ID, event
type and version, occurrence time, JSON payload, and SHA-256 payload digest. Receipt-to-event and
event-to-original-job links are tenant-composite. No new event producer, consumer, webhook contract,
or exactly-once guarantee is introduced in Part 1; future delivery remains at-least-once.

## Public input boundary

Public input requires a namespaced type, provider event ID, aware occurrence timestamp, subject, explicit consent, and payload. Tenant, provider, IDs, digests, receive time, and state are server-owned. Missing or false processing consent rejects the request before evidence retention.
# Milestone 2 durable pipeline events

The Part 3 pipeline recognizes `ingest.canonical_event.v1`, `ingest.csv.v1`, and
`reconcile.tenant.v1` durable job contracts. Internal reconciliation scheduling uses the
`outcomeos.reconciliation.requested` canonical control event. These contracts validate and
operate stored evidence only; they do not perform provider calls or business evaluation.

## Canonical CSV v1

CSV input is UTF-8 and has this exact, ordered, unique header row:

`provider_event_id,event_type,occurred_at,subject_type,subject_id,processing_permitted,advertising_permitted,consent_purpose,references_json,attribution_json,money_minor_units,money_currency,payload_json`

Tenant IDs, OutcomeOS-generated IDs, digests, object keys, and processing state are not input
fields. JSON cells must contain objects, timestamps must include an offset, money uses integer
minor units and an ISO 4217 currency, and processing consent is mandatory.
