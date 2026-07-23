# Delta for chat-api-stub

> **Change:** `fase2-chat-ia-mcp`
> **Source:** `openspec/specs/chat-api-stub/spec.md` (C03)

## ADDED Requirements

### Requirement: AI-backed response

The system SHALL process chat messages via `AIClient.chat()` or `AIClient.chat_with_tools()` when `SILICONFLOW_API_KEY` is configured. The endpoint SHALL return a `ChatResponse` with the AI-generated `reply`, the active `session_id`, a `timestamp`, and optional `usage` metadata.

(Previously: no AI integration)

#### Scenario: AI responds to user message
- GIVEN `SILICONFLOW_API_KEY` is set and a session exists
- WHEN `POST /chat` is called with `{"message": "Hola, quiero un crédito"}`
- THEN the response is `200 OK`
- AND `reply` contains the AI-generated response text
- AND `session_id` matches the active session

### Requirement: Echo fallback

The system SHALL fall back to echo behavior when `SILICONFLOW_API_KEY` is not set or empty, returning `"Echo: {message}"` as `reply`.

(Previously: N/A — echo was the only behavior)

#### Scenario: No API key falls back to echo
- GIVEN `SILICONFLOW_API_KEY` is not set
- WHEN `POST /chat` is called with `{"message": "Hola"}`
- THEN `reply` equals `"Echo: Hola"`

### Requirement: Conversation persistence

The system SHALL persist each user message and its AI reply in the `conversations` table, linked by `session_id`. The user message SHALL be saved before the AI call; the AI reply SHALL be saved after.

(Previously: no persistence)

#### Scenario: Messages persisted for session
- GIVEN a chat session
- WHEN a user message is sent and AI replies
- THEN a `Conversation` row exists for `rol="user"` with the user's text
- AND a `Conversation` row exists for `rol="assistant"` with the AI's reply

### Requirement: History loading

The system SHALL load the last N conversation messages from the `conversations` table and include them as context for the AI call. N SHALL default to 20 and be configurable via settings.

(Previously: no history)

#### Scenario: History loaded as context
- GIVEN a session with 5 prior exchanges
- WHEN a new message is sent
- THEN the AI call includes the last 20 messages as context history

## MODIFIED Requirements

### Requirement: F-CHAT-01 — POST /chat endpoint

The system SHALL expose a `POST /chat` endpoint accepting a JSON body with `{"message": "<string>", "session_id": "<optional-uuid>"}`. If `session_id` is omitted or empty, the system SHALL auto-generate a new UUID and create a `Session` row.
(Previously: accepted `message` only, no session auto-creation)

#### Scenario: Session auto-created on first message
- GIVEN no prior session
- WHEN `POST /chat` is called with `{"message": "Hola"}`
- THEN a `session_id` is auto-generated and returned in the response
- AND a `Session` row is created in the database with `estado_actual="inicio"`

#### Scenario: Existing session loaded
- GIVEN an existing session with id `abc-123`
- WHEN `POST /chat` is called with `{"message": "Hola", "session_id": "abc-123"}`
- THEN the response includes `session_id: "abc-123"`
- AND the session history is loaded as context

### Requirement: F-CHAT-02 — Response format

The endpoint SHALL return a JSON response with `{"reply": "<string>", "session_id": "<uuid>", "timestamp": "<ISO-8601>", "usage": {"prompt_tokens": <int>, "completion_tokens": <int>, "total_tokens": <int>} | null}`.
(Previously: returned echo with optional session_id from header)

#### Scenario: Full response with usage
- GIVEN a successful AI call
- WHEN the endpoint responds
- THEN the body contains `reply`, `session_id`, `timestamp`, and `usage`

### Requirement: F-CHAT-05 — ApiClient.sendMessage

An `ApiClient` class SHALL exist in `frontend/src/lib/api.ts` with a `sendMessage(message, sessionId?)` method returning `Promise<ChatResponse>`. The method SHALL accept an optional `sessionId` parameter.
(Previously: `sendMessage(message)` only)

#### Scenario: ApiClient sends with session
- GIVEN the frontend is initialized
- WHEN `apiClient.sendMessage("Hola", "abc-123")` is called
- THEN a POST request is sent to `/api/chat` with `{"message": "Hola", "session_id": "abc-123"}`
- AND the promise resolves with a `ChatResponse` including `reply`, `session_id`, `timestamp`

## REMOVED Requirements

### Requirement: F-CHAT-03 — Echo prefix

(Reason: replaced by AI-backed response; echo preserved as fallback only)
(Migration: clients SHALL NOT depend on `"Echo:"` prefix — check `reply` content instead)

### Requirement: NF-CHAT-01 — Under 50ms

(Reason: AI calls inherently take 2–30s; timeout set at 30s per call)
(Migration: frontend SHALL show typing indicator while waiting)
