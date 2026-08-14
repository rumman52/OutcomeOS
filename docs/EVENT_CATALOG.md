# Canonical event catalog

Canonical envelopes are provider-neutral, tenant-scoped and schema-versioned. Version 1 is defined in `outcomeos_api.events.schemas`. Producers must provide an aware occurrence time, receipt time, provider identity, subject, SHA-256 digest, consent purpose and sanitized payload. Raw payloads may be retained only by authorized policy using a tenant-scoped object key and digest.

Initial namespaced types are `lead.captured`, `lead.qualified`, `order.created`, `order.confirmed`, `fulfillment.delivered`, `order.returned`, `booking.created`, `booking.attended`, `booking.no_show`, `account.activated`, `payment.succeeded`, `payment.refunded`, `outcome.verified`, `outcome.billable`, `dispute.opened`, `dispute.resolved`, and `invoice.paid`.

The schema exists; durable receipt, normalization, outbox processing and replay are not implemented yet.
# Persistence boundary

Canonical event envelopes may be persisted by the Milestone 2 foundation with a tenant ID, event
type and version, occurrence time, JSON payload, and SHA-256 payload digest. Receipt-to-event and
event-to-original-job links are tenant-composite. No new event producer, consumer, webhook contract,
or exactly-once guarantee is introduced in Part 1; future delivery remains at-least-once.
