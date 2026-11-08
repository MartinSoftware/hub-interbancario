"""Mock del Banco A. Recibe webhooks del Hub en /webhooks/hub."""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Banco A")

BANK_A_SIGNATURE_SECRET = "bank_a_secret"
RECEIVED = []


@app.post("/webhooks/hub")
async def receive_hub_webhook(
    request: Request,
    x_hub_signature: str = Header(alias="X-Hub-Signature"),
    x_hub_timestamp: str = Header(alias="X-Hub-Timestamp"),
    x_hub_event_id: str = Header(alias="X-Hub-Event-Id"),
):
    body = await request.body()
    message = f"{x_hub_timestamp}.".encode() + body
    expected = hmac.new(
        BANK_A_SIGNATURE_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_hub_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body)
    RECEIVED.append(payload)

    print(f"\n[DUMMY BANCO A] Webhook recibido:")
    print(f"  event_id: {x_hub_event_id}")
    print(f"  transfer: {payload.get('transfer_id')}")
    print(f"  change:   {payload.get('previous_status')} → {payload.get('new_status')}")
    print(f"  reason:   {payload.get('reason')}")

    return JSONResponse(status_code=200, content={"ok": True})


@app.get("/received")
async def list_received():
    return {"count": len(RECEIVED), "webhooks": RECEIVED}