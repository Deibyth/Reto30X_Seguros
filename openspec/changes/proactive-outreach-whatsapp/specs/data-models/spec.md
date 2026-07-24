# Spec: Data Models (Delta)

> **Capability:** C02 — `data-models`
> **Change:** `proactive-outreach-whatsapp`
> **Date:** 2026-07-23
> **Base spec:** `openspec/specs/data-models/spec.md`

## Description

Delta extending the Notification model with scheduling, retry, and opportunity FK fields for the proactive WhatsApp outreach feature. All existing models and requirements remain unchanged.

## Requirements

### Functional

- F-DATA-01: The system SHALL define 12 ORM models: Customer, Product, Credit, Insurance, Policy, Claim, Application, Document, Conversation, Session, Opportunity, Notification.
- F-DATA-02: All models SHALL use SQLAlchemy 2.0 `Mapped` / `mapped_column` typing style.
- F-DATA-03: All models SHALL inherit from a shared `Base` declarative base.
- F-DATA-04: The system SHALL create an async SQLAlchemy engine using `aiosqlite` as the driver.
- F-DATA-05: The system SHALL provide an `AsyncSession` factory via `async_sessionmaker`.
- F-DATA-06: The system SHALL call `Base.metadata.create_all()` on startup inside the app lifespan.
- F-DATA-07: Each model SHALL include `id` (UUID, primary key), `created_at`, and `updated_at` timestamp columns.
- F-DATA-08: The database file SHALL be stored at `backend/data/proteccion360.db`.
- F-DATA-09: A `data/.gitkeep` file SHALL be created to preserve the directory in version control.
- F-DATA-10: The `models/__init__.py` SHALL re-export all model classes and `Base`.
- F-DATA-11: The Notification model SHALL be extended with the following columns: `scheduled_at` (DateTime, nullable), `sent_at` (DateTime, nullable), `responded_at` (DateTime, nullable), `error_log` (Text, nullable), `intento_actual` (Integer, default=0), `max_intentos` (Integer, default=1), `opportunity_id` (UUID, FK→opportunities, nullable).
- F-DATA-12: The Notification model SHALL define a relationship to Opportunity via `opportunity_id`.

### Non-Functional

- NF-DATA-01: All timestamps SHALL use `datetime.utcnow` (timezone-naive for SQLite compatibility).
- NF-DATA-02: UUID primary keys SHALL use Python `uuid.uuid4` with SQLite `TEXT` storage.
- NF-DATA-03: JSON fields SHALL use SQLAlchemy `JSON` type (stored as TEXT in SQLite).
- NF-DATA-04: The async session SHALL be scoped via FastAPI dependency injection (`yield` pattern).
- NF-DATA-05: Schema auto-create is MVP-only; a PostgreSQL migration path SHALL be documented in model comments.

## Data Schema

### Entity-Relationship Overview

```
Customer ──> Application ──> Credit
  │              │
  │              └──> Document
  │
  ├──> Session ──> Conversation
  ├──> Policy ──> Insurance
  ├──> Opportunity ──> Notification
  ├──> Notification
  └──> Claim ──> Document
```

### Customer
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| documento_identidad | String(50) | `unique`, `index`, `nullable=False` |
| nombre_completo | String(200) | `nullable=False` |
| email | String(200) | `nullable=True` |
| telefono | String(20) | `nullable=True` |
| salario | Float | `nullable=True` |
| tipo_contrato | String(50) | `nullable=True` |
| antiguedad_meses | Integer | `nullable=True` |
| score_crediticio | Float | `nullable=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Product
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| nombre | String(200) | `nullable=False` |
| tipo | String(50) | `nullable=False` — `"credito"` / `"seguro"` |
| descripcion | Text | `nullable=True` |
| monto_maximo | Float | `nullable=True` |
| modalidad | String(50) | `nullable=True` |
| activo | Boolean | `default=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Credit (extends Application via FK)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| application_id | UUID (FK→application) | `unique`, `nullable=False` |
| monto_solicitado | Float | `nullable=False` |
| plazo_meses | Integer | `nullable=False` |
| destino | String(200) | `nullable=True` |
| tasa_interes | Float | `nullable=True` |
| modalidad_pago | String(50) | `nullable=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Insurance
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| nombre | String(200) | `nullable=False` |
| cobertura | Text | `nullable=True` |
| publico_objetivo | String(200) | `nullable=True` |
| prima_base | Float | `nullable=True` |
| activo | Boolean | `default=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Policy (issued insurance contract)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| insurance_id | UUID (FK→insurance) | `nullable=False` |
| numero_poliza | String(100) | `nullable=True` |
| prima | Float | `nullable=False` |
| estado | String(50) | `default="activo"` |
| fecha_inicio | DateTime | `nullable=False` |
| fecha_fin | DateTime | `nullable=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Claim
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| policy_id | UUID (FK→policy) | `nullable=True` |
| estado | String(50) | `default="reportado"` |
| descripcion | Text | `nullable=True` |
| monto_reclamado | Float | `nullable=True` |
| fecha_evento | DateTime | `nullable=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Application (polymorphic form submission)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| product_id | UUID (FK→product) | `nullable=True` |
| tipo | String(50) | `nullable=False` — `"credito"` / `"seguro"` |
| estado | String(50) | `default="iniciada"` |
| form_data | JSON | `default={}` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Document
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| application_id | UUID (FK→application) | `nullable=True` |
| claim_id | UUID (FK→claim) | `nullable=True` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| tipo_documento | String(50) | `nullable=False` |
| file_path | String(500) | `nullable=False` |
| extracted_text | Text | `nullable=True` |
| ocr_processed | Boolean | `default=False` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Conversation
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| session_id | UUID (FK→session) | `nullable=False` |
| rol | String(20) | `nullable=False` — `"user"` / `"assistant"` |
| mensaje | Text | `nullable=False` |
| metadata_json | JSON | `nullable=True` |
| created_at | DateTime | `default=utcnow` |

