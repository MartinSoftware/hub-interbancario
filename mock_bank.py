"""
Mock del banco destino (DinoBit simulado).
Corre en :8002 y responde ACCEPTED a cualquier webhook válido.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock DinoBit")

DINOBIT_SIGNATURE_SECRET = "dinobit_secret"
RECEIVED = []


@app.post("/hooks/interbank")
async def receive_interbank_webhook(
    request: Request,
    x_hub_signature: str = Header(alias="X-Hub-Signature"),
    x_hub_timestamp: str = Header(alias="X-Hub-Timestamp"),
    x_hub_event_id: str = Header(alias="X-Hub-Event-Id"),
):
    body = await request.body()

    # Verificar firma HMAC
    message = f"{x_hub_timestamp}.".encode() + body
    expected = hmac.new(
        DINOBIT_SIGNATURE_SECRET.encode(), message, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_hub_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body)
    RECEIVED.append(payload)

    print(f"\n[DUMMY DINOBIT] Webhook recibido:")
    print(f"  event_id: {x_hub_event_id}")
    print(f"  transfer: {payload['transfer']['transfer_id']}")
    print(f"  amount:   {payload['transfer']['amount']} {payload['transfer']['currency']}")

    return JSONResponse(
        status_code=200,
        content={
            "decision": "ACCEPTED",
            "reason": None,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.get("/received")
async def list_received():
    return {"count": len(RECEIVED), "webhooks": RECEIVED}