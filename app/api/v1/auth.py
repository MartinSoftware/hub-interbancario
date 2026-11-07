from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.security import create_access_token
from app.infrastructure.db.repositories import BankRepository
from app.infrastructure.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter(tags=["auth"])


@router.post("/oauth/token")
async def issue_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    grant_type: Annotated[str, Form()] = "client_credentials",
    client_id: Annotated[str, Form()] = "",
    client_secret: Annotated[str, Form()] = "",
    scope: Annotated[str, Form()] = "transfers:write transfers:read",
) -> JSONResponse:
    """
    Emite un access token OAuth2 (Client Credentials).
    Para simplificar, usamos `code` como client_id y `signature_secret`
    como client_secret en el MVP (en producción se hashea con bcrypt).
    """
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="grant_type debe ser 'client_credentials'",
        )

    bank_repo = BankRepository(db)
    bank = await bank_repo.get_by_code(client_id)
    if bank is None or not bank.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    # En MVP: compara contra signature_secret directamente
    # En producción: usar bcrypt contra api_key_hash
    if client_secret != bank.signature_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    scopes = scope.split()
    token, expires_in = create_access_token(bank.code, scopes)

    return JSONResponse(
        content={
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "scope": " ".join(scopes),
        }
    )