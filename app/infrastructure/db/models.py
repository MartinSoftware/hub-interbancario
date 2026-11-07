import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.infrastructure.db.base import Base, TimestampMixin

# ─────────────────────────────────────────────────────────────
# BANKS: registro de bancos interconectados
# ─────────────────────────────────────────────────────────────
class Bank(Base, TimestampMixin):
    __tablename__ = "banks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ─────────────────────────────────────────────────────────────
# TRANSFERS: la transferencia en sí
# ─────────────────────────────────────────────────────────────
class Transfer(Base, TimestampMixin):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfers_amount_positive"),
        UniqueConstraint(
            "origin_bank_id",
            "client_transfer_id",
            name="uq_transfers_origin_client_id",
        ),
        Index("ix_transfers_status", "status"),
        Index("ix_transfers_origin_created", "origin_bank_id", "created_at"),
        Index("ix_transfers_destination_created", "destination_bank_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_transfer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    origin_bank_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("banks.code"), nullable=False
    )
    destination_bank_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("banks.code"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    concept: Mapped[str] = mapped_column(String(140), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="NORMAL")
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ─────────────────────────────────────────────────────────────
# IDEMPOTENCY_KEYS: control de X-Idempotency-Key
# ─────────────────────────────────────────────────────────────
class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    bank_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("banks.code"), nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


# ─────────────────────────────────────────────────────────────
# WEBHOOK_LOGS: TODO intento de webhook (entrante o saliente)
# ─────────────────────────────────────────────────────────────
class WebhookLog(Base):
    __tablename__ = "webhook_logs"
    __table_args__ = (
        Index("ix_webhook_logs_transfer", "transfer_id"),
        Index("ix_webhook_logs_pending", "success", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # INBOUND / OUTBOUND
    target_bank_id: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("banks.code"), nullable=True
    )
    target_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    http_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────────────────────────────────────────
# TRANSFER_EVENTS: auditoría de cambios de estado (append-only)
# ─────────────────────────────────────────────────────────────
class TransferEvent(Base):
    __tablename__ = "transfer_events"
    __table_args__ = (Index("ix_transfer_events_transfer", "transfer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────────────────────────────────────────
# JOB_QUEUE: cola de trabajos (alternativa a Redis)
# ─────────────────────────────────────────────────────────────
class JobQueue(Base):
    __tablename__ = "job_queue"
    __table_args__ = (
        Index("ix_job_queue_pending", "status", "run_at"),
        Index("ix_job_queue_worker", "status", "locked_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )  # PENDING, RUNNING, COMPLETED, FAILED
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )