# Tasks: Proactive WhatsApp Outreach

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500–700 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

## Phase 1: Data Model

- [x] 1.1 Modify `backend/app/models/notification.py` — added: `scheduled_at`, `sent_at`, `responded_at`, `error_log`, `intento_actual` (default=0), `max_intentos` (default=2), `opportunity_id` FK, `opportunity` relationship
- [x] 1.2 Modify `backend/app/models/opportunity.py` — added `notifications` back_populates relationship
- [x] 1.3 Verified both models re-exported in `backend/app/models/__init__.py`

## Phase 2: Service Layer

- [x] 2.1 Create `backend/app/services/outbound_service.py` — `Prospect` dataclass + `OutboundService.__init__` with session_maker and ai_client
- [x] 2.2 Implement `OutboundService.select_prospects(limit=50)` — iterates eligible customers: contract type & tenure (indefinido ≥2m / temporal≥6m), salary ≥ 1 SMMLV, skips existing products (Policy→Credit fallback), skips recently notified (30d), joins Opportunity for scoring, sorts DESC, limits
- [x] 2.3 Implement `OutboundService.generate_message(prospect)` — calls `AIClient.chat_raw()` with system prompt + profile; falls back to static template on None/exception/empty reply
- [x] 2.4 Implement `OutboundService.create_notification(prospect, content)` — creates and persists `Notification(estado="pendiente", scheduled_at=now)` with FK to opportunity
- [x] 2.5 Implement `OutboundService.process_reattempts()` — queries sent notifications with `responded_at IS NULL` and `sent_at +5d`, increments `intento_actual`, creates new pending retry records
- [x] 2.6 Create `backend/tests/test_outbound_service.py` — 15 tests covering: empty DB, contract filtering, income filtering, existing product exclusion (Policy→Credit fallback + both-products skip), top-N limit, opportunity score ordering, recent notification exclusion, AI fallback (no client, exception, empty reply), AI integration, notification persistence, reattempt creation, recent-sent skip

## Phase 3: Scheduler

- [x] 3.1 Create `backend/app/scheduler.py` — OutboundScheduler wrapping AsyncIOScheduler with 15-min interval, _run_outbound pipeline (select → generate → notify + re-attempts)
- [x] 3.2 Modify `backend/app/main.py` — init OutboundService in lifespan, start/stop scheduler, include outbound_router
- [x] 3.3 Modify `backend/requirements.txt` — add `apscheduler>=3.10.4`

## Phase 4: API

- [x] 4.1 Create `backend/app/routers/outbound.py` — 4 endpoints: GET /outbound/pending, POST /outbound/{id}/sent, /responded, /failed; all with 404 on unknown ID, limit validated 1–50; test: 3 router tests + 15 service tests

## Phase 5: WhatsApp Bot

- [x] 5.1 Modify `src/lib/api-client.ts` — added `getPendingOutbound`, `markOutboundSent`, `markOutboundResponded`, `markOutboundFailed` with `PendingNotification` type
- [x] 5.2 Create `src/services/outbound-poller.ts` — interval cada 5s polling `/outbound/pending`, sending via sock.sendMessage(), reporting back via mutation endpoints
- [x] 5.3 Modify `src/lib/baileys/handler.ts` — import and call startOutboundPoller(sock) at end of setupHandler
