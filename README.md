# Hub Interbancario

API neutral que actúa como **broker de mensajes** entre bancos digitales. No custodia fondos ni mantiene deudas entre bancos — solo registra y enruta transferencias interbancarias de forma segura, idempotente y auditable.

> Modelo de **liquidación instantánea** (similar a PIX/Yape), donde cada banco cierra su propia contabilidad en el momento.

---

## Estado del proyecto

✅ **Backend funcional** — Flujo end-to-end verificado para los 3 escenarios:
- `COMPLETED` (happy path)
- `REJECTED` (rechazo del destino)
- `FAILED` (destino caído, 3 reintentos con backoff)

---

## ¿Qué hace?

1. Recibe transferencias de un banco origen con autenticación OAuth2 y firma HMAC.
2. Valida idempotencia en dos capas (request + negocio).
3. Persiste la transferencia en estado `PENDING` y encola un job.
4. Un worker envía un webhook firmado al banco destino (`transfer.received`).
5. Actualiza el estado según la decisión del destino (`ACCEPTED` / `REJECTED`).
6. Notifica al banco origen con el cambio de estado (`transfer.status_changed`).
7. Audita cada transición en `transfer_events`.

## ¿Qué NO hace?

- ❌ No custodia dinero.
- ❌ No mantiene saldos nostro/vostro entre bancos.
- ❌ No liquida con un banco central.
- ❌ No es un cliente final ni una app móvil.

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| **API** | FastAPI 0.115 + Uvicorn |
| **Base de datos** | PostgreSQL 16 + SQLAlchemy 2.x + Alembic |
| **Cola de trabajos** | PostgreSQL (`job_queue` con `FOR UPDATE SKIP LOCKED`) — **sin Redis** |
| **Validación** | Pydantic v2 |
| **Seguridad** | OAuth2 Client Credentials + JWT (HS256) + HMAC-SHA256 |
| **HTTP Client** | httpx (async) |
| **Testing** | pytest (pendiente) |

---

## Máquina de estados

```text
       ┌───────────┐
       │  PENDING  │
       └─────┬─────┘
             │ worker toma el job
             ▼
       ┌───────────┐
       │PROCESSING │
       └─────┬─────┘
             │
   ┌─────────┼───────────┬──────────┐
   │         │           │          │
   ▼         ▼           ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│COMPLETED │ │ REJECTED │ │  FAILED  │ │ REVERSED │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
  destino      destino      destino      reverso
   aceptó      rechazó       caído       manual
```

---

## Flujo de una transferencia

```text
Banco A ──1. POST /transfers──► Hub
  │
  ├─2. Valida HMAC + JWT + idempotencia
  ├─3. INSERT transfers (PENDING)
  ├─4. INSERT job_queue
  │
  ▼
Worker
  │
  ├─5. Toma el job (FOR UPDATE SKIP LOCKED)
  ├─6. UPDATE transfers (PROCESSING)
  │
  ├─7. POST webhook a DinoBit (transfer.received)
  │    └─► DinoBit responde ACCEPTED/REJECTED
  │
  ├─8. UPDATE transfers (COMPLETED/REJECTED)
  │
  ├─9. POST webhook a Banco A (transfer.status_changed)
  │    └─► Banco A recibe la notificación
  │
  └─10. Mark job as COMPLETED
```

---

## Endpoints

### Públicos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Healthcheck |
| `GET` | `/` | Info del servicio |
| `GET` | `/docs` | Swagger UI (solo en dev) |

### Auth

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/oauth/token` | Client Credentials → JWT |

### API v1 (requieren JWT + HMAC)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/transfers` | Crear transferencia |
| `GET` | `/api/v1/transfers` | Listar (paginado, filtro `status`) |
| `GET` | `/api/v1/transfers/{id}` | Consultar detalle |

### Headers requeridos en API v1

