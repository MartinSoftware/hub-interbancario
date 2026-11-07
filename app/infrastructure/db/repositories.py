import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import IdempotencyConflictError, TransferNotFoundError
from app.infrastructure.db.models import (
    Bank,
    IdempotencyKey,
    JobQueue,
    Transfer,
    TransferEvent,
)

# ─────────────────────────────────────────────────────────────
# BANKS
# ─────────────────────────────────────────────────────────────
class BankRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_code(self, code: str) -> Bank | None:
        result = await self.session.execute(select(Bank).where(Bank.code == code))
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Bank]:
        result = await self.session.execute(
            select(Bank).where(Bank.is_active.is_(True))
        )
        return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────
# TRANSFERS
# ─────────────────────────────────────────────────────────────
class TransferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        client_transfer_id: str,
        origin_bank_id: str,
        destination_bank_id: str,
        amount,
        currency: str,
        concept: str,
        priority: str,
        metadata: dict | None,
    ) -> Transfer:
        transfer = Transfer(
            client_transfer_id=client_transfer_id,
            origin_bank_id=origin_bank_id,
            destination_bank_id=destination_bank_id,
            amount=amount,
            currency=currency,
            concept=concept,
            status="PENDING",
            priority=priority,
            metadata_=metadata,
        )
        self.session.add(transfer)
        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            raise IdempotencyConflictError(
                "Ya existe una transferencia con ese client_transfer_id"
            ) from e
        return transfer

    async def get_by_id(self, transfer_id: uuid.UUID) -> Transfer | None:
        result = await self.session.execute(
            select(Transfer).where(Transfer.id == transfer_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, transfer_id: uuid.UUID) -> Transfer:
        transfer = await self.get_by_id(transfer_id)
        if transfer is None:
            raise TransferNotFoundError(f"Transferencia {transfer_id} no existe")
        return transfer

    async def update_status(
        self,
        transfer_id: uuid.UUID,
        new_status: str,
        *,
        reason: str | None = None,
    ) -> Transfer:
        transfer = await self.get_or_raise(transfer_id)
        transfer.status = new_status
        if reason:
            transfer.failure_reason = reason
        if new_status == "COMPLETED":
            transfer.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return transfer


# ─────────────────────────────────────────────────────────────
# TRANSFER_EVENTS (auditoría)
# ─────────────────────────────────────────────────────────────
class TransferEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        *,
        transfer_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        actor: str,
        reason: str | None = None,
    ) -> TransferEvent:
        event = TransferEvent(
            transfer_id=transfer_id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        self.session.add(event)
        await self.session.flush()
        return event


# ─────────────────────────────────────────────────────────────
# IDEMPOTENCY_KEYS
# ─────────────────────────────────────────────────────────────
class IdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> IdempotencyKey | None:
        result = await self.session.execute(
            select(IdempotencyKey).where(IdempotencyKey.key == key)
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        *,
        key: str,
        bank_id: str,
        request_hash: str,
        status_code: int,
        response_body: dict,
    ) -> IdempotencyKey:
        entry = IdempotencyKey(
            key=key,
            bank_id=bank_id,
            request_hash=request_hash,
            status_code=status_code,
            response_body=response_body,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


# ─────────────────────────────────────────────────────────────
# JOB_QUEUE
# ─────────────────────────────────────────────────────────────
class JobQueueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
        max_attempts: int = 3,
    ) -> JobQueue:
        job = JobQueue(
            job_type=job_type,
            payload=payload,
            status="PENDING",
            max_attempts=max_attempts,
        )
        self.session.add(job)
        await self.session.flush()
        return job