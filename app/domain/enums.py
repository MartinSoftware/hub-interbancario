from enum import Enum


class TransferStatus(str, Enum):
    #Estados posibles de una transferencia
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"


class TransferPriority(str, Enum):
    NORMAL = "NORMAL"
    EXPRESS = "EXPRESS"


class Currency(str, Enum):
    PEN = "PEN"
    USD = "USD"


class WebhookDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"