import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_signed_webhook(
    *,
    url: str,
    payload: dict,
    signature_secret: str,
    event_id: str,
    timeout_seconds: int | None = None,
) -> tuple[bool, int | None, dict | None, str | None]:
    """
    Envía un webhook firmado con HMAC-SHA256.
    Devuelve (success, http_status, response_body, error_message).
    """
    body_bytes = json.dumps(
        payload, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    timestamp = datetime.now(timezone.utc).isoformat()

    message = f"{timestamp}.".encode() + body_bytes
    signature = hmac.new(
        signature_secret.encode(), message, hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Event-Id": event_id,
        "X-Hub-Signature": signature,
        "X-Hub-Timestamp": timestamp,
    }

    timeout = timeout_seconds or settings.WEBHOOK_TIMEOUT_SECONDS

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, content=body_bytes, headers=headers)
        logger.info(
            "Webhook enviado a %s → HTTP %s (event_id=%s)",
            url,
            response.status_code,
            event_id,
        )
        try:
            response_body = response.json()
        except Exception:
            response_body = {"raw": response.text}
        return (
            200 <= response.status_code < 300,
            response.status_code,
            response_body,
            None,
        )
    except httpx.TimeoutException as e:
        logger.warning("Timeout enviando webhook a %s: %s", url, e)
        return False, None, None, f"Timeout: {e}"
    except httpx.HTTPError as e:
        logger.warning("Error HTTP enviando webhook a %s: %s", url, e)
        return False, None, None, f"HTTP error: {e}"
    except Exception as e:
        logger.exception("Error inesperado enviando webhook a %s", url)
        return False, None, None, f"Unexpected error: {e}"