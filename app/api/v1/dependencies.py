from typing import Annotated
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.exceptions import (
    BankMismatchError,
    BankNotFoundError,
    InvalidSignatureError,
    InvalidTokenError,
)
from app.core.config import settings
from app.core.security import decode_access_token, verify_hmac_signature
from app.infrastructure.db.models import Bank
from app.infrastructure.db.repositories import BankRepository
from app.infrastructure.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]

async def get_current_bank(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    x_bank_id: Annotated[str | None, Header(alias="X-Bank-Id")] = None,
) -> Bank:
    """
    Valida JWT + verifica que X-Bank-Id coincida con el 'sub' del token.
    Devuelve el Bank autenticado.
    """
    if credentials is None:
        raise InvalidTokenError("Falta el header Authorization: Bearer ...")

    payload = decode_access_token(credentials.credentials)
    token_bank = payload["sub"]

    if x_bank_id is not None and x_bank_id != token_bank:
        raise BankMismatchError(
            f"X-Bank-Id ({x_bank_id}) no coincide con el token ({token_bank})"
        )

    bank_repo = BankRepository(db)
    bank = await bank_repo.get_by_code(token_bank)
    if bank is None or not bank.is_active:
        raise BankNotFoundError(f"Banco '{token_bank}' no existe o está inactivo")
    return bank


async def verify_signature(
    request: Request,
    bank: Annotated[Bank, Depends(get_current_bank)],
    x_signature: Annotated[str, Header(alias="X-Signature")],
    x_timestamp: Annotated[str, Header(alias="X-Timestamp")],
) -> None:
    """
    Verifica la firma HMAC del body del request.
    Lanza InvalidSignatureError si no coincide.
    """
    body = await request.body()
    if not verify_hmac_signature(
        secret=bank.signature_secret,
        timestamp=x_timestamp,
        body=body,
        provided_signature=x_signature,
    ):
        raise InvalidSignatureError("Firma HMAC del body no coincide")


# Tipo cómodo de usar en los endpoints
CurrentBank = Annotated[Bank, Depends(get_current_bank)]
SignatureOk = Annotated[None, Depends(verify_signature)]