from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

FEE_MINOR = 15000
TENANT = "11111111-1111-4111-8111-111111111111"
OTHER_TENANT = "22222222-2222-4222-8222-222222222222"
USER = "demo-user"


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()


def sign(secret: str, body: bytes, ts: int) -> str:
    return hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def stable(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def audit(kind: str, target: str) -> dict[str, str]:
    return {
        "id": str(uuid.uuid4()),
        "type": kind,
        "target_id": target,
        "created_at": now(),
        "actor": "system/demo",
    }


def check(kind: str, result: str, reason: str, tenant_id: str) -> dict[str, Any]:
    return {
        "id": stable(f"{tenant_id}:{kind}"),
        "tenant_id": tenant_id,
        "kind": kind,
        "result": result,
        "reason": reason,
        "input_digest": digest({"kind": kind}),
        "version": "sandbox:v1",
        "created_at": now(),
    }


@dataclass
class MVPStore:
    path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("OUTCOMEOS_DEMO_DB", "/tmp/outcomeos-demo.json")
        )
    )
    data: dict[str, Any] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        self.load()

    def load(self) -> None:
        self.data = json.loads(self.path.read_text()) if self.path.exists() else self.reset()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.data = seed_data()
            self.save()
            return self.data

    def tenant(self, tenant_id: str) -> dict[str, Any]:
        if tenant_id not in self.data["tenants"]:
            raise KeyError("tenant not found")
        return cast(dict[str, Any], self.data["tenants"][tenant_id])

    def receive_message(self, tenant_id: str, text: str) -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            c = t["conversations"][0]
            c["messages"].append({"direction": "inbound", "text": text, "created_at": now()})
            t["audit_events"].append(audit("message.received", c["id"]))
            self.save()
            return cast(dict[str, Any], c)

    def approve_proposal(self, tenant_id: str, idem: str = "demo-approval") -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            ids = t["ids"]
            key = f"approve:{idem}"
            if key in t["idempotency"]:
                return cast(dict[str, Any], t["idempotency"][key])
            lead = {
                "id": ids["lead"],
                "tenant_id": tenant_id,
                "stage": "pending_verification",
                "contact_id": ids["contact"],
                "created_at": now(),
            }
            order = {
                "id": ids["order"],
                "tenant_id": tenant_id,
                "lead_id": lead["id"],
                "status": "confirmed",
                "currency": "BDT",
                "collected_revenue_minor": 150000,
                "product_cost_minor": 70000,
                "discount_minor": 0,
                "allocated_ad_spend_minor": 20000,
                "courier_charge_minor": 8000,
                "payment_fee_minor": 3000,
                "return_cost_minor": 0,
                "version": 1,
                "items": [
                    {
                        "sku": "LINEN-SAGE",
                        "quantity": 1,
                        "unit_price_minor": 150000,
                        "currency": "BDT",
                    }
                ],
                "created_at": now(),
            }
            attr = {
                "id": ids["attribution"],
                "tenant_id": tenant_id,
                "order_id": order["id"],
                "selected_touchpoint_id": ids["touchpoint"],
                "rule_version": "last_eligible_touch:v1",
                "confidence": "exact",
                "reason": "conversation referral matched seeded sandbox ad within 30 days",
                "created_at": now(),
            }
            t["leads"] = [lead]
            t["orders"] = [order]
            t["attribution_results"] = [attr]
            t["audit_events"].append(audit("tool_proposal.approved", order["id"]))
            self.evaluate(tenant_id, save=False)
            res = {"lead": lead, "order": order, "outcome": t["outcomes"][0]}
            t["idempotency"][key] = res
            self.save()
            return res

    def complete_verification(self, tenant_id: str) -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            t["verification_checks"] = [
                check("otp", "passed", "sandbox OTP 123456 matched", tenant_id),
                check(
                    "duplicate_contact",
                    "passed",
                    "no existing verified lead",
                    tenant_id,
                ),
                check("customer_intent", "passed", "explicit order intent", tenant_id),
                check(
                    "suspicious_address",
                    "passed",
                    "address accepted by deterministic rule",
                    tenant_id,
                ),
                check("prior_return", "passed", "no prior return warning", tenant_id),
            ]
            if t["leads"]:
                t["leads"][0]["stage"] = "verified"
            t["audit_events"].append(audit("lead.verification_completed", t["ids"]["lead"]))
            self.evaluate(tenant_id, save=False)
            self.save()
            return {"checks": t["verification_checks"], "outcome": t["outcomes"][0]}

    def record_evidence(self, tenant_id: str, kind: str, event_id: str) -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            receipt_key = f"webhook:{kind}:{event_id}"
            if receipt_key in t["idempotency"]:
                return cast(dict[str, Any], t["idempotency"][receipt_key])
            field = "shipments" if kind == "delivery" else "settlement_events"
            event_type = "shipment.delivered" if kind == "delivery" else "payment.cod_settled"
            rec = {
                "id": stable(f"{tenant_id}:{kind}:{event_id}"),
                "tenant_id": tenant_id,
                "order_id": t["ids"]["order"],
                "provider": "sandbox",
                "external_id": event_id,
                "created_at": now(),
            }
            t[field] = [rec]
            t["webhook_receipts"].append(
                {
                    "tenant_id": tenant_id,
                    "provider": "sandbox",
                    "external_id": event_id,
                    "kind": kind,
                    "received_at": now(),
                }
            )
            t["audit_events"].append(audit(event_type, rec["id"]))
            self.evaluate(tenant_id, save=False)
            res = {"status": "accepted", "kind": kind, "outcome": t["outcomes"][0]}
            t["idempotency"][receipt_key] = res
            self.save()
            return res

    def workflow(self, tenant_id: str, idem: str = "demo-approval") -> dict[str, Any]:
        self.approve_proposal(tenant_id, idem)
        self.complete_verification(tenant_id)
        self.record_evidence(tenant_id, "delivery", "legacy-delivery")
        return self.record_evidence(tenant_id, "cod", "legacy-cod")

    def evaluate(self, tenant_id: str, save: bool = True) -> dict[str, Any]:
        t = self.tenant(tenant_id)
        ids = t["ids"]
        checklist = {
            "customer_verified": bool(t["verification_checks"])
            and all(c["result"] == "passed" for c in t["verification_checks"]),
            "attribution_eligible": bool(t["attribution_results"]),
            "order_confirmed": bool(t["orders"]) and t["orders"][0]["status"] == "confirmed",
            "delivery_received": bool(t.get("shipments")),
            "cod_settled": bool(t.get("settlement_events")),
            "contract_eligible": t["contract_versions"][0]["status"] == "active",
        }
        missing = [
            label
            for key, label in [
                ("customer_verified", "Customer verification missing"),
                ("attribution_eligible", "Attribution missing"),
                ("order_confirmed", "Order confirmation missing"),
                ("delivery_received", "Delivery evidence missing"),
                ("cod_settled", "COD settlement missing"),
                ("contract_eligible", "Contract inactive"),
            ]
            if not checklist[key]
        ]
        state = "billable" if not missing else "pending_evidence"
        outcome = {
            "id": ids["outcome"],
            "tenant_id": tenant_id,
            "order_id": ids["order"],
            "state": state,
            "readiness": checklist,
            "missing_reasons": missing,
            "contract_version_id": ids["contract_version"],
            "version": len(t.get("audit_events", [])),
            "created_at": now(),
        }
        t["outcomes"] = [outcome]
        if state == "billable" and not t["billable_results"]:
            bill = {
                "id": ids["billable"],
                "tenant_id": tenant_id,
                "outcome_id": outcome["id"],
                "amount_minor": FEE_MINOR,
                "currency": "BDT",
                "contract_version_id": ids["contract_version"],
                "created_at": now(),
            }
            led = {
                "id": ids["ledger"],
                "tenant_id": tenant_id,
                "billable_result_id": bill["id"],
                "amount_minor": FEE_MINOR,
                "currency": "BDT",
                "direction": "debit",
                "type": "performance_fee",
                "created_at": now(),
            }
            t["billable_results"] = [bill]
            t["ledger_entries"].append(led)
            t["audit_events"].append(audit("outcome.billable_fee_created", outcome["id"]))
        if save:
            self.save()
        return outcome

    def dispute_reverse(self, tenant_id: str) -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            if t["disputes"] and t["disputes"][0]["status"] == "reversed":
                return cast(dict[str, Any], t["disputes"][0])
            d = {
                "id": t["ids"]["dispute"],
                "tenant_id": tenant_id,
                "outcome_id": t["ids"]["outcome"],
                "status": "reversed",
                "reason": "merchant disputed delivered evidence in demo",
                "evidence_timeline": timeline(t),
                "created_at": now(),
                "resolved_at": now(),
            }
            credit = {
                "id": t["ids"]["credit"],
                "tenant_id": tenant_id,
                "linked_ledger_entry_id": t["ids"]["ledger"],
                "amount_minor": FEE_MINOR,
                "currency": "BDT",
                "direction": "credit",
                "type": "performance_fee_credit",
                "created_at": now(),
            }
            t["disputes"] = [d]
            if not any(e.get("id") == credit["id"] for e in t["ledger_entries"]):
                t["ledger_entries"].append(credit)
            t["audit_events"].append(audit("dispute.reversed", d["id"]))
            self.save()
            return d


