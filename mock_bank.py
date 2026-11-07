"""
Mock del banco destino (DinoBit simulado).
Corre en :8002 y responde según la variable DECISION_MODE.

Modos:
  - ACCEPTED: acepta siempre
  - REJECTED: rechaza siempre con un motivo
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock DinoBit")

DINOBIT_SIGNATURE_SECRET = "dinobit_secret"
DECISION_MODE = os.getenv("DECISION_MODE", "ACCEPTED").upper()
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

    print(f"\n[DUMMY DINOBIT] Webhook recibido (modo={DECISION_MODE}):")
    print(f"  event_id: {x_hub_event_id}")
    print(f"  transfer: {payload['transfer']['transfer_id']}")
    print(f"  amount:   {payload['transfer']['amount']} {payload['transfer']['currency']}")

    if DECISION_MODE == "REJECTED":
        return JSONResponse(
            status_code=200,
            content={
                "decision": "REJECTED",
                "reason": "Cuenta destino bloqueada por el banco",
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Por defecto: ACCEPTED
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


@app.get("/mode")
async def current_mode():
    return {"mode": DECISION_MODE}