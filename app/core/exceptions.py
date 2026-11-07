from typing import Any


class HubError(Exception):

    error_code: str = "HUB_ERROR"
    http_status: int = 500
    message: str = "Internal hub error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(HubError):
    error_code = "VALIDATION_ERROR"
    http_status = 400


class InvalidSignatureError(HubError):
    error_code = "INVALID_SIGNATURE"
    http_status = 403


class BankMismatchError(HubError):
    error_code = "BANK_MISMATCH"
    http_status = 403


class InvalidTokenError(HubError):
    error_code = "INVALID_TOKEN"
    http_status = 401


class BankNotFoundError(HubError):
    error_code = "BANK_NOT_FOUND"
    http_status = 404


class TransferNotFoundError(HubError):
    error_code = "TRANSFER_NOT_FOUND"
    http_status = 404


class IdempotencyConflictError(HubError):
    error_code = "IDEMPOTENCY_CONFLICT"
    http_status = 409


class DomainRuleViolationError(HubError):
    error_code = "DOMAIN_RULE_VIOLATION"
    http_status = 422


class RateLimitedError(HubError):
    error_code = "RATE_LIMITED"
    http_status = 429