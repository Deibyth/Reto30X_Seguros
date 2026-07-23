# Delta for chat-api-stub

> **Change:** `fase3-recoleccion-conversacional`
> **Based on:** `openspec/specs/chat-api-stub/spec.md`

## MODIFIED Requirements

### Requirement: AI system prompt with FormSchema

The system SHALL inject the complete `FormSchema` serialized as JSON into the AI system prompt. The system prompt SHALL include instructions for progressive field collection: ask fields one at a time, in logical section order, required before optional; update `session.campos_diligenciados` after each turn; track completeness against the schema; when all required fields are complete, summarize and ask confirmation.
(Previously: The endpoint echoed user messages. System prompt was injected with session context and history, with no FormSchema.)

#### Scenario: Echo response with form data collection
- GIVEN the backend is running with FormSchema loaded
- WHEN `POST /chat` is called with `{"message": "Mi nombre es Juan"}`
- THEN the response is `200 OK`
- AND the `reply` contains the next question or confirmation
- AND `campos_actualizados` contains `["nombre"]`

#### Scenario: Form instruction override
- GIVEN a session in `"recopilando_datos"` state
- WHEN the user sends a message
- THEN the system prompt SHALL include the serialized `FormSchema`
- AND the AI SHALL follow progressive collection instructions over generic chat

## ADDED Requirements

### Requirement: Response metadata for field tracking

The chat response SHALL include a `campos_actualizados` field in its metadata, listing which fields from `campos_diligenciados` were added or updated in this turn.

The system SHALL also include `completitud_pct: float` (0.0–100.0) indicating the percentage of required fields collected.

#### Scenario: Field metadata in response
- GIVEN user just provided their salary
- WHEN `POST /chat` returns
- THEN the response metadata SHALL include `campos_actualizados: ["salario"]`
- AND `completitud_pct` reflects the updated percentage

#### Scenario: Empty campo_actualizados
- GIVEN the AI asks a question without the user providing data
- WHEN `POST /chat` returns
- THEN `campos_actualizados` SHALL be an empty list

### Requirement: AI follows progressive collection protocol

The AI system prompt SHALL instruct the AI to: (1) ask fields one field at a time, never multiple in one turn; (2) prioritize required fields in each section before optional ones; (3) update `session.campos_diligenciados` by calling the appropriate tool or returning structured metadata; (4) track completeness against the FormSchema; (5) when all required fields are filled, summarize and ask "¿Confirmás la solicitud?".

#### Scenario: Single field asked per turn
- GIVEN the user has not provided any data
- WHEN the session enters `"recopilando_datos"`
- THEN the AI asks for a single field (e.g., "¿Cuál es tu nombre completo?")
- AND SHALL NOT ask for multiple fields in the same response

#### Scenario: Confirmation request on completion
- GIVEN all required fields are collected
- WHEN the AI generates the next reply
- THEN the reply SHALL include a summary of collected data
- AND SHALL include "¿Confirmás la solicitud?"

## API Contract — Extended

Extended `ChatResponse`:

```json
{
  "reply": "string",
  "timestamp": "ISO-8601",
  "session_id": "string | null",
  "campos_actualizados": ["string"],
  "completitud_pct": 75.0
}
```
