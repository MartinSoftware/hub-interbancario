from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.domain.enums import Currency, TransferPriority, TransferStatus

# ─────────────────────────────────────────────────────────────
# REQUEST: crear transferencia
# ─────────────────────────────────────────────────────────────
class TransferCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_bank_id: str = Field(
        ..., min_length=3, max_length=20, examples=["BANK_A"]
    )
    destination_bank_id: str = Field(
        ..., min_length=3, max_length=20, examples=["DINOBIT"]
    )
    amount: Decimal = Field(
        ..., gt=0, le=Decimal("50000.00"), decimal_places=2, examples=["1500.00"]
    )
    currency: Currency = Currency.PEN
    concept: str = Field(..., max_length=140)
    client_transfer_id: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="ID único del banco origen para esta transferencia",
        examples=["BNK-A-2026-000042"],
    )
    priority: TransferPriority = TransferPriority.NORMAL
    metadata: dict[str, Any] | None = None

    @field_validator("destination_bank_id")
    @classmethod
    def destination_not_same_as_origin(cls, v: str, info) -> str:
        origin = info.data.get("origin_bank_id")
        if origin and v == origin:
            raise ValueError(
                "destination_bank_id no puede ser igual a origin_bank_id"
            )
        return v

# ─────────────────────────────────────────────────────────────
# RESPONSE: creación
# ─────────────────────────────────────────────────────────────
class TransferCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: str
    status: TransferStatus
    created_at: datetime
    estimated_completion: datetime | None = None

# ─────────────────────────────────────────────────────────────
# RESPONSE: detalle
# ─────────────────────────────────────────────────────────────
class TransferDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transfer_id: str
    client_transfer_id: str
    origin_bank_id: str
    destination_bank_id: str
    amount: Decimal
    currency: Currency
    concept: str
    status: TransferStatus
    priority: TransferPriority
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")