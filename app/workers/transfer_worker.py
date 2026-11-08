"""
Worker que procesa la tabla `job_queue` haciendo polling.
Alternativa a Redis (sin infraestructura extra).
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.infrastructure.db.models import (
    Bank,
    JobQueue,
    Transfer,
    TransferEvent,
    WebhookLog,
)
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.http.webhook_client import send_signed_webhook

configure_logging()
logger = get_logger(__name__)


async def claim_next_job() -> JobQueue | None:
    """Toma el siguiente job PENDING usando SELECT ... FOR UPDATE SKIP LOCKED."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            select(JobQueue)
            .where(JobQueue.status == "PENDING", JobQueue.run_at <= now)
            .order_by(JobQueue.run_at)
            .limit(settings.WORKER_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        jobs = result.scalars().all()

        if not jobs:
            return None

        job = jobs[0]
        job.status = "RUNNING"
        job.locked_until = now + timedelta(minutes=5)
        job.attempts += 1
        await session.commit()
        await session.refresh(job)
        logger.info(
            "Job %s reclamado (tipo=%s, intento=%d)",
            job.id, job.job_type, job.attempts,
        )
        return job


async def process_send_webhook_job(job: JobQueue) -> None:
    """Procesa un job de tipo 'send_webhook_to_destination'."""
    transfer_id = uuid.UUID(job.payload["transfer_id"])

    async with AsyncSessionLocal() as session:
        transfer = await session.get(Transfer, transfer_id)
        if transfer is None:
            raise RuntimeError(f"Transfer {transfer_id} no existe")

        bank_result = await session.execute(
            select(Bank).where(Bank.code == transfer.destination_bank_id)
        )
        dest_bank = bank_result.scalar_one_or_none()
        if dest_bank is None:
            raise RuntimeError(
                f"Banco destino {transfer.destination_bank_id} no existe"
            )

        if transfer.status == "PENDING":
            transfer.status = "PROCESSING"
            session.add(
                TransferEvent(
                    transfer_id=transfer.id,
                    from_status="PENDING",
                    to_status="PROCESSING",
                    actor="worker",
                )
            )
            await session.commit()

        event_id = str(uuid.uuid4())
        webhook_payload = {
            "event_id": event_id,
            "event_type": "transfer.received",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "transfer": {
                "transfer_id": str(transfer.id),
                "client_transfer_id": transfer.client_transfer_id,
                "origin_bank_id": transfer.origin_bank_id,
                "destination_bank_id": transfer.destination_bank_id,
                "amount": str(transfer.amount),
                "currency": transfer.currency,
                "concept": transfer.concept,
                "status": transfer.status,
                "priority": transfer.priority,
                "metadata": transfer.metadata_,
            },
        }

        success, http_status, response_body, error = await send_signed_webhook(
            url=dest_bank.callback_url,
            payload=webhook_payload,
            signature_secret=dest_bank.signature_secret,
            event_id=event_id,
        )

        session.add(
            WebhookLog(
                transfer_id=transfer.id,
                direction="OUTBOUND",
                target_bank_id=dest_bank.code,
                target_url=dest_bank.callback_url,
                event_type="transfer.received",
                payload=webhook_payload,
                http_status=http_status,
                response_body=response_body,
                attempt=job.attempts,
                success=success,
                error_message=error,
            )
        )
        await session.commit()

        if not success:
            raise RuntimeError(
                f"Webhook falló (http={http_status}, error={error})"
            )

        decision = (response_body or {}).get("decision")
        final_status: str | None = None
        final_reason: str | None = None

        if decision == "ACCEPTED":
            transfer.status = "COMPLETED"
            transfer.completed_at = datetime.now(timezone.utc)
            session.add(
                TransferEvent(
                    transfer_id=transfer.id,
                    from_status="PROCESSING",
                    to_status="COMPLETED",
                    actor=f"bank:{dest_bank.code}",
                )
            )
            logger.info("Transfer %s COMPLETED", transfer.id)
            final_status = "COMPLETED"
        elif decision == "REJECTED":
            reason = (response_body or {}).get("reason", "Rechazada por destino")
            transfer.status = "REJECTED"
            transfer.failure_reason = reason
            session.add(
                TransferEvent(
                    transfer_id=transfer.id,
                    from_status="PROCESSING",
                    to_status="REJECTED",
                    actor=f"bank:{dest_bank.code}",
                    reason=reason,
                )
            )
            logger.info("Transfer %s REJECTED: %s", transfer.id, reason)
            final_status = "REJECTED"
            final_reason = reason
        else:
            logger.warning("Respuesta sin decision clara: %s", response_body)

        await session.commit()

        # Notificar al banco origen (fuera de la transacción)
        if final_status is not None:
            await notify_origin_bank(
                transfer, "PROCESSING", final_status, final_reason
            )


async def mark_job_completed(job_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(JobQueue)
            .where(JobQueue.id == job_id)
            .values(
                status="COMPLETED",
                completed_at=datetime.now(timezone.utc),
                locked_until=None,
            )
        )
        await session.commit()


async def mark_job_failed(job_id: uuid.UUID, error: str) -> None:
    """Incrementa intentos y reprograma con backoff, o marca FAILED si agotó."""
    async with AsyncSessionLocal() as session:
        job = await session.get(JobQueue, job_id)
        if job is None:
            return

        if job.attempts >= job.max_attempts:
            job.status = "FAILED"
            job.last_error = error
            job.locked_until = None
            logger.error(
                "Job %s FAILED tras %d intentos: %s",
                job.id, job.attempts, error,
            )

            # Propagar FAILED a la transferencia asociada
            transfer_id_raw = job.payload.get("transfer_id")
            if transfer_id_raw:
                transfer = await session.get(
                    Transfer, uuid.UUID(transfer_id_raw)
                )
                if transfer is not None and transfer.status == "PROCESSING":
                    transfer.status = "FAILED"
                    transfer.failure_reason = f"Webhook falló: {error[:200]}"
                    session.add(
                        TransferEvent(
                            transfer_id=transfer.id,
                            from_status="PROCESSING",
                            to_status="FAILED",
                            actor="worker",
                            reason=error[:255],
                        )
                    )
                    logger.warning(
                        "Transfer %s marcada como FAILED tras agotar reintentos",
                        transfer.id,
                    )
                    # Guardar para notificar después del commit
                    transfer_to_notify = transfer
                    await session.commit()
                    # Notificar al origen (fuera de la transacción)
                    await notify_origin_bank(
                        transfer_to_notify, "PROCESSING", "FAILED", error[:200]
                    )
                    return
        else:
            backoff = settings.retry_backoff_list[
                min(job.attempts - 1, len(settings.retry_backoff_list) - 1)
            ]
            job.status = "PENDING"
            job.last_error = error
            job.locked_until = None
            job.run_at = datetime.now(timezone.utc) + timedelta(minutes=backoff)
            logger.warning(
                "Job %s reintentará en %d min (intento %d/%d)",
                job.id, backoff, job.attempts, job.max_attempts,
            )
        await session.commit()

async def notify_origin_bank(
    transfer: Transfer, previous_status: str, new_status: str, reason: str | None
) -> None:
    """
    Envía un webhook al banco origen notificando el cambio de estado.
    Si falla, se registra en webhook_logs pero no se relanza la excepción
    (la transferencia ya está en estado final; no queremos revertirla).
    """
    async with AsyncSessionLocal() as session:
        origin_result = await session.execute(
            select(Bank).where(Bank.code == transfer.origin_bank_id)
        )
        origin_bank = origin_result.scalar_one_or_none()
        if origin_bank is None:
            logger.warning(
                "Banco origen %s no encontrado, no se notifica",
                transfer.origin_bank_id,
            )
            return

        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "event_type": "transfer.status_changed",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "transfer_id": str(transfer.id),
            "previous_status": previous_status,
            "new_status": new_status,
            "reason": reason,
        }

        success, http_status, response_body, error = await send_signed_webhook(
            url=origin_bank.callback_url,
            payload=payload,
            signature_secret=origin_bank.signature_secret,
            event_id=event_id,
        )

        session.add(
            WebhookLog(
                transfer_id=transfer.id,
                direction="OUTBOUND",
                target_bank_id=origin_bank.code,
                target_url=origin_bank.callback_url,
                event_type="transfer.status_changed",
                payload=payload,
                http_status=http_status,
                response_body=response_body,
                attempt=1,
                success=success,
                error_message=error,
            )
        )
        await session.commit()

        if success:
            logger.info(
                "Notificado al origen %s: %s → %s",
                origin_bank.code,
                previous_status,
                new_status,
            )
        else:
            logger.warning(
                "No se pudo notificar al origen %s: %s",
                origin_bank.code,
                error,
            )

async def run_worker() -> None:
    logger.info(
        "Worker arrancando (poll=%ds, batch=%d)",
        settings.WORKER_POLL_INTERVAL_SECONDS,
        settings.WORKER_BATCH_SIZE,
    )
    try:
        while True:
            job = await claim_next_job()
            if job is None:
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
                continue

            try:
                if job.job_type == "send_webhook_to_destination":
                    await process_send_webhook_job(job)
                    await mark_job_completed(job.id)
                else:
                    raise RuntimeError(f"Job type desconocido: {job.job_type}")
            except Exception as e:
                logger.exception("Error procesando job %s", job.id)
                await mark_job_failed(job.id, str(e))
    except KeyboardInterrupt:
        logger.info("Worker detenido por el usuario")


if __name__ == "__main__":
    asyncio.run(run_worker())