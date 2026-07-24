# Design: Proactive WhatsApp Outreach

## Technical Approach

Single-batch pipeline driven by an in-process APScheduler job within the existing FastAPI lifespan. Prospect selection queries Customer/Opportunity with eligibility rules in a single SQL pass. AI message generation calls `AIClient.chat_raw()` directly (not ChatService, which is conversational). Messages land as Notification records the WhatsApp bot polls via REST — the bot already has an outbox pattern, so its changes are minimal.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Scheduler runtime | In-process APScheduler (lifespan) | Separate cron container, Celery, RQ | No infra overhead; 15-min interval tolerates restarts; existing lifespan pattern is proven |
| Message generation | `AIClient.chat_raw()` with a dedicated prompt | `ChatService.process_message()`, static templates | ChatService expects session/message loop state; outbound is one-shot generation. Using AIClient directly avoids session pollution |
| Prospect selection strategy | SQL query in service (no ML) | Precomputed ML scoring table | MVP scope; rules are deterministic (contract, income, existing products). ML can layer on later via Opportunity.score |
| API ↔ Bot contract | REST polling (`GET /outbound/pending`) | Webhook (backend pushes), message queue | Bot already polls; webhook adds delivery complexity. REST keeps the outbox pattern symmetric |
| Re-attempt state | `estado="reintento"` with `intento_actual` counter | Separate re_attempts table | Simpler queries; single Notification table remains source of truth. A single retry fits in existing schema |

## Data Flow

```
APScheduler (every 15 min)
    │
    ▼
OutboundService.select_prospects()
    │  ┌─ Customer (tipo_contrato, salario, score_crediticio)
    │  ├─ Opportunity (score DESC)
    │  ├─ Policy / Credit (exclude if already held)
    │  └─ Notification (exclude if pending/recently notified)
    │
    ▼
OutboundService.generate_message(customer, product_type)
    │  └─ AIClient.chat_raw(system_prompt + profile) → LLM response
    │
    ▼
OutboundService.create_notification(customer, message, opportunity)
    │  └─ Notification(estado="pendiente", scheduled_at=now)
    │
    ▼
  ┌──── Wait for bot poll ────┐
  │                           │
  ▼                           ▼
Bot: GET /outbound/pending → Bot: POST /outbound/{id}/sent
  (sends via WhatsApp)          (updates estado="enviado")
```

**Re-attempt path** (5 days later on same APScheduler tick):
```
Scheduler detects sent notification with responded_at=NULL, sent_at +5d
    → estado="reintento", intento_actual++
    → bot re-polls, sends re-attempt message
```

## File Changes

### Backend (Reto30X_Credit)

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/notification.py` | Modify | Add `scheduled_at`, `sent_at`, `responded_at`, `error_log`, `intento_actual`, `max_intentos`, `opportunity_id` FK, and `opportunity` relationship |
| `backend/app/services/outbound_service.py` | Create | `OutboundService` — `select_prospects()`, `generate_message()`, `create_notification()`, `process_reattempts()` |
| `backend/app/routers/outbound.py` | Create | `GET /outbound/pending`, `POST /outbound/{id}/sent`, `/responded`, `/failed` |
| `backend/app/scheduler.py` | Create | APScheduler setup, interval job, lifespan integration helpers |
| `backend/app/main.py` | Modify | Init `OutboundService` in lifespan, start/stop scheduler, include outbound router |
| `backend/requirements.txt` | Modify | Add `apscheduler>=3.10.4` |

### WhatsApp Bot (Reto30X_whatsapp)

| File | Action | Description |
|------|--------|-------------|
| `src/lib/api-client.ts` | Modify | Add `getPendingOutbound()`, `markOutboundSent()`, `markOutboundResponded()`, `markOutboundFailed()` |
| `src/services/outbound-poller.ts` | Create | Periodic poller (every 5s) for `GET /outbound/pending`, sends via `sock.sendMessage()`, reports back via mutation APIs |
| `src/lib/baileys/handler.ts` | Modify | Start outbound-poller alongside existing outbox interval |

## Interfaces / Contracts

### OutboundService

```python
# backend/app/services/outbound_service.py

@dataclass
class Prospect:
    customer: Customer
    recommended_product_type: str  # "credito" | "seguro"
    opportunity: Opportunity | None
    score: float

class OutboundService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        ai_client: AIClient | None,
    ) -> None

    async def select_prospects(self, limit: int = 50) -> list[Prospect]
    async def generate_message(self, prospect: Prospect) -> str
    async def create_notification(self, prospect: Prospect, content: str) -> Notification
    async def process_reattempts(self) -> int  # returns count
```

### REST API Contract

```python
# GET /outbound/pending?limit=20
# Response 200:
{
  "items": [
    {
      "notification_id": "uuid",
      "phone": "+573001234567",
      "content": "¡Hola Juan!...",
      "customer_name": "Juan Pérez"
    }
  ]
}

# POST /outbound/{id}/sent      → 200 {"status": "ok"}
# POST /outbound/{id}/responded  → 200 {"status": "ok"}
# POST /outbound/{id}/failed     → 200 {"status": "ok"}
#   body: {"error": "message"}
# All mutations: 404 if id not found
```

### Bot API Client (TypeScript)

```typescript
// src/lib/api-client.ts — new exports
export type PendingNotification = {
  notification_id: string;
  phone: string;
  content: string;
  customer_name: string;
};

export async function getPendingOutbound(limit = 20): Promise<PendingNotification[]>;
export async function markOutboundSent(id: string): Promise<void>;
export async function markOutboundResponded(id: string): Promise<void>;
export async function markOutboundFailed(id: string, error: string): Promise<void>;
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `select_prospects()` rules | Mock session + seeded Customer/Opportunity rows; test each exclusion criterion in isolation |
| Unit | `generate_message()` fallback | Mock AIClient to raise timeout; assert static template returned with name + product |
| Unit | `process_reattempts()` | Seed sent Notification older than 5d, no response; assert new Notification created |
| Integration | API endpoints | `httpx.AsyncClient` with `TestClient`; test full CRUD lifecycle: pending → sent → responded |
| Integration | Scheduler lifecycle | Start/stop scheduler via lifespan events; assert job registered and runs once |
| E2E (bot) | Poller happy path | Mock `api-client`, mock `sock.sendMessage`; assert poller processes and marks sent |

No migration needed — all new Notification fields are nullable. Schema auto-create will add them on next restart.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. API endpoints follow existing health/chat patterns. APScheduler runs in-process and does not spawn subprocesses.

## Migration / Rollout

No data migration required. All new columns are nullable with defaults. Schema update happens automatically on next `Base.metadata.create_all()`. Rollback: remove APScheduler start line from lifespan and re-deploy; new columns remain in schema (harmless).

## Open Questions

- None — all decisions resolved in proposal and specs.
