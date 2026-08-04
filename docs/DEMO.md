# Demo

1. `cp .env.example .env`
2. `make setup`
3. `make infra-up`
4. `make migrate`
5. `make seed`
6. `make dev`
7. Open `http://localhost:3000` and confirm sandbox campaign/conversation/profit labels.
8. Use `POST /api/v1/ai/proposals/{conversation_id}/approve` with `Idempotency-Key: demo-approval` to create lead/order/outcome/ledger facts.
9. Use signed `POST /api/v1/sandbox/webhooks/delivery` and `/cod` for evidence simulation.
10. Use `POST /api/v1/disputes/reverse` to append a credit and view `/api/v1/evidence`.

Acceptance fixture: BDT 1,500 collected revenue - BDT 700 product cost - BDT 200 ad spend - BDT 80 courier - BDT 30 COD fee - BDT 150 performance fee = BDT 340 contribution profit.
