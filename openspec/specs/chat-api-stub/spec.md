# Spec: Chat API Stub

> **Capability:** C03 — `chat-api-stub`
> **Change:** `fundacion-plataforma`
> **Date:** 2026-07-16

## Description

Placeholder chat endpoint (`POST /chat`) that echoes back the user message. This is a stub for the real AI-powered chat in Fase 2. An API client class in the frontend provides the fetch layer.

## Requirements

### Functional

- F-CHAT-01: The system SHALL expose a `POST /chat` endpoint accepting a JSON body with `{"message": "<string>"}`.
- F-CHAT-02: The endpoint SHALL return a JSON response with `{"reply": "<echo>", "timestamp": "<ISO-8601>"}`.
- F-CHAT-03: The response `reply` SHALL be the string `"Echo: {message}"` (prefix echo).
- F-CHAT-04: The endpoint SHALL accept an optional `X-Session-Id` header and return it as `session_id` in the response.
- F-CHAT-05: An `ApiClient` class SHALL exist in `frontend/src/lib/api.ts` with a `sendMessage(message)` method.
- F-CHAT-06: `sendMessage` SHALL POST to `/api/chat` (proxied by Vite to backend) and return the response JSON.
- F-CHAT-07: The `ApiClient` SHALL include a `checkHealth()` method calling `GET /api/health`.
- F-CHAT-08: The endpoint SHALL return `422 Unprocessable Entity` for missing or invalid `message` field.

### Non-Functional

- NF-CHAT-01: The chat endpoint SHALL respond in under 50ms (no business logic, no DB).
- NF-CHAT-02: The `ApiClient` SHALL use the Fetch API (no Axios or other HTTP library).
- NF-CHAT-03: The `ApiClient` SHALL NOT require authentication (MVP only).
- NF-CHAT-04: The endpoint SHALL accept CORS requests from `http://localhost:5173`.

## API Contract

### `POST /chat`

**Request:**
```json
{
  "message": "Hola, quiero un crédito"
}
```

**Headers:** `Content-Type: application/json`, optionally `X-Session-Id: uuid-string`

**Response `200 OK`:**
```json
{
  "reply": "Echo: Hola, quiero un crédito",
  "timestamp": "2026-07-16T12:00:00Z",
  "session_id": "uuid-string"
}
```

**Response `422 Unprocessable Entity`:**
```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### `ApiClient` Interface

```typescript
// frontend/src/lib/api.ts
interface ChatResponse {
  reply: string
  timestamp: string
  session_id?: string
}

interface HealthResponse {
  status: string
  version: string
  uptime_seconds: number
  database: string
  environment: string
}

class ApiClient {
  private baseUrl: string
  private sessionId: string | null

  constructor(baseUrl?: string)

  async sendMessage(message: string): Promise<ChatResponse>
  async checkHealth(): Promise<HealthResponse>
}
```

## Pydantic Models

```python
# app/routers/chat.py
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    reply: str
    timestamp: datetime
    session_id: str | None = None
```

## File Structure

```
backend/app/routers/
├── __init__.py
└── chat.py                  # POST /chat handler, ChatRequest/ChatResponse models

frontend/src/lib/
└── api.ts                   # ApiClient class with sendMessage, checkHealth
```

## Dependencies

**Inter-capability:**
- `health-check` (C01) — `ApiClient.checkHealth()` hits the health endpoint
- `data-models` (C02) — (future) chat will persist to Conversation/Session models
- `docker-infrastructure` (C05) — Vite proxy routes `/api` to backend

**External:**
- `pydantic` (included via FastAPI)
- No additional frontend dependencies beyond baseline

## Scenarios

### Scenario 1: Echo response
**Given** the backend is running
**When** `POST /chat` is called with `{"message": "Hola"}`
**Then** the response is `200 OK`
**And** `reply` equals `"Echo: Hola"`

### Scenario 2: Empty message rejected
**Given** the backend is running
**When** `POST /chat` is called with `{"message": ""}`
**Then** the response is `422 Unprocessable Entity`

### Scenario 3: API client sends message
**Given** the frontend is initialized
**When** `apiClient.sendMessage("Hola")` is called
**Then** a POST request is sent to `/api/chat`
**And** the returned promise resolves with a `ChatResponse` object

### Scenario 4: Session propagation
**Given** the frontend initialized a session
**When** a chat message is sent
**Then** the `X-Session-Id` header is included in the request
**And** the response includes the same `session_id`
