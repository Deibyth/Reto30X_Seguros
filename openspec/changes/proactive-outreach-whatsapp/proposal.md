# Proposal: Proactive WhatsApp Outreach

## Intent

Enable automated outbound WhatsApp messaging to eligible affiliated customers — offering relevant insurance/credit products via AI-personalized messages delivered through the existing WhatsApp bot outbox system.

## Scope

### In Scope

1. Extend Notification model with scheduling, retry, and opportunity FK fields
2. Prospect selection service: customer eligibility rules (employment stability, income, credit, product gaps)
3. AI message generation via existing ChatService (Groq/llama)
4. APScheduler background job (runs every 15–30 min)
5. `GET /api/outbound/pending` — bot polls pending outbound messages
6. `POST /api/outbound/{id}/sent` — bot reports delivery
7. `POST /api/outbound/{id}/responded` — bot reports user response
8. WhatsApp bot: new poller for `/outbound/pending`
9. Rate limiting: max 50 outbound messages per batch
10. Re-attempt: 1 retry after 5 days if no response (tracked in Notification)

### Out of Scope

- Email / SMS outbound
- Campaign management UI, A/B testing, analytics dashboard
- Webhook or event-driven architecture

## Capabilities

### New Capabilities

- `outbound-prospect-selection`: Identify eligible customers — stable employment (indefinido ≥2m / fixed-term ≥6m), income ≥1 SMMLV, good credit behavior, gaps in insurance/credit products
- `outbound-message-personalization`: AI-generated personalized messages via existing ChatService (Groq/llama), keyed by customer name, salary range, segment, and recommended products
- `outbound-scheduler`: APScheduler background job orchestrating selection → generation → Notification creation every 15–30 min
- `outbound-api`: REST endpoints for WhatsApp bot to poll pending outbound notifications and report delivery/response status

### Modified Capabilities

- `data-models`: Notification table extended with `scheduled_at`, `sent_at`, `error_log`, `intento_actual`, `max_intentos`, `opportunity_id` (FK → opportunities)

## Approach

| Phase | Focus | Deliverables |
|-------|-------|-------------|
| 1 | Data model | Extend Notification model + schema migration |
| 2 | Service layer | Prospect selection + AI message generation |
| 3 | Scheduling | APScheduler as app lifespan task |
| 4 | API | REST endpoints for bot consumption |
| 5 | Bot | New poller in WhatsApp bot alongside existing chat polling |

Backend logic first, bot changes minimal — the outbox pattern already exists.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/notification.py` | Modified | Add scheduling/retry/FK fields |
| `backend/app/services/outbound.py` | New | Prospect selection + message generation |
| `backend/app/routers/outbound.py` | New | REST endpoints (/pending, /sent, /responded) |
| `backend/app/main.py` | Modified | Register APScheduler in lifespan |
| `backend/app/scheduler/outbound_job.py` | New | Job definition (interval trigger) |
| `Reto30X_whatsapp/src/api-client.ts` | Modified | Add outbound API methods |
| `Reto30X_whatsapp/src/services/outbound-poller.ts` | New | Periodic `/outbound/pending` poller |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| AI message latency/cost per prospect | Med | Batch generation, not real-time |
| Dual-repo coordination | Med | Backend logic first; bot changes are thin |
| No auth on internal endpoints | Low | Rate-limiting; internal-only by convention |

## Rollback Plan

- Disable APScheduler: comment out start in lifespan
- Remove Notification records with `estado="pendiente"`
- Deploy previous WhatsApp bot version (old polling only)

## Success Criteria

- [ ] Eligible prospects are correctly identified by all eligibility rules
- [ ] AI generates coherent, personalized messages per customer profile
- [ ] Messages reach WhatsApp via bot's outbox (`sent_at` populated)
- [ ] Re-attempt fires after 5 days with no response (`intento_actual` incremented)
- [ ] User response routes into normal Anna conversation flow seamlessly