### Session (conversation state machine)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=True` |
| estado_actual | String(50) | `default="inicio"` |
| campos_diligenciados | JSON | `default={}` |
| ultima_intencion | String(100) | `nullable=True` |
| activa | Boolean | `default=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Opportunity
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| product_id | UUID (FK→product) | `nullable=True` |
| tipo | String(50) | `nullable=False` |
| estado | String(50) | `default="pendiente"` |
| descripcion | Text | `nullable=True` |
| score | Float | `nullable=True` |
| created_at | DateTime | `default=utcnow` |
| updated_at | DateTime | `default=utcnow, onupdate=utcnow` |

### Notification
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID (PK) | `default=uuid4` |
| customer_id | UUID (FK→customer) | `nullable=False` |
| tipo | String(20) | `nullable=False` — `"wpp"` / `"email"` |
| asunto | String(200) | `nullable=True` |
| contenido | Text | `nullable=False` |
| estado | String(50) | `default="pendiente"` |
| leida | Boolean | `default=False` |
| scheduled_at | DateTime | `nullable=True` |
| sent_at | DateTime | `nullable=True` |
| responded_at | DateTime | `nullable=True` |
| error_log | Text | `nullable=True` |
| intento_actual | Integer | `default=0` |
| max_intentos | Integer | `default=1` |
| opportunity_id | UUID (FK→opportunities) | `nullable=True` |
| created_at | DateTime | `default=utcnow` |

## File Structure

```
backend/
├── app/
│   ├── database.py                    # async_engine, AsyncSession, get_db dependency
│   └── models/
│       ├── __init__.py                # Base + re-export all models
│       ├── customer.py
│       ├── product.py
│       ├── credit.py
│       ├── insurance.py
│       ├── policy.py
│       ├── claim.py
│       ├── application.py
│       ├── document.py
│       ├── conversation.py
│       ├── session.py
│       ├── opportunity.py
│       └── notification.py
├── data/
│   └── .gitkeep
```

## Dependencies

**Inter-capability:**
- `health-check` (C01) — health endpoint reads DB status via `get_db` dependency
- `fastmcp-server` (C04) — MCP tools query models via shared session
- `chat-api-stub` (C03) — future chat will persist messages via Conversation model
- `docker-infrastructure` (C05) — DB file path must match volume mount
- `outbound-prospect-selection` — queries Customer/Opportunity models
- `outbound-scheduler` — creates Notification records with new fields
- `outbound-api` — reads/updates Notification records via REST

**External:**
- `sqlalchemy[asyncio]>=2.0.36`
- `aiosqlite>=0.20.0`

## Scenarios

### Scenario 1: All models created on startup
**Given** the database directory exists
**When** the app factory calls `create_all()`
**Then** the `proteccion360.db` file is created
**And** all 12 tables exist in the database

### Scenario 2: Session lifecycle via dependency injection
**Given** a FastAPI route handler
**When** `get_db` dependency is injected
**Then** an `AsyncSession` is opened
**And** the session is closed after the response is sent

### Scenario 3: Customer creation
**Given** a valid customer payload
**When** persisted via `AsyncSession`
**Then** the customer has a UUID `id`, `created_at`, and `updated_at`
**And** the `documento_identidad` is unique across all customers

### Scenario 4: Notification with outbound fields
**Given** a Notification record created by the outbound scheduler
**When** persisted via `AsyncSession`
**Then** the Notification has `scheduled_at`, `sent_at`, `responded_at`, `error_log`, `intento_actual`, `max_intentos`, and `opportunity_id`
**And** `opportunity_id` references an existing Opportunity record

### Scenario 5: Notification-Opportunity relationship
**Given** a Notification with `opportunity_id` set
**When** queried via SQLAlchemy relationship
**Then** the related Opportunity is accessible via `notification.opportunity`
