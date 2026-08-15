# Deterministic outcome evaluation

Milestone 3 Part 2 defines a provider-neutral, framework-independent evaluator. It records factual
results only: it does not perform attribution, calculate a fee, create a billable result, decide a
dispute, call a provider, or use AI.

## Bound input and evidence

The application layer supplies an explicit evaluation and outcome identity, `as_of`, authenticated
tenant and source identity, normalized subject, and exact immutable contract/rule version IDs and
SHA-256 digests. A trusted event projection contains only its canonical ID/digest, type/schema,
aware occurrence and receipt timestamps, subject, allowlisted references, optional integer-minor-unit
money metadata, and an optional sanitized status. Raw payloads and credentials are excluded.

Input uses the contract foundation's canonical JSON implementation. Events have stable ordering.
Exact duplicate IDs with identical projections are removed; conflicting duplicates, cross-tenant
evidence, subject mismatch, unsupported schemas, invalid digests, and naive timestamps fail closed
as bounded operational errors rather than business verdicts.

## Templates

| Template | Required evidence | In-window disqualifier |
| --- | --- | --- |
| `delivered_paid_order` | `order.confirmed`, `fulfillment.delivered`, `payment.succeeded` | `order.returned`, `payment.refunded` |
| `attended_booking` | `booking.created`, `booking.attended` | `booking.no_show` |
| `qualified_lead_accepted` | `lead.captured`, `lead.qualified`, `lead.accepted` | none |
| `paid_activated_subscription` | `account.activated`, `payment.succeeded` | `payment.refunded` |

Attended and no-show evidence together is an operational conflict. Monetary evidence must use a
consistent currency, but no arithmetic or pricing decision occurs. Qualification alone never means
that a lead was accepted.

## Time semantics and results

The unique anchor starts evaluation. The anchor is always admissible; other occurrences use the
half-open interval `[anchor, anchor + evaluation_window_seconds)`. Finalization is evaluation end
plus `finalization_window_seconds`. Additional evidence must be received no later than both `as_of`
and finalization. An event at evaluation end is excluded, evidence received exactly at finalization
is admissible, and `as_of` exactly at finalization may verify.

Before finalization, missing evidence or a satisfied template produces `pending`. At/after
finalization, complete positive evidence produces `verified`, missing evidence produces `rejected`,
and an admissible disqualifier produces `rejected`. Evidence arriving after finalization cannot
rewrite a finalized result; persistence must record only a sanitized late-event operational signal.

Input and decision digests omit generated database timestamps, worker leases, and insertion metadata.
Identical immutable inputs are byte-for-byte deterministic. Persistence and authenticated read/replay
APIs remain incomplete in this local implementation; there is no claim of production readiness.
