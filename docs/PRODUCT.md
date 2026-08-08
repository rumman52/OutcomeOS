# Product

OutcomeOS is a global, multi-tenant outcome verification and performance billing platform for brands, agencies, revenue teams, outcome-based service providers, approved partners, finance users and dispute reviewers.

Its promise is: **Connect every customer journey to verified business evidence, then bill only for outcomes that actually happened.**

## Initial outcome templates

1. Delivered and paid order.
2. Attended appointment or completed booking.
3. Qualified lead accepted by the business.
4. Paid signup or activated subscription.

Cash on delivery is one optional evidence method; no country, language, currency, channel or provider is a product default. Future templates extend versioned definitions rather than country-specific branches.

## Release boundary

The global core covers tenant configuration, canonical event ingestion, evidence, immutable outcome transitions, contracts, attribution, exact performance billing, invoices/credits/obligations, disputes, assisted conversations, approvals and postback delivery. It does not custody funds, promise global payouts, autonomously publish campaigns or budgets, adjudicate legal disputes, provide a partner marketplace or tax engine, execute user code, or automatically reject a person using a black-box AI score.

## Current truth

Only the global value objects, canonical envelope and outcome state-machine foundation are newly implemented. The existing country-specific deterministic fixture is legacy sandbox behavior. Production persistence, identity, workers, billing, UI workflows and real provider connections remain incomplete; see `docs/IMPLEMENTATION_STATUS.md`.
