# Product

## Purpose

OutcomeOS is intended to make an organization's order-to-billing process explicit, durable, and auditable while connecting commercial work to measurable outcomes. The first product proof is deliberately narrow: a user creates a customer and priced order, accepts the order, generates an invoice from it, records payment, and can reload the application without losing or changing the facts.

This is a product direction, not a statement of current capability. See `IMPLEMENTATION_STATUS.md` for verified state.

## Users and jobs

- **Commercial operator:** capture a complete order and know which version was accepted.
- **Billing operator:** generate a correct invoice without re-keying order data and trace every amount to its source.
- **Finance reviewer:** reconcile subtotal, discounts, tax, credits, payments, and balance in one currency.
- **Tenant administrator:** control membership and roles without exposing another tenant's customers or financial data.
- **Auditor:** reconstruct who performed a transition, when, and why, without relying on mutable application logs.

## Persistent order-to-billing demo journey

1. A demo user enters a local-only tenant through clearly labeled demo authentication.
2. They create a customer and a draft order with currency, quantities, unit prices, discounts, and tax inputs.
3. The API calculates authoritative totals and persists the draft under the tenant.
4. The user accepts the order. Accepted commercial facts become immutable.
5. They issue one invoice sourced from that accepted order. The invoice snapshots its calculation inputs and receives a tenant-scoped sequential display number.
6. They record a payment allocation and see the remaining balance and derived status.
7. After refresh or service restart, the records, links, totals, transitions, and audit history remain present.
8. Attempts to replay a command do not create a duplicate; attempts to read or mutate it as another tenant are denied.

The journey may use only local demo identity and synthetic provider behavior in early phases. It must never be represented as a real payment, tax, accounting, or identity integration.

## Core rules

- Money uses integer minor units and an ISO 4217 currency; mixed-currency arithmetic is rejected.
- Quantity and rate precision, tax method, discount order, and rounding policy are explicit and tested.
- Accepted orders and issued invoices are immutable. Revisions, voids, credits, and adjustments are new linked facts.
- `invoice total = line subtotal - discounts + tax`; `balance = invoice total - credits - allocated payments`. Values must reconcile at commit.
- An allocation is non-negative, uses the invoice currency, and cannot exceed either invoice balance or available payment.
- Server calculations and state machines are authoritative. All create/transition commands are tenant-scoped and idempotent.

## Initial scope and non-goals

Initial scope covers tenant membership, customers, orders, invoices, manual payment records, audit history, and a persistent browser journey. Automated payment capture, production tax calculation, general ledger/accounting sync, revenue recognition, multi-entity consolidation, and production identity are not assumed. Provider logos, fixtures, and sandbox calls never establish a live capability.

## Success and release gates

- The journey completes from an empty database and survives reload/restart.
- Exact calculations are covered by boundary and property-oriented tests.
- Cross-tenant negative tests cover API, storage, jobs, caches, and exports.
- Duplicate command and worker delivery tests prove at-most-one financial effect.
- Accessibility checks cover the primary journey.
- Capability labels agree with `IMPLEMENTATION_STATUS.md`.

Production release additionally requires real identity, authorization defense in depth, observability, backups and restore evidence, threat-model and privacy review, operational runbooks, and independent disabling of all demo/mock paths.
