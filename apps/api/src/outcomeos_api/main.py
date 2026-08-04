import hashlib
import secrets
from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from outcomeos_api.ai import DeterministicMockAI, TOOL_SCHEMAS, execute_tool
from outcomeos_api.config import get_settings
from outcomeos_api.domain import utcnow
from outcomeos_api.models import ChatRequest
from outcomeos_api.store import Store

settings = get_settings()
app = FastAPI(title="OutcomeOS API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)
store = Store()
store.seed()
ai = DeterministicMockAI()


@app.get("/healthz", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/api/demo/products")
def products(tenant_id: str = "tenant_dhakastyle") -> list[dict[str, Any]]:
    return store.products(tenant_id)


@app.post("/api/demo/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    now, contact_id, conversation_id = utcnow().isoformat(), str(uuid4()), str(uuid4())
    with store.transaction() as db:
        if request.phone:
            db.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?,NULL)", (contact_id,request.tenant_id,request.phone))
            row=db.execute("SELECT id FROM contacts WHERE tenant_id=? AND phone=?", (request.tenant_id,request.phone)).fetchone()
            contact_id=row[0]
            db.execute("INSERT OR IGNORE INTO leads VALUES(?,?,?,?,?)", (str(uuid4()),request.tenant_id,contact_id,"new","campaign_demo"))
        else: contact_id=None
        db.execute("INSERT OR IGNORE INTO conversations VALUES(?,?,?,?,?)", (conversation_id,request.tenant_id,contact_id,request.session_id,"open"))
        row=db.execute("SELECT id,status FROM conversations WHERE tenant_id=? AND session_id=?", (request.tenant_id,request.session_id)).fetchone()
        conversation_id=row[0]
        db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (str(uuid4()),request.tenant_id,conversation_id,"customer",request.message,now))
        reply=ai.reply(request.message)
        handoff=reply == "HANDOFF_REQUIRED"
        if handoff:
            reply="A support agent will continue here. জরুরি সহায়তার জন্য আমাদের প্রতিনিধি যোগ দেবেন।"
            db.execute("UPDATE conversations SET status='human_handoff' WHERE id=?", (conversation_id,))
        db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?)", (str(uuid4()),request.tenant_id,conversation_id,"assistant",reply,now))
        db.execute("INSERT INTO touchpoints VALUES(?,?,?,?,?,?,?)", (str(uuid4()),request.tenant_id,contact_id,None,"campaign_demo",now,'{"channel":"shop_chat"}'))
    return {"conversation_id":conversation_id,"reply":reply,"handoff":handoff}


@app.get("/api/demo/conversations/{session_id}")
def conversation(session_id: str, tenant_id: str = "tenant_dhakastyle") -> dict[str, Any]:
    row=store.connection.execute("SELECT id,status FROM conversations WHERE tenant_id=? AND session_id=?", (tenant_id,session_id)).fetchone()
    if not row: raise HTTPException(404,"conversation not found")
    messages=store.connection.execute("SELECT role,body,created_at FROM messages WHERE tenant_id=? AND conversation_id=? ORDER BY created_at,id", (tenant_id,row[0])).fetchall()
    return {"id":row[0],"status":row[1],"messages":[dict(item) for item in messages]}


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]


@app.get("/api/ai/tools")
def tools() -> dict[str, Any]: return TOOL_SCHEMAS


@app.post("/api/ai/tools/execute")
def tool_call(call: ToolCall) -> object:
    try: return execute_tool(store,call.name,call.arguments)
    except (ValueError,KeyError) as error: raise HTTPException(422,str(error)) from error


class EventRequest(BaseModel):
    tenant_id: str
    order_id: str
    event_type: str
    idempotency_key: str = Field(min_length=8)
    evidence: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/events")
def event(request: EventRequest) -> dict[str,str]:
    try: event_id=store.record_event(request.tenant_id,request.order_id,request.event_type,request.idempotency_key,request.evidence)
    except Exception as error:
        if "UNIQUE" in str(error): return {"status":"duplicate"}
        raise HTTPException(422,str(error)) from error
    return {"id":event_id}


class OTPRequest(BaseModel):
    tenant_id: str
    phone: str = Field(pattern=r"^\+?[0-9]{8,15}$")


class OTPVerify(BaseModel):
    challenge_id: str
    code: str = Field(pattern=r"^[0-9]{6}$")


@app.post("/api/auth/otp")
def request_otp(request: OTPRequest) -> dict[str, Any]:
    if settings.app_env not in {"development","demo"}:
        raise HTTPException(404,"development OTP is unavailable")
    code=f"{secrets.randbelow(1_000_000):06d}"
    challenge_id=str(uuid4())
    with store.transaction() as db:
        db.execute("INSERT INTO otp_challenges VALUES(?,?,?,?,?,NULL)",(challenge_id,request.tenant_id,request.phone,hashlib.sha256(code.encode()).hexdigest(),(utcnow()+timedelta(minutes=5)).isoformat()))
    response: dict[str,Any]={"challenge_id":challenge_id,"expires_in_seconds":300}
    if settings.can_expose_otp: response["code"]=code
    return response


@app.post("/api/auth/otp/verify")
def verify_otp(request: OTPVerify) -> dict[str, bool]:
    if settings.app_env not in {"development","demo"}:
        raise HTTPException(404,"development OTP is unavailable")
    digest=hashlib.sha256(request.code.encode()).hexdigest()
    with store.transaction() as db:
        challenge=db.execute("SELECT code_hash,expires_at,consumed_at FROM otp_challenges WHERE id=?",(request.challenge_id,)).fetchone()
        if not challenge or challenge[2] or challenge[1] < utcnow().isoformat() or not secrets.compare_digest(challenge[0],digest):
            raise HTTPException(401,"invalid or expired challenge")
        db.execute("UPDATE otp_challenges SET consumed_at=? WHERE id=?",(utcnow().isoformat(),request.challenge_id))
    return {"verified":True}
