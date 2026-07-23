# Delta for chat-sessions

> **Change:** `fase3-recoleccion-conversacional`
> **Based on:** `openspec/specs/chat-sessions/spec.md`

## MODIFIED Requirements

### Requirement: Field tracking with progressive updates

The system SHALL update `session.campos_diligenciados` progressively turn by turn, merging new fields into the existing JSON without overwriting previously collected data. The ChatService SHALL extract field names from the AI response's `campos_actualizados` metadata and persist the merged result after each AI turn.
(Previously: `campos_diligenciados` was updated in bulk — fields extracted from AI response metadata or detected intent in a single pass.)

#### Scenario: Fields accumulated progressively
- GIVEN a session with `campos_diligenciados={"nombre": "Juan"}`
- WHEN the AI updates with `campos_actualizados=["salario"]` and value `2500000`
- THEN `campos_diligenciados` SHALL contain `{"nombre": "Juan", "salario": 2500000}`
- AND the previous `nombre` field SHALL NOT be lost

#### Scenario: Field overwrite on update
- GIVEN `campos_diligenciados={"nombre": "Juan"}`
- WHEN the user corrects their name to "Juan Carlos"
- THEN `campos_diligenciados["nombre"]` SHALL be `"Juan Carlos"`
- AND no duplicate entries exist

### Requirement: State machine with completion flow

When all required fields are collected and the user confirms, the system SHALL call `create_application()`. After success, the system SHALL clear `session.campos_diligenciados` (set to `{}`) and set `session.estado_actual` to `"completado"`.
(Previously: State transitions were based solely on AI intent detection. There was no completion/cleanup flow tied to data collection.)

#### Scenario: Session completed after confirmation
- GIVEN all required fields collected and user confirmed
- WHEN `create_application()` succeeds
- THEN `session.campos_diligenciados` is `{}`
- AND `session.estado_actual` is `"completado"`

#### Scenario: Completion reversed on failure
- GIVEN `create_application()` fails (e.g., DB error)
- WHEN the error is returned
- THEN `session.campos_diligenciados` SHALL retain its previous value
- AND `session.estado_actual` SHALL NOT change

## ADDED Requirements

### Requirement: Form schema versioning

The `Session` model SHALL include a `form_schema_version` field (string, nullable). When a session enters `"recopilando_datos"` state, the system SHALL set `form_schema_version` to the current version identifier of the `FormSchema` (e.g., `"1.0"`). This enables auditing which schema version was used for collection.

#### Scenario: Version set on data collection start
- GIVEN a session at `estado_actual="inicio"`
- WHEN the session transitions to `"recopilando_datos"`
- THEN `form_schema_version` SHALL be set to a non-null version string

#### Scenario: Version persists through session
- GIVEN a session with `form_schema_version="1.0"`
- WHEN the session reaches `"completado"`
- THEN `form_schema_version` SHALL remain `"1.0"` (immutable after creation)
