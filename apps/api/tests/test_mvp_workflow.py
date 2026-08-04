import json
import time

import pytest

from outcomeos_api.config import get_settings
from outcomeos_api.mvp import FEE_MINOR, TENANT, MVPStore, profit, sign


def test_bangladesh_journey_separates_approval_delivery_cod_and_dispute(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OUTCOMEOS_DEMO_DB", str(tmp_path / "demo.json"))
    s = MVPStore()
    s.reset()
    approved = s.approve_proposal(TENANT, "same-key")
    assert approved["order"]["status"] == "confirmed"
    t = s.tenant(TENANT)
    assert t["billable_results"] == []
    assert t["outcomes"][0]["missing_reasons"] == [
        "Customer verification missing",
        "Delivery evidence missing",
        "COD settlement missing",
    ]

    s.complete_verification(TENANT)
    delivery = s.record_evidence(TENANT, "delivery", "evt-delivered")
    assert delivery["outcome"]["missing_reasons"] == ["COD settlement missing"]
    assert t["billable_results"] == []

    cod = s.record_evidence(TENANT, "cod", "evt-cod")
    assert cod["outcome"]["state"] == "billable"
    assert len(t["billable_results"]) == 1
    assert t["billable_results"][0]["amount_minor"] == FEE_MINOR
    assert profit(t)["contribution_profit_minor"] == 34000

    s.record_evidence(TENANT, "delivery", "evt-delivered")
    s.record_evidence(TENANT, "cod", "evt-cod")
    assert len(t["billable_results"]) == 1
    assert len([e for e in t["ledger_entries"] if e["direction"] == "debit"]) == 1

    d = s.dispute_reverse(TENANT)
    assert d["status"] == "reversed"
    assert t["ledger_entries"][-1]["direction"] == "credit"
    assert profit(t)["contribution_profit_minor"] == 49000
    s2 = MVPStore()
    assert s2.tenant(TENANT)["orders"][0]["id"] == approved["order"]["id"]


def test_api_delivery_and_cod_webhooks_are_distinct_and_idempotent():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from outcomeos_api.main import app

    client = TestClient(app)
    client.post("/api/v1/demo/reset")
    conversation_id = client.get("/api/v1/conversations").json()[0]["id"]
    client.post(f"/api/v1/ai/proposals/{conversation_id}/approve")
    client.post("/api/v1/leads/verify")

    def signed_post(kind: str, event_id: str):
        payload = {"event_id": event_id}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ts = int(time.time())
        return client.post(
            f"/api/v1/sandbox/webhooks/{kind}",
            json=payload,
            headers={
                "X-OutcomeOS-Timestamp": str(ts),
                "X-OutcomeOS-Signature": sign(
                    get_settings().webhook_sandbox_secret, body, ts
                ),
            },
        )

    delivery = signed_post("delivery", "evt-delivered")
    assert delivery.status_code == 200
    assert delivery.json()["outcome"]["missing_reasons"] == ["COD settlement missing"]
    assert client.get("/api/v1/evidence").json()["billable_results"] == []

    cod = signed_post("cod", "evt-cod")
    assert cod.status_code == 200
    assert cod.json()["outcome"]["state"] == "billable"
    signed_post("delivery", "evt-delivered")
    evidence = client.get("/api/v1/evidence").json()
    assert len(evidence["billable_results"]) == 1
    assert (
        len(
            [
                entry
                for entry in evidence["ledger_entries"]
                if entry["direction"] == "debit"
            ]
        )
        == 1
    )
