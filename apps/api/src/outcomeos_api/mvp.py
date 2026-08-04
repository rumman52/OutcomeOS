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
from typing import Any

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
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.reset()

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
        return self.data["tenants"][tenant_id]

    def workflow(self, tenant_id: str, idem: str = "demo-approval") -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            ids = t["ids"]
            if idem in t["idempotency"]:
                return t["idempotency"][idem]
            lead = {
                "id": ids["lead"],
                "stage": "pending_verification",
                "contact_id": ids["contact"],
                "tenant_id": tenant_id,
                "created_at": now(),
            }
            checks = [
                check("otp", "passed", "sandbox OTP 123456 matched"),
                check("duplicate_contact", "passed", "no existing verified lead"),
                check("customer_intent", "passed", "explicit order intent"),
                check(
                    "suspicious_address",
                    "passed",
                    "address accepted by deterministic rule",
                ),
                check("prior_return", "passed", "no prior return warning"),
            ]
            lead["stage"] = "verified"
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
            outcome = {
                "id": ids["outcome"],
                "tenant_id": tenant_id,
                "order_id": order["id"],
                "state": "billable",
                "evidence": [
                    "conversation",
                    "human_approval",
                    "lead_verification",
                    "delivery",
                    "cod_settlement",
                    "attribution",
                ],
                "contract_version_id": ids["contract_version"],
                "version": 6,
                "created_at": now(),
            }
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
            t.update(
                {
                    "leads": [lead],
                    "verification_checks": checks,
                    "orders": [order],
                    "attribution_results": [attr],
                    "outcomes": [outcome],
                    "billable_results": [bill],
                    "ledger_entries": [led],
                }
            )
            result = {
                "lead": lead,
                "order": order,
                "outcome": outcome,
                "billable_result": bill,
                "ledger_entry": led,
            }
            t["idempotency"][idem] = result
            t["audit_events"].append(audit("workflow.approved", ids["order"]))
            self.save()
            return result

    def dispute_reverse(self, tenant_id: str) -> dict[str, Any]:
        with self.lock:
            t = self.tenant(tenant_id)
            self.workflow(tenant_id)
            if t["disputes"] and t["disputes"][0]["status"] == "reversed":
                return t["disputes"][0]
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
            t["ledger_entries"].append(credit)
            t["outcomes"][0]["state"] = "credited"
            t["audit_events"].append(audit("dispute.reversed", d["id"]))
            self.save()
            return d


def check(kind: str, result: str, reason: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, kind)),
        "kind": kind,
        "result": result,
        "reason": reason,
        "input_digest": digest({"kind": kind}),
        "version": "sandbox:v1",
        "created_at": now(),
    }


def audit(kind: str, target: str) -> dict[str, str]:
    return {
        "id": str(uuid.uuid4()),
        "type": kind,
        "target_id": target,
        "created_at": now(),
        "actor": "system/demo",
    }


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


def seed_data() -> dict[str, Any]:
    ids = {
        k: str(uuid.uuid5(uuid.NAMESPACE_URL, k))
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
    tenant = {
        "id": TENANT,
        "name": "Dhaka Demo Commerce",
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
                "campaign_id": "camp-sandbox-1",
                "ad_id": "ad-sandbox-1",
                "source": "facebook",
                "medium": "paid_social",
                "conversation_id": ids["conversation"],
                "confidence": "exact",
            }
        ],
        "contacts": [{"id": ids["contact"], "display_name": "Maya Akter"}],
        "conversations": [
            {
                "id": ids["conversation"],
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
                "title": "Product, price, stock and policy",
                "chunks": [
                    (
                        "Sage green linen set price BDT 1500; stock 8; Dhaka delivery BDT 80; "
                        "COD accepted; returns within 7 days."
                    )
                ],
            }
        ],
        "ai_runs": [
            {
                "id": "ai-1",
                "answer": (
                    "Yes, sage green linen set is in stock for BDT 1,500. "
                    "Dhaka delivery is BDT 80 and COD is available."
                ),
                "evidence": ["kd-1"],
                "tool_proposals": [
                    {"tool": "create_lead"},
                    {"tool": "create_order", "requires_human_approval": True},
                ],
            }
        ],
        "leads": [],
        "orders": [],
        "verification_checks": [],
        "attribution_results": [],
        "outcomes": [],
        "billable_results": [],
        "ledger_entries": [],
        "disputes": [],
        "audit_events": [audit("demo.seeded", "tenant")],
        "contract_versions": [
            {
                "id": ids["contract_version"],
                "fee_minor": FEE_MINOR,
                "currency": "BDT",
                "result_type": "delivered_order_cod_settled",
                "attribution_window_days": 30,
                "status": "active",
            }
        ],
    }
    other = {
        **tenant,
        "id": OTHER_TENANT,
        "name": "Other Tenant",
        "knowledge_documents": [
            {
                "id": "other-kd",
                "title": "Private other tenant stock",
                "chunks": ["Other tenant secret product."],
            }
        ],
        "ids": ids.copy(),
    }
    return {
        "tenants": {TENANT: tenant, OTHER_TENANT: other},
        "users": {USER: {"id": USER, "email": "demo@outcomeos.local", "memberships": [TENANT]}},
    }


store = MVPStore()
