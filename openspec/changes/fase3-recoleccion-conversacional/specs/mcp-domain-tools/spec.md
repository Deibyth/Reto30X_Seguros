# Delta for mcp-domain-tools

> **Change:** `fase3-recoleccion-conversacional`
> **Based on:** `openspec/specs/mcp-domain-tools/spec.md`

## ADDED Requirements

### Requirement: create_application tool

The system SHALL expose an MCP tool `create_application(tipo, customer_id, form_data, monto_solicitado, plazo_meses, destino)` that creates an `Application` row and a `Credit` row in a single atomic transaction.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tipo` | `str` | Yes | MUST be `"credito"` |
| `customer_id` | `str` (UUID) | Yes | Customer owning the application |
| `form_data` | `dict` | Yes | Complete collected fields JSON from `campos_diligenciados` |
| `monto_solicitado` | `float` | Yes | Requested credit amount |
| `plazo_meses` | `int` | Yes | Term in months |
| `destino` | `str` | Yes | Purpose of the credit |

The tool SHALL:
- Create `Application` with `tipo="credito"`, `estado="iniciada"`, `form_data` set to the JSON payload, `customer_id` linked
- Create `Credit` with `monto_solicitado`, `plazo_meses`, `destino`, `tasa_interes` (default from config), linked to the `Application`
- Optionally link an existing `Document` if a document_id is present in `form_data` (via `Document.application_id`)

#### Scenario: Application + Credit created atomically
- GIVEN a customer with id `cust-123` and all required form_data
- WHEN `create_application("credito", "cust-123", {...}, 5000000, 24, "Libre inversion")` is called
- THEN an `Application` row is created with `estado="iniciada"`
- AND a `Credit` row is created linked to that application
- AND `Credit.monto_solicitado` is `5000000`
- AND `Credit.plazo_meses` is `24`

#### Scenario: Database error rolls back transaction
- GIVEN a database constraint violation (e.g., invalid `customer_id`)
- WHEN `create_application()` is called
- THEN no `Application` row is created
- AND no `Credit` row is created
- AND the tool returns an error dict with `error` field describing the failure

#### Scenario: Document linked if present
- GIVEN `form_data` contains `document_id: "doc-456"`
- WHEN `create_application()` succeeds
- THEN `Application.document_id` SHALL reference document `"doc-456"`
- AND the `Document` SHALL have its `application_id` updated

### Requirement: Atomic session cleanup

After `create_application()` succeeds, the calling code SHALL clear `session.campos_diligenciados` and set `session.estado_actual` to `"completado"` in the SAME transaction (or in a subsequent atomic update). The system SHALL NOT leave sessions in an inconsistent state.

#### Scenario: Session cleaned after successful creation
- GIVEN `create_application()` succeeded
- WHEN the session update completes
- THEN `session.campos_diligenciados` is `{}`
- AND `session.estado_actual` is `"completado"`

#### Scenario: Session unchanged on failure
- GIVEN `create_application()` raised an exception
- WHEN the error is caught
- THEN `session.campos_diligenciados` SHALL be unchanged
- AND `session.estado_actual` SHALL be unchanged
