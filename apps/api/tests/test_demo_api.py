from fastapi.testclient import TestClient

from outcomeos_api.main import app


def test_chat_persists_across_refresh_and_hands_off_safely() -> None:
    client=TestClient(app)
    response=client.post("/api/demo/chat",json={"tenant_id":"tenant_dhakastyle","session_id":"browser-session-001","message":"I need a human"})
    assert response.status_code == 200 and response.json()["handoff"] is True
    refreshed=client.get("/api/demo/conversations/browser-session-001").json()
    assert refreshed["status"] == "human_handoff"
    assert [message["role"] for message in refreshed["messages"]] == ["customer","assistant"]


def test_catalog_is_bilingual_and_money_is_minor_units() -> None:
    products=TestClient(app).get("/api/demo/products").json()
    assert len(products) == 5
    assert all(p["name_bn"] and isinstance(p["price_minor"],int) and p["currency"] == "BDT" for p in products)
