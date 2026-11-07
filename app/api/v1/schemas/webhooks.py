from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.domain.enums import TransferStatus

# ─────────────────────────────────────────────────────────────
# Webhook: Hub → Banco destino (nueva transferencia)
# ─────────────────────────────────────────────────────────────
class WebhookTransferNotification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="UUID del evento, para idempotencia")
    event_type: Literal["transfer.received"] = "transfer.received"
    occurred_at: datetime
    transfer: dict[str, Any]

# ─────────────────────────────────────────────────────────────
# Respuesta del banco destino al webhook
# ─────────────────────────────────────────────────────────────
class WebhookTransferAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["ACCEPTED", "REJECTED"]
    reason: str | None = Field(None, max_length=255)
    processed_at: datetime

# ─────────────────────────────────────────────────────────────
# Webhook: Hub → Banco origen (cambio de estado)
# ─────────────────────────────────────────────────────────────
class WebhookStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: Literal["transfer.status_changed"] = "transfer.status_changed"
    occurred_at: datetime
    transfer_id: str
    previous_status: TransferStatus
    new_status: TransferStatus
    reason: str | None = None