from typing import Any
from pydantic import BaseModel, Field

class ErrorResponse(BaseModel):
    error_code: str = Field(..., examples=["IDEMPOTENCY_CONFLICT"])
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None