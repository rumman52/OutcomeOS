# Implementation status

OutcomeOS currently provides a deterministic local competition MVP for one Bangladesh Facebook-commerce journey. It is a SANDBOX implementation only; real Meta, WhatsApp, TikTok, Google, courier, payment, hosted AI and production identity providers are NOT CONNECTED.

## Implemented sandbox behavior

- Bangla inbound seeded conversation and tenant-scoped seeded product/COD knowledge.
- Deterministic AI reply/proposal fixture with evidence references and human-approval requirement.
- Separate lead/order approval, deterministic lead verification, delivery evidence, COD settlement evidence and outcome evaluation steps.
- Delivery without COD leaves the outcome pending with `COD settlement missing` and creates no fee.
- COD plus delivery plus verification plus attribution verifies the outcome and creates exactly one BDT 150 performance-fee debit.
- Replayed sandbox webhooks are idempotent and do not duplicate billable results or ledger debits.
- Server-calculated contribution profit is BDT 340 after the fee and BDT 490 after dispute reversal credit.
- Dispute reversal appends a linked BDT 150 credit without deleting or editing the original debit.
- Next.js route shells exist for the required competition pages and render service-unavailable instead of fallback financial data when the API cannot be reached.

## Partial / not production-ready

- Runtime persistence is still the deterministic local JSON-backed sandbox store; PostgreSQL models and migrations are present but not the sole source of truth for API behavior.
- PostgreSQL RLS is represented in migration/model tests but full PostgreSQL integration tests could not be run in this environment.
- The worker is not yet a durable PostgreSQL outbox consumer with heartbeat and dead-letter processing.
- Demo authentication is a local server-set cookie and is intentionally blocked in production.
- Lockfiles were not generated because registry access was blocked; they were not hand-written.