def timeline(t: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"type": x, "timestamp": now()}
        for x in [
            "campaign/ad/touchpoint",
            "customer conversation",
            "AI proposal approved",
            "lead verified",
            "order confirmed",
            "delivery evidence",
            "COD settlement",
            "outcome rule v1",
            "contract v1",
            "BDT 150 fee",
            "ledger debit",
            "audit",
        ]
    ]


def profit(t: dict[str, Any]) -> dict[str, Any]:
    o = (t.get("orders") or [{}])[0]
    perf = sum(
        e["amount_minor"] if e["direction"] == "debit" else -e["amount_minor"]
        for e in t.get("ledger_entries", [])
    )
    val = (
        o.get("collected_revenue_minor", 0)
        - o.get("product_cost_minor", 0)
        - o.get("discount_minor", 0)
        - o.get("allocated_ad_spend_minor", 0)
        - o.get("payment_fee_minor", 0)
        - o.get("courier_charge_minor", 0)
        - o.get("return_cost_minor", 0)
        - perf
    )
    return {
        "currency": "BDT",
        "contribution_profit_minor": val,
        "performance_fee_minor": perf,
        "expected_acceptance_profit_minor": 34000,
    }


def tenant_seed(tenant_id: str, name: str) -> dict[str, Any]:
    ids = {
        k: stable(f"{tenant_id}:{k}")
        for k in [
            "contact",
            "conversation",
            "touchpoint",
            "lead",
            "order",
            "attribution",
            "outcome",
            "contract_version",
            "billable",
            "ledger",
            "dispute",
            "credit",
        ]
    }
    return {
        "id": tenant_id,
        "name": name,
        "ids": ids,
        "idempotency": {},
        "campaigns": [
            {
                "id": "camp-sandbox-1",
                "name": "SANDBOX Facebook commerce campaign",
                "spend_minor": 20000,
                "currency": "BDT",
            }
        ],
        "ads": [
            {
                "id": "ad-sandbox-1",
                "campaign_id": "camp-sandbox-1",
                "creative_id": "creative-sage",
                "label": "SANDBOX / NOT CONNECTED",
            }
        ],
        "touchpoints": [
            {
                "id": ids["touchpoint"],
                "tenant_id": tenant_id,
                "campaign_id": "camp-sandbox-1",
                "ad_id": "ad-sandbox-1",
                "source": "facebook",
                "medium": "paid_social",
                "conversation_id": ids["conversation"],
                "confidence": "exact",
            }
        ],
        "contacts": [{"id": ids["contact"], "tenant_id": tenant_id, "display_name": "Maya Akter"}],
        "conversations": [
            {
                "id": ids["conversation"],
                "tenant_id": tenant_id,
                "contact_id": ids["contact"],
                "provider": "SANDBOX Messenger",
                "messages": [
                    {
                        "direction": "inbound",
                        "text": "আপনার sage green linen set আছে? COD হবে?",
                    }
                ],
            }
        ],
        "knowledge_documents": [
            {
                "id": "kd-1",
                "tenant_id": tenant_id,
                "title": "Product, price, stock and policy",
                "chunks": [
                    "Sage green linen set price BDT 1500; stock 8; Dhaka delivery BDT 80; "
                    "COD accepted; returns within 7 days."
                ],
            }
        ],
        "ai_runs": [
            {
                "id": "ai-1",
                "tenant_id": tenant_id,
                "answer": (
                    "জি, sage green linen set স্টকে আছে। দাম BDT 1,500। "
                    "Dhaka delivery BDT 80 এবং COD হবে।"
                ),
                "evidence": ["kd-1"],
                "tool_proposals": [
                    {"tool": "create_lead"},
                    {"tool": "create_order", "requires_human_approval": True},
                ],
                "validation_status": "valid",
                "prompt_version": "sandbox-bn-v1",
            }
        ],
        "leads": [],
        "orders": [],
        "verification_checks": [],
        "attribution_results": [],
        "outcomes": [],
        "billable_results": [],
        "ledger_entries": [],
        "shipments": [],
        "settlement_events": [],
        "webhook_receipts": [],
        "disputes": [],
        "audit_events": [audit("demo.seeded", "tenant")],
        "contract_versions": [
            {
                "id": ids["contract_version"],
                "tenant_id": tenant_id,
                "fee_minor": FEE_MINOR,
                "currency": "BDT",
                "result_type": "delivered_order_cod_settled",
                "attribution_window_days": 30,
                "status": "active",
            }
        ],
        "outbox_messages": [],
        "worker_heartbeats": [],
    }


def seed_data() -> dict[str, Any]:
    tenant = tenant_seed(TENANT, "Dhaka Demo Commerce")
    other = tenant_seed(OTHER_TENANT, "Other Tenant")
    other["knowledge_documents"] = [
        {
            "id": "other-kd",
            "tenant_id": OTHER_TENANT,
            "title": "Private other tenant stock",
            "chunks": ["Other tenant secret product."],
        }
    ]
    return {
        "tenants": {TENANT: tenant, OTHER_TENANT: other},
        "users": {USER: {"id": USER, "email": "demo@outcomeos.local", "memberships": [TENANT]}},
    }


store = MVPStore()