| Header | Valor |
|---|---|
| `Authorization` | `Bearer <jwt>` |
| `X-Bank-Id` | Código del banco (debe coincidir con `sub` del JWT) |
| `X-Idempotency-Key` | UUID único de la petición |
| `X-Timestamp` | ISO8601 UTC (±5 min de drift) |
| `X-Signature` | HMAC-SHA256 hex de `timestamp.body` con el `signature_secret` del banco |

---

## Modelo de datos

| Tabla | Propósito |
|---|---|
| `banks` | Registro de bancos interconectados |
| `transfers` | Transferencias con estado y metadata |
| `transfer_events` | Auditoría append-only de transiciones |
| `webhook_logs` | Cada intento de webhook (INBOUND/OUTBOUND) |
| `idempotency_keys` | Control de `X-Idempotency-Key` (24h) |
| `job_queue` | Cola de trabajos asíncrona |

---

## Instalación y ejecución

### Requisitos
- Python 3.12+
- PostgreSQL 16 nativo (puerto 5432)

### Setup

```powershell
# 1. Crear virtualenv
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -e ".[dev]"

# 3. Configurar
Copy-Item .env.example .env
# Editar .env si es necesario

# 4. Crear la base de datos (en psql como postgres)
# CREATE USER hub WITH PASSWORD 'hub';
# CREATE DATABASE hub OWNER hub;
# GRANT ALL PRIVILEGES ON DATABASE hub TO hub;

# 5. Aplicar migraciones
alembic upgrade head

# 6. Insertar bancos de prueba (en psql como hub)
# INSERT INTO banks (code, name, callback_url, api_key_hash, signature_secret, is_active)
# VALUES
#   ('BANK_A',  'Banco A', 'http://localhost:8001/webhooks/hub',    'placeholder', 'bank_a_secret',  true),
#   ('DINOBIT', 'DinoBit', 'http://localhost:8002/hooks/interbank', 'placeholder', 'dinobit_secret', true);
```

### Ejecutar los 4 procesos (en 4 terminales)

| Terminal | Comando | Puerto |
|---|---|---|
| 1 — Hub | `uvicorn app.main:app --reload --port 8000` | 8000 |
| 2 — Mock DinoBit | `$env:DECISION_MODE="ACCEPTED"; uvicorn mock_bank:app --reload --port 8002` | 8002 |
| 3 — Mock Banco A | `uvicorn mock_bank_a:app --reload --port 8001` | 8001 |
| 4 — Worker | `python -m app.workers.transfer_worker` | — |

---

## Probar el flujo completo

```powershell
# 1. Obtener token
curl.exe -X POST http://localhost:8000/oauth/token `
  -d "grant_type=client_credentials" `
  -d "client_id=BANK_A" `
  -d "client_secret=bank_a_secret" `
  -d "scope=transfers:write transfers:read"

# 2. Copiar el access_token y usarlo en el script
# Editar test_transfer.ps1 → $TOKEN = "..."

# 3. Ejecutar
.tests\test_transfer.ps1
```

---

## Escenarios verificados

### ✅ Happy path (COMPLETED)
```text
Banco A → Hub → DinoBit (ACCEPTED) → Hub → Banco A
```
Verificado con `webhook_logs`: 2 registros `OUTBOUND` exitosos.

### ✅ Rechazo (REJECTED)
```text
DinoBit responde REJECTED con reason
```
Verificado con `transfer.failure_reason` y evento `PROCESSING` → `REJECTED`.

### ✅ Caída del destino (FAILED)
```text
DinoBit apagado → 3 reintentos con backoff (1min cada uno) → FAILED
```
Verificado con 3 registros en `webhook_logs` con `success=false`.

---

## Trabajo futuro

Mejoras no implementadas que se mencionan en la documentación académica:
- Tests automatizados (pytest)
- Idempotencia en webhooks entrantes (por parte del banco destino)
- Rate limiting por banco
- Endpoint de reverso `POST /transfers/{id}/reverse`
- mTLS (certificados de cliente)
- Firma RSA/ECDSA en lugar de HMAC
- Logs estructurados en JSON
- Métricas Prometheus
- CI/CD con GitHub Actions
- Docker compose

---

## Licencia

MIT