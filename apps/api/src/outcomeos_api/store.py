import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from outcomeos_api.domain import transition, utcnow
from outcomeos_api.models import CreateOrderArgs, OutcomeStage


class Store:
    """Transactional demo store. PostgreSQL deployments use the equivalent SQL migration."""

    def __init__(self, path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        schema = Path(__file__).with_name("schema.sql").read_text()
        self.connection.executescript(schema)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection:
            yield self.connection

    def seed(self) -> str:
        tenant = "tenant_dhakastyle"
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO tenants(id,name) VALUES(?,?)", (tenant, "DhakaStyle Demo Store"))
            for sku, en, bn, price, cost, stock in (
                ("DS-PNJ", "Emerald Panjabi", "এমেরাল্ড পাঞ্জাবি", 285000, 170000, 18),
                ("DS-SAR", "Jamdani Saree", "জামদানি শাড়ি", 495000, 315000, 9),
                ("DS-KRT", "Cotton Kurti", "কটন কুর্তি", 165000, 90000, 24),
                ("DS-SHL", "Nakshi Shawl", "নকশি শাল", 220000, 125000, 12),
                ("DS-BAG", "Jute Tote", "পাটের ব্যাগ", 85000, 42000, 31),
            ):
                product_id, variant_id = f"product_{sku}", f"variant_{sku}"
                db.execute("INSERT OR IGNORE INTO products VALUES(?,?,?,?,1)", (product_id, tenant, en, bn))
                db.execute("INSERT OR IGNORE INTO variants VALUES(?,?,?,?,?,?)", (variant_id, tenant, product_id, sku, price, "BDT"))
                db.execute("INSERT OR IGNORE INTO inventory VALUES(?,?,?,?,?)", (f"inventory_{sku}", tenant, variant_id, stock, cost))
            db.execute("INSERT OR IGNORE INTO campaigns VALUES(?,?,?,?,?)", ("campaign_demo", tenant, "Pohela Boishakh Demo", 500000, "BDT"))
            db.execute("INSERT OR IGNORE INTO contract_versions(id,tenant_id,version,pricing_model,fixed_fee_minor,currency) VALUES(?,?,?,?,?,?)", ("contract_bdt150_v1", tenant, 1, "fixed", 15000, "BDT"))
            db.execute("INSERT OR IGNORE INTO accounts VALUES(?,?,?,?)", ("account_owner",tenant,"owner@dhakastyle.demo","owner"))
            db.execute("INSERT OR IGNORE INTO accounts VALUES(?,?,?,?)", ("account_support",tenant,"support@dhakastyle.demo","support_agent"))
            db.execute("INSERT OR IGNORE INTO faq_policies VALUES(?,?,?,?,?,?,?)", ("policy_delivery",tenant,"policy","Delivery & returns","ডেলিভারি ও রিটার্ন","Delivery takes 2–5 days; returns accepted within 7 days.","ডেলিভারি ২–৫ দিন; ৭ দিনের মধ্যে রিটার্ন করা যাবে।"))
        return tenant

    def products(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute("""SELECT p.id,p.name_en,p.name_bn,v.id variant_id,v.sku,v.price_minor,v.currency,i.on_hand
          FROM products p JOIN variants v ON v.product_id=p.id AND v.tenant_id=p.tenant_id
          JOIN inventory i ON i.variant_id=v.id AND i.tenant_id=v.tenant_id WHERE p.tenant_id=? AND p.active=1""", (tenant_id,))
        return [dict(row) for row in rows]

    def stock(self, tenant_id: str, variant_id: str) -> int:
        row = self.connection.execute("SELECT on_hand FROM inventory WHERE tenant_id=? AND variant_id=?", (tenant_id, variant_id)).fetchone()
        if not row:
            raise KeyError("variant not found")
        return int(row[0])

    def append_event(self, db: sqlite3.Connection, tenant: str, aggregate_id: str, event_type: str, data: dict[str, Any], key: str) -> str:
        event_id = str(uuid4())
        now = utcnow().isoformat()
        db.execute("INSERT INTO canonical_events VALUES(?,?,?,?,?,?,?)", (event_id, tenant, aggregate_id, event_type, now, json.dumps(data), key))
        db.execute("INSERT INTO outbox_messages VALUES(?,?,?,?,?,NULL)", (str(uuid4()), tenant, event_id, json.dumps({"event_id": event_id}), now))
        return event_id

    def create_order(self, args: CreateOrderArgs) -> dict[str, Any]:
        existing = self.connection.execute("SELECT id,total_minor,currency FROM orders WHERE tenant_id=? AND idempotency_key=?", (args.tenant_id, args.idempotency_key)).fetchone()
        if existing:
            return dict(existing)
        order_id, now, total = str(uuid4()), utcnow().isoformat(), 0
        with self.transaction() as db:
            for item in args.items:
                row = db.execute("""SELECT v.price_minor,v.currency,i.on_hand FROM variants v JOIN inventory i ON i.variant_id=v.id AND i.tenant_id=v.tenant_id WHERE v.id=? AND v.tenant_id=?""", (item.variant_id, args.tenant_id)).fetchone()
                if not row or row[2] < item.quantity:
                    raise ValueError("item unavailable")
                total += int(row[0]) * item.quantity
                db.execute("UPDATE inventory SET on_hand=on_hand-? WHERE tenant_id=? AND variant_id=?", (item.quantity, args.tenant_id, item.variant_id))
            db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?)", (order_id,args.tenant_id,args.contact_id,"created",args.payment_method,total,"BDT",args.delivery_address,now,args.idempotency_key))
            for item in args.items:
                db.execute("INSERT INTO order_items SELECT ?,?,?,id,?,price_minor,currency FROM variants WHERE id=? AND tenant_id=?", (str(uuid4()),order_id,args.tenant_id,item.quantity,item.variant_id,args.tenant_id))
            outcome_id = str(uuid4())
            db.execute("INSERT INTO outcomes VALUES(?,?,?,?,?)", (outcome_id,args.tenant_id,order_id,"captured",now))
            db.execute("INSERT INTO outcome_transitions VALUES(?,?,?,?,?,?,?)", (str(uuid4()),args.tenant_id,outcome_id,None,"captured",now,json.dumps({"source":"order.created"})))
            self.append_event(db,args.tenant_id,order_id,"order.created",{"total_minor":total,"currency":"BDT"},args.idempotency_key)
        return {"id": order_id, "total_minor": total, "currency": "BDT", "outcome_id": outcome_id}

    def record_event(self, tenant: str, order_id: str, event_type: str, key: str, evidence: dict[str, Any]) -> str:
        with self.transaction() as db:
            event_id = self.append_event(db, tenant, order_id, event_type, evidence, key)
            if event_type == "order.confirmed":
                db.execute("UPDATE orders SET status='confirmed' WHERE id=? AND tenant_id=?", (order_id,tenant))
            elif event_type == "shipment.delivered":
                db.execute("INSERT OR IGNORE INTO shipments VALUES(?,?,?,?,?)", (str(uuid4()),tenant,order_id,"delivered",utcnow().isoformat()))
            elif event_type in {"payment.cod_settled","payment.prepaid_validated"}:
                db.execute("INSERT OR IGNORE INTO payments VALUES(?,?,?,?,?,?,1)", (str(uuid4()),tenant,order_id,event_type.removeprefix("payment."),0,"BDT"))
            elif event_type in {"order.cancelled","order.returned"}:
                db.execute("UPDATE orders SET status=? WHERE id=? AND tenant_id=?", (event_type.split('.')[1],order_id,tenant))
            self._advance(db, tenant, order_id, event_id)
        return event_id

    def _advance(self, db: sqlite3.Connection, tenant: str, order_id: str, evidence_event: str) -> None:
        outcome = db.execute("SELECT id,stage FROM outcomes WHERE tenant_id=? AND order_id=?", (tenant,order_id)).fetchone()
        order = db.execute("SELECT status,payment_method,created_at FROM orders WHERE tenant_id=? AND id=?", (tenant,order_id)).fetchone()
        assert outcome and order
        current = OutcomeStage(outcome["stage"])
        if order["status"] in {"cancelled","returned"}:
            target = OutcomeStage.DISQUALIFIED
        else:
            delivered = db.execute("SELECT 1 FROM shipments WHERE tenant_id=? AND order_id=? AND status='delivered'", (tenant,order_id)).fetchone()
            payment_status = "cod_settled" if order["payment_method"] == "cod" else "prepaid_validated"
            paid = db.execute("SELECT 1 FROM payments WHERE tenant_id=? AND order_id=? AND status=? AND independently_validated=1", (tenant,order_id,payment_status)).fetchone()
            target = current
            if order["status"] == "confirmed":
                target = OutcomeStage.QUALIFIED
                if delivered:
                    target = OutcomeStage.CONVERTED
                    if paid:
                        target = OutcomeStage.VERIFIED
        stages = [OutcomeStage.CAPTURED, OutcomeStage.QUALIFIED, OutcomeStage.CONVERTED, OutcomeStage.VERIFIED]
        while current != target:
            next_stage = target if target == OutcomeStage.DISQUALIFIED else stages[stages.index(current) + 1]
            transition(current,next_stage)
            now=utcnow().isoformat()
            db.execute("UPDATE outcomes SET stage=?,updated_at=? WHERE id=?", (next_stage.value,now,outcome["id"]))
            db.execute("INSERT INTO outcome_transitions VALUES(?,?,?,?,?,?,?)", (str(uuid4()),tenant,outcome["id"],current.value,next_stage.value,now,json.dumps({"canonical_event_id":evidence_event})))
            current = next_stage
        if target == OutcomeStage.VERIFIED:
            contract = db.execute("SELECT id,fixed_fee_minor,currency FROM contract_versions WHERE tenant_id=? AND effective_at<=? ORDER BY effective_at DESC,version DESC LIMIT 1", (tenant,order["created_at"])).fetchone()
            assert contract
            result_id=str(uuid4())
            db.execute("INSERT OR IGNORE INTO billable_results VALUES(?,?,?,?,?,?,?)", (result_id,tenant,outcome["id"],contract["id"],contract["fixed_fee_minor"],contract["currency"],now))
            result=db.execute("SELECT id FROM billable_results WHERE tenant_id=? AND outcome_id=?", (tenant,outcome["id"])).fetchone()
            db.execute("INSERT OR IGNORE INTO ledger_entries VALUES(?,?,?,?,?,?,?,?,?)", (str(uuid4()),tenant,"performance_fee_accrual",contract["fixed_fee_minor"],contract["currency"],result["id"],f"accrual:{outcome['id']}",now,json.dumps({"event_id":evidence_event})))
