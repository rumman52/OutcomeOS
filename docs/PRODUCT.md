# Product

OutcomeOS is a multi-tenant AI-powered performance-marketing operating system that connects advertising and customer conversations to verified business outcomes, calculates contribution profit, and charges only for contractually verified results.

## Implemented local MVP slice

The first vertical is a Bangladesh Facebook-commerce/e-commerce demo. It uses deterministic sandbox adapters only; it does not contact Meta, WhatsApp, Google, TikTok, Pathao, payment, courier, or AI provider APIs.

The seeded journey is:

1. Local demo sign-in to `Dhaka Demo Commerce`.
2. Seeded sandbox campaign, ad, spend snapshot, touchpoint, and Messenger-style conversation.
3. Tenant-scoped knowledge for product price, stock, delivery, COD, return policy, and FAQs.
4. Deterministic AI answer with evidence references and a human-approved lead/order proposal.
5. Idempotent lead and order creation in BDT minor units.
6. Deterministic OTP, duplicate, intent, address-risk, and prior-return verification checks.
7. Signed sandbox delivery/COD events are accepted by the versioned API surface.
8. Outcome verification requires order, lead verification, delivery, COD settlement, and attribution evidence.
9. Versioned contract creates exactly one BDT 150 performance-fee ledger entry.
10. Contribution profit is calculated server-side as BDT 340 for the acceptance fixture.
11. Dispute reversal appends a linked credit; original financial facts remain present.

## Non-goals

Real provider approvals, production OIDC, fund holding, campaign publishing, budget changes, voice calling, model fine-tuning, and production compliance certification are outside this local MVP.
