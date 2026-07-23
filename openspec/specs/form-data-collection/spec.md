# Form Data Collection Specification

> **Capability:** New — `form-data-collection`
> **Change:** `fase3-recoleccion-conversacional`
> **Date:** 2026-07-16

## Purpose

Define the FormSchema contract that structures credit application fields and the AI-driven progressive collection protocol. The AI uses this schema to guide the conversation, track completeness, and trigger application creation.

## Requirements

### Requirement: FormSchema contract

The system SHALL define a `FormSchema` as an internal JSON structure with sections, each containing fields. Each field SHALL specify: `nombre`, `tipo` (string|number|date|email|select), `requerido` (bool), `validaciones` (min/max/pattern/enum), `prompt_question` (how to ask), and `seccion`. Sections SHALL be ordered logically (e.g., personal data first, financial data second).

#### Scenario: Schema defines all credit form fields
- GIVEN the `FormSchema` is loaded
- WHEN inspected
- THEN it contains at least the fields: nombre, documento, email, telefono, salario, monto_solicitado, plazo, destino
- AND each field has `seccion`, `tipo`, `requerido`, `validaciones`, and `prompt_question`

### Requirement: Progressive field collection

The AI SHALL ask fields one at a time, in logical order within each section (required first, optional after). The AI SHALL NOT ask multiple fields in a single turn unless clarifying. The AI SHALL update `session.campos_diligenciados` after each user response with the field name and value.

#### Scenario: Fields collected sequentially
- GIVEN a session at `estado_actual="recopilando_datos"`
- WHEN the AI asks for `nombre` and the user responds
- THEN `session.campos_diligenciados` SHALL contain `{"nombre": "Juan Perez"}`
- AND the AI proceeds to the next required field in the same section

#### Scenario: Required fields before optional
- GIVEN a section with both required and optional fields
- WHEN all required fields in that section are collected
- THEN the AI SHALL ask optional fields in the same section before moving to the next section

### Requirement: Optional field skip

If the user explicitly chooses not to provide an optional field, the system SHALL save it as `null` in `campos_diligenciados` and continue to the next field.

#### Scenario: User skips optional field
- GIVEN the AI asks an optional field (e.g., `telefono_alternativo`)
- WHEN the user says "no tengo" or "prefiero no decirlo"
- THEN `campos_diligenciados["telefono_alternativo"]` SHALL be `null`
- AND the AI proceeds to the next field

### Requirement: Approximation for unknown values

If the user does not know an exact value (e.g., exact salary), the AI SHALL ask for an approximation. The system SHALL accept approximate numeric values.

#### Scenario: User provides approximation
- GIVEN the AI asks for `salario`
- WHEN the user says "no sé exacto, como 2 millones"
- THEN `campos_diligenciados["salario"]` SHALL be `2000000`
- AND the field is marked as collected

### Requirement: Completeness detection

The AI SHALL track collection progress by comparing collected fields against the `FormSchema`. When all REQUIRED fields across all sections have a non-null value in `campos_diligenciados`, the AI SHALL summarize the collected data and ask the user for confirmation.

#### Scenario: All required fields complete
- GIVEN `campos_diligenciados` has all required fields populated
- WHEN the last required field is collected
- THEN the AI SHALL present a summary of all collected data
- AND the AI SHALL ask: "¿Confirmás la solicitud?"

#### Scenario: Required field still missing
- GIVEN some required fields remain empty
- WHEN the AI evaluates completeness
- THEN the AI SHALL continue asking the next missing required field
- AND SHALL NOT offer confirmation

### Requirement: Confirmation triggers `create_application`

When the user confirms, the system SHALL call the `create_application()` tool with the collected `form_data`. The tool SHALL create `Application` + `Credit` in an atomic transaction. After success, `session.campos_diligenciados` SHALL be cleared and `session.estado_actual` SHALL become `"completado"`.

#### Scenario: Confirmation succeeds
- GIVEN all required fields are collected and the user confirms
- WHEN `create_application()` is called
- THEN `Application` and `Credit` rows are created
- AND `session.campos_diligenciados` is cleared
- AND `session.estado_actual` becomes `"completado"`

#### Scenario: Confirmation declined
- GIVEN the AI asks for confirmation
- WHEN the user declines or wants to change a field
- THEN the AI SHALL ask which field to correct
- AND the session remains in `"recopilando_datos"` state

## Dependencies

- `chat-sessions` — `session.campos_diligenciados`, `session.estado_actual`
- `chat-api-stub` — AI system prompt injection
- `mcp-domain-tools` — `create_application()` tool
