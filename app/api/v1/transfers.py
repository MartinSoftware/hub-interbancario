import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.dependencies import CurrentBank, DbSession, SignatureOk
from app.api.v1.schemas.transfers import (
    TransferCreateRequest,
    TransferCreateResponse,
    TransferDetailResponse,
)
from app.core.exceptions import IdempotencyConflictError, DomainRuleViolationError
from app.core.security import hash_body
from app.infrastructure.db.repositories import (
    BankRepository,
    IdempotencyRepository,
    JobQueueRepository,
    TransferEventRepository,
    TransferRepository,
)

from app.api.v1.schemas.transfers import TransferListResponse

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_transfer(
    request: Request,
    payload: TransferCreateRequest,
    db: DbSession,
    bank: CurrentBank,
    _sig: SignatureOk,
    x_idempotency_key: Annotated[str, Header(alias="X-Idempotency-Key")],
) -> JSONResponse:
    """
    Crea una transferencia interbancaria.
    Valida banco destino, idempotencia, y encola el job.
    """
    # 1. Verificar que el origin del payload coincida con el banco autenticado
    if payload.origin_bank_id != bank.code:
        raise DomainRuleViolationError(
            "origin_bank_id no coincide con el banco autenticado"
        )

    # 2. Verificar que el destino exista y esté activo
    bank_repo = BankRepository(db)
    destination = await bank_repo.get_by_code(payload.destination_bank_id)
    if destination is None or not destination.is_active:
        raise DomainRuleViolationError(
            f"Banco destino '{payload.destination_bank_id}' no existe o está inactivo"
        )

    # 3. Idempotencia: si ya existe la key, devolver respuesta guardada
    body = await request.body()
    request_hash = hash_body(body)
    idem_repo = IdempotencyRepository(db)
    existing = await idem_repo.get(x_idempotency_key)
    if existing is not None:
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(
                "Idempotency-Key ya usada con un body distinto"
            )
        return JSONResponse(
            content=existing.response_body or {},
            status_code=existing.status_code or 202,
        )

    # 4. Crear la transferencia
    transfer_repo = TransferRepository(db)
    transfer = await transfer_repo.create(
        client_transfer_id=payload.client_transfer_id,
        origin_bank_id=payload.origin_bank_id,
        destination_bank_id=payload.destination_bank_id,
        amount=payload.amount,
        currency=payload.currency.value,
        concept=payload.concept,
        priority=payload.priority.value,
        metadata=payload.metadata,
    )

    # 5. Auditar evento inicial
    event_repo = TransferEventRepository(db)
    await event_repo.log(
        transfer_id=transfer.id,
        from_status=None,
        to_status="PENDING",
        actor=f"bank:{bank.code}",
    )

    # 6. Encolar job para enviar webhook al destino
    job_repo = JobQueueRepository(db)
    await job_repo.enqueue(
        job_type="send_webhook_to_destination",
        payload={"transfer_id": str(transfer.id)},
    )

    # 7. Guardar idempotency
    response_body = {
        "transfer_id": str(transfer.id),
        "status": "PENDING",
        "created_at": transfer.created_at.isoformat(),
        "estimated_completion": None,
    }
    await idem_repo.save(
        key=x_idempotency_key,
        bank_id=bank.code,
        request_hash=request_hash,
        status_code=202,
        response_body=response_body,
    )

    await db.commit()
    return JSONResponse(content=response_body, status_code=202)

@router.get("", response_model=TransferListResponse)
async def list_transfers(
    db: DbSession,
    bank: CurrentBank,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TransferListResponse:
    """Lista transferencias del banco (origen o destino), paginadas."""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    transfer_repo = TransferRepository(db)
    items, total = await transfer_repo.list_for_bank(
        bank_code=bank.code,
        status=status,
        page=page,
        page_size=page_size,
    )

    return TransferListResponse(
        items=[
            TransferDetailResponse(
                transfer_id=str(t.id),
                client_transfer_id=t.client_transfer_id,
                origin_bank_id=t.origin_bank_id,
                destination_bank_id=t.destination_bank_id,
                amount=t.amount,
                currency=t.currency,
                concept=t.concept,
                status=t.status,
                priority=t.priority,
                created_at=t.created_at,
                updated_at=t.updated_at,
                completed_at=t.completed_at,
                failure_reason=t.failure_reason,
                metadata=t.metadata_,
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )

@router.get("/{transfer_id}", response_model=TransferDetailResponse)
async def get_transfer(
    transfer_id: uuid.UUID,
    db: DbSession,
    bank: CurrentBank,
) -> TransferDetailResponse:
    """Consulta una transferencia. Solo el banco origen o destino puede verla."""
    transfer_repo = TransferRepository(db)
    transfer = await transfer_repo.get_or_raise(transfer_id)

    # Solo origen o destino pueden consultarla
    if bank.code not in (transfer.origin_bank_id, transfer.destination_bank_id):
        from app.core.exceptions import BankMismatchError
        raise BankMismatchError(
            "No tienes permiso para consultar esta transferencia"
        )

    return TransferDetailResponse(
        transfer_id=str(transfer.id),
        client_transfer_id=transfer.client_transfer_id,
        origin_bank_id=transfer.origin_bank_id,
        destination_bank_id=transfer.destination_bank_id,
        amount=transfer.amount,
        currency=transfer.currency,
        concept=transfer.concept,
        status=transfer.status,
        priority=transfer.priority,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
        completed_at=transfer.completed_at,
        failure_reason=transfer.failure_reason,
        metadata=transfer.metadata_,
    )