# Hub Interbancario

API neutral que actúa como **broker de mensajes** entre bancos digitales. No custodia fondos ni mantiene deudas entre bancos — solo registra y enruta transferencias interbancarias de forma segura, idempotente y auditable.

## ¿Qué hace?

- Recibe transferencias de un banco origen.
- Las valida (firma HMAC, idempotencia, reglas de dominio).
- Notifica al banco destino vía webhook.
- Actualiza el estado según la respuesta (`ACCEPTED` / `REJECTED`).
- Notifica al banco origen con el resultado final.

## ¿Qué NO hace?

- No custodia dinero.
- No mantiene saldos nostro/vostro.
- No liquida entre bancos.

> Modelo de **liquidación instantánea** (similar a PIX/Yape), donde cada banco cierra su propia contabilidad en el momento.

## Stack

- **FastAPI** (Python 3.12+)
- **PostgreSQL** (persistencia + cola de trabajos)
- **SQLAlchemy 2.x + Alembic** (ORM y migraciones)
- **Pydantic v2** (validación)
- **OAuth2 Client Credentials + HMAC-SHA256** (seguridad)

> **Sin Redis.** La cola de trabajos asíncronos se implementa como una tabla en PostgreSQL (`job_queue`) con `SELECT ... FOR UPDATE SKIP LOCKED`. Garantiza durabilidad y consistencia transaccional.

## Requisitos

- Python 3.12+
- PostgreSQL 16 (nativo, puerto 5432)

## Setup

\`\`\`powershell
# Crear virtualenv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -e ".[dev]"

# Copiar .env.example a .env
Copy-Item .env.example .env

# Correr la API
uvicorn app.main:app --reload
\`\`\`

## Documentación

- Swagger UI: `http://localhost:8000/docs` (solo en dev)
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Licencia

MIT