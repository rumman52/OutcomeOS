from outcomeos_api.mvp import TENANT, profit, store


def test_bangladesh_demo_workflow_persists_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTCOMEOS_DEMO_DB", str(tmp_path / "demo.json"))
    from outcomeos_api.mvp import MVPStore

    s = MVPStore()
    s.reset()
    first = s.workflow(TENANT, "same-key")
    second = s.workflow(TENANT, "same-key")
    assert first == second
    t = s.tenant(TENANT)
    assert t["billable_results"][0]["amount_minor"] == 15000
    assert profit(t)["contribution_profit_minor"] == 34000
    d = s.dispute_reverse(TENANT)
    assert d["status"] == "reversed"
    assert t["ledger_entries"][-1]["direction"] == "credit"
    s2 = MVPStore()
    assert s2.tenant(TENANT)["orders"][0]["id"] == first["order"]["id"]


def test_tenant_knowledge_is_scoped():
    store.reset()
    t = store.tenant(TENANT)
    assert "Other tenant secret" not in "\n".join(
        c for d in t["knowledge_documents"] for c in d["chunks"]
    )
