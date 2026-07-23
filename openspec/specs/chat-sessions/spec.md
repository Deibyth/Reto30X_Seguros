# Chat Sessions Specification

> **Capability:** C06 — `chat-sessions`
> **Change:** `fase2-chat-ia-mcp`
> **Date:** 2026-07-16

## Purpose

Manage chat session lifecycle: create or load sessions, persist each conversation turn, track session state for future form-filling and opportunity detection.

## Requirements

### Requirement: Session auto-creation

The system SHALL create a `Session` row when the first message is sent without a `session_id`. The `id` SHALL be a UUID4. `estado_actual` SHALL default to `"inicio"`. `campos_diligenciados` SHALL default to `{}`. `ultima_intencion` SHALL be `null`.

#### Scenario: New session created
- GIVEN no `session_id` in the request
- WHEN `POST /chat` is called
- THEN a `Session` is created with `estado_actual="inicio"`
- AND the new `session_id` is returned in the response

### Requirement: Session loading by ID

The system SHALL load an existing session when a valid `session_id` is provided. If the session does not exist, the system SHALL return `404 Not Found`.

#### Scenario: Existing session loaded
- GIVEN a session with id `abc-123` exists
- WHEN `POST /chat` is called with `session_id: "abc-123"`
- THEN the session is loaded and its history is used as AI context

#### Scenario: Invalid session rejected
- GIVEN no session with id `invalid-id` exists
- WHEN `POST /chat` is called with `session_id: "invalid-id"`
- THEN the response is `404 Not Found`

### Requirement: State machine tracking

The system SHALL update `session.estado_actual` to reflect the conversation phase. Valid states SHALL include: `inicio`, `recopilando_datos`, `evaluando`, `ofreciendo_producto`, `completado`. The ChatService SHALL determine state transitions based on the AI's detected intent.

#### Scenario: State transitions on intent
- GIVEN a session at `estado_actual="inicio"`
- WHEN the AI detects the user wants a credit
- THEN the system updates `estado_actual` to `recopilando_datos`

### Requirement: Field tracking

The system SHALL update `session.campos_diligenciados` with structured data the user provides (e.g., `{"nombre": "Juan", "salario": 2500000}`). The ChatService SHALL extract fields from the AI response metadata or detected intent.

#### Scenario: Fields accumulated
- GIVEN a session with `campos_diligenciados={"nombre": "Juan"}`
- WHEN the user provides their salary
- THEN `campos_diligenciados` SHALL contain both `nombre` and `salario`

### Requirement: Intent tracking

The system SHALL update `session.ultima_intencion` on each message turn to the AI's best guess of user intent. Values SHALL include: `solicitar_credito`, `consultar_producto`, `simular_cuota`, `info_seguro`, `ninguna`.

#### Scenario: Intent updated per turn
- GIVEN a session
- WHEN a user message about "quiero un crédito" is processed
- THEN `ultima_intencion` is set to `solicitar_credito`

### Requirement: Conversation persistence

The system SHALL persist each user message as `Conversation(rol="user")` and each AI reply as `Conversation(rol="assistant")`, both linked to the active `session_id`. Persistence SHALL be atomic — user message saved before AI call, AI reply saved after.

#### Scenario: Both turns persisted
- GIVEN a chat session
- WHEN the AI responds to a user message
- THEN the `conversations` table contains two new rows for that `session_id`
- AND the user row `created_at` is before the assistant row

### Requirement: History window

The system SHALL load the most recent N conversation messages for AI context. N SHALL default to 20. Only messages with `rol="user"` or `rol="assistant"` SHALL be included (not system messages).

#### Scenario: History truncated to N
- GIVEN a session with 30 conversation turns
- WHEN a new message is processed
- THEN only the latest 20 messages are passed as AI context

#### Scenario: Empty history loaded
- GIVEN a brand new session
- WHEN the first message is processed
- THEN the history list is empty (only system prompt passed)
