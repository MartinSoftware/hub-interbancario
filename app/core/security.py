import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.core.config import settings
from app.core.exceptions import InvalidTokenError

# ─────────────────────────────────────────────────────────────
# HMAC (firma de webhooks y requests)
# ─────────────────────────────────────────────────────────────
def compute_hmac_signature(secret: str, timestamp: str, body: bytes) -> str:
    """
    Calcula HMAC-SHA256 sobre 'timestamp.body' (evita replay + tampering).
    Devuelve el hex digest.
    """
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_hmac_signature(
    secret: str, timestamp: str, body: bytes, provided_signature: str
) -> bool:
    """Compara en tiempo constante (evita timing attacks)."""
    expected = compute_hmac_signature(secret, timestamp, body)
    return hmac.compare_digest(expected, provided_signature)

# ─────────────────────────────────────────────────────────────
# Hash de body (para idempotencia)
# ─────────────────────────────────────────────────────────────
def hash_body(body: bytes) -> str:
    """SHA256 hex del body crudo (para comparar reintentos idempotentes)."""
    return hashlib.sha256(body).hexdigest()

# ─────────────────────────────────────────────────────────────
# JWT (OAuth2 access tokens)
# ─────────────────────────────────────────────────────────────
def create_access_token(bank_code: str, scopes: list[str]) -> tuple[str, int]:
    """
    Crea un JWT firmado con HS256.
    Devuelve (token, expires_in_seconds).
    """
    now = datetime.now(timezone.utc)
    expires_in = settings.JWT_EXPIRES_MINUTES * 60
    payload = {
        "sub": bank_code,
        "scopes": scopes,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """Decodifica el JWT. Lanza InvalidTokenError si falla."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as e:
        raise InvalidTokenError(f"JWT inválido: {e}") from e

    if "sub" not in payload:
        raise InvalidTokenError("JWT sin 'sub'")
    return payload