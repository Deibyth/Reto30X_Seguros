# Exploration: Multichannel Messaging and Lightweight CRM

## Executive recommendation

Keep FastAPI and SQLite as the MVP control plane, but introduce a channel-neutral messaging core with a durable inbox/outbox. Channel ingress must persist and return `202 Accepted` before agent or webhook processing. Run Telegram through an HTTP adapter in the backend and Baileys in a small Node 20 sidecar behind the same adapter contract. Treat Baileys as a replaceable first-version transport, not as domain infrastructure.

Do not extend `Conversation` or `Customer` into catch-all multichannel records. Add explicit channel/thread/message/contact records, link them to the existing `Session` and `Customer` when known, and wrap `ChatService.process_message()` as the existing internal-agent route. Store external API keys as hashes, send them only in headers, encrypt channel credentials at rest, and never return secrets to the UI.

The change is not ready for proposal until operator authentication, CRM stage semantics, routing ownership, and tenant scope are clarified.

## Current State

### Backend and internal agent

- `backend/app/main.py:create_app()` registers only health, chat, analytics, and outbound routers. Its lifespan creates tables, initializes `ChatService`, `OutboundService`, `AnalyticsService`, and starts one in-process `OutboundScheduler`.
- `backend/app/routers/chat.py:chat_handler()` accepts text synchronously through `POST /chat`, identifies a browser session with `X-Session-Id`, calls `ChatService.process_message()`, and returns the AI reply in the same request.
- `backend/app/services/chat.py:ChatService.process_message()` owns the existing two-phase AI/tool loop. It loads up to 20 `Conversation` rows, calls the AI, executes insurance MCP tools, persists `user`/`assistant` turns, and updates `Session` state.
- The inbound turn is persisted only after the first AI call succeeds (`process_message()` lines 673-697). This differs from `openspec/specs/chat-sessions/spec.md`, which says the user message is saved before the AI call. New asynchronous ingress must not inherit this data-loss window.
- `backend/app/services/tool_bridge.py:ToolBridge` and the FastMCP tools can be reused unchanged behind an internal-agent responder adapter.

### Persistence

- `backend/app/models/session.py:Session` tracks AI/form state and optionally links to `Customer`; it has no channel identity or tenant.
- `backend/app/models/conversation.py:Conversation` stores only session, role, text, metadata, and timestamp. It lacks direction, provider message ID, channel, delivery state, idempotency key, reply correlation, media, and ownership.
- `backend/app/models/customer.py:Customer` is already the business customer database, but `documento_identidad` and `nombre_completo` are required. A Telegram user or WhatsApp number cannot become a `Customer` without inventing business identity data.
- `backend/app/models/opportunity.py:Opportunity.estado` is free-form and defaults to `pendiente`. It can be related to CRM work but currently represents product opportunities, not chat/contact lifecycle or assignment.
- `backend/app/models/notification.py:Notification` is an outbound campaign record with coarse `wpp`/`email` type, status, retry counters, and optional opportunity. It is not a normalized message ledger.
- `backend/app/main.py:lifespan()` uses `Base.metadata.create_all()`. That creates missing tables but does not add columns to existing SQLite tables. `backend/app/migration_001.py` confirms schema evolution is currently manual and SQLite-specific.
- No tenant or organization key appears in these models. All current data is effectively single-tenant.

### Existing outbound flow

- `backend/app/services/outbound_service.py:OutboundService` selects prospects, generates WhatsApp-oriented text, and writes pending `Notification` rows.
- `backend/app/scheduler.py:OutboundScheduler` runs in-process every 15 minutes and creates notifications. It catches per-prospect errors but is neither a distributed worker nor a durable queue.
- `backend/app/routers/outbound.py` exposes unauthenticated polling and status mutations: `GET /outbound/pending` and `POST /outbound/{id}/{sent|responded|failed}`.
- No WhatsApp bot, Baileys package, Telegram adapter, or webhook implementation exists in this repository. OpenSpec describes a bot poller, but the real tree contains only the backend contract.
- The current retry flow is not sufficient for normalized delivery: there is no provider event ID uniqueness, atomic claim/lease, exponential backoff schedule, dead-letter state, or duplicate-send protection.

### API and security

- There is no user login, operator authorization, API-key dependency, or route-level permission model.
- `backend/app/middleware/security.py:SecurityMiddleware` provides security headers and an in-memory per-IP rate limit only. It trusts `X-Forwarded-For` and is reset on restart.
- `backend/app/main.py:create_app()` allows only `GET`, `POST`, and `OPTIONS`, and CORS allows only `Content-Type`, `X-Session-Id`, and `X-Requested-With`. CRM stage updates and API-key headers require deliberate changes.
- Existing `/outbound` mutations and analytics endpoints are unauthenticated. The former cannot be reused as a public callback API without an authentication boundary.
- Browser-held shared integration secrets would be extractable. A Settings UI needs operator authentication or a separately protected deployment boundary before it can manage credentials safely.

### Frontend, navigation, and dashboard

- `frontend/src/App.tsx` uses local state rather than a router and supports only `chat` and `dashboard` views.
- `frontend/src/components/layout/Header.tsx` is the top-level navigation switcher. There is no Settings view.
- `frontend/src/components/dashboard/DashboardLayout.tsx` provides Pipeline, Trends, Customers, Insurance, and AI tabs. “Multichannel” could be a new top-level operational view; putting channel settings inside dashboard analytics would mix concerns.
- `frontend/src/lib/api.ts:ApiClient` and `frontend/src/lib/analytics.ts` use native `fetch`; this pattern can be retained.
- `backend/app/services/analytics.py:AnalyticsService` uses SQLite-oriented raw SQL and pandas. It can be extended for channel/CRM aggregates, but operational contact lists should use normal paginated queries rather than pandas.
- The Customers dashboard is aggregate-only. There is no customer/contact CRUD API or contact table UI.
- `frontend/package.json` has no frontend test runner. Strict TDD for new UI behavior needs a small Vitest/React Testing Library setup or an explicitly accepted build-only verification gap.

### Tests

- Backend tests use pytest, async in-memory SQLite, FastAPI `TestClient`, and injected/mocked services (`backend/tests/conftest.py`). These patterns are reusable for normalization, auth, routing, CRM, and API tests.
- `backend/tests/test_outbound_router.py` proves the current unauthenticated poll/status contract.
- `backend/tests/test_security.py` covers headers and rate limits, not authentication or authorization.
- `backend/tests/test_chat.py` provides broad service-level coverage for the internal agent and should protect the responder bridge from regressions.
- There are no transport contract tests, webhook signature tests, idempotency tests, worker recovery tests, frontend component tests, or end-to-end tests.

## Affected Areas

- `backend/app/main.py` — initialize normalized messaging services/workers and register channel, CRM, and Settings routers.
- `backend/app/config.py` — add only non-secret operational settings and a credential-encryption master key reference; channel credentials should be persisted as encrypted records rather than multiplied environment fields.
- `backend/app/models/` — add channel configuration, contact identity, chat thread, canonical message, delivery attempt, and API-key records; link rather than overload existing models.
- `backend/app/services/chat.py` — reuse behind an internal-agent adapter; avoid making provider details part of `ChatService`.
- `backend/app/services/outbound_service.py` and `backend/app/routers/outbound.py` — bridge campaign notifications into the canonical outbox and retire or authenticate the polling contract incrementally.
- `backend/app/middleware/security.py` or a new auth dependency — authenticate integration requests from header API keys and authorize operator/API scopes.
- `backend/app/services/analytics.py` — add channel and CRM summary metrics after the operational model is stable.
- `frontend/src/App.tsx` and `frontend/src/components/layout/Header.tsx` — add top-level Multichannel and Settings navigation.
- `frontend/src/components/dashboard/DashboardLayout.tsx` — add CRM/channel KPIs, not credential management.
- `frontend/src/lib/api.ts` — add typed channel, message, contact, CRM, and Settings clients with a centralized request helper.
- `docker-compose.yml` — add a Baileys Node sidecar and persistent encrypted auth-state volume.
- `backend/tests/` — add unit, API, integration, auth, idempotency, and recovery tests.

## Proposed normalized model

| Concept | Minimum purpose |
|---|---|
| `ChannelConnection` | One configured Telegram or WhatsApp/Baileys endpoint; enabled state, route mode, encrypted credentials, external webhook URL, and versioned config. |
| `Contact` | Lightweight CRM person with display name and optional business fields; may link to one existing `Customer`. |
| `ContactChannelIdentity` | Unique `(channel_connection_id, provider_user_id)` identity with normalized address/phone and contact link. |
| `ChatThread` | Stable conversation per channel identity; route mode, owner/handoff state, CRM stage, optional `Session`, and timestamps. |
| `Message` | Canonical inbound/outbound event with provider ID, direction, type, text/payload reference, status, causation/reply IDs, and idempotency key. |
| `DeliveryAttempt` | Attempt number, destination, response/error class, next retry time, and terminal state for webhook/provider delivery. |
| `IntegrationApiKey` | Hashed key, prefix, scopes, enabled/revoked timestamps, and audit metadata; plaintext shown once only. |

Recommended initial CRM stage keys are `lead`, `payment_pending`, `closed_won`, and `closed_lost`. “Closer” should be an assignment/owner role, not a stage. This is a recommendation only; product confirmation is required. Keep API keys stable and localize UI labels independently.

## Target flow

1. Telegram webhook or Baileys sidecar emits a provider event.
2. The backend authenticates the adapter, normalizes the event, inserts it using a provider-event uniqueness constraint, and returns `202` after commit.
3. A durable inbox worker claims the message and resolves the thread's configured route.
4. For `internal_agent`, a responder adapter resolves/creates the linked `Session`, calls `ChatService.process_message()`, and appends the reply to the canonical outbox.
5. For `external_webhook`, a delivery worker sends the normalized event with a delivery ID and HMAC signature. A `2xx` only acknowledges delivery; response bodies are ignored for replies.
6. The external system later calls an authenticated header-key endpoint using the thread/message reference and an idempotency key. The API validates ownership and appends an outbound canonical message.
7. A channel delivery worker sends through Telegram or Baileys and records provider IDs/status without blocking the original inbound request.

For the SQLite MVP, implement the inbox/outbox as database rows with short transactions, explicit claim timestamps, retry scheduling, and stale-claim recovery. Run one worker instance. This preserves asynchronous semantics without introducing a broker. PostgreSQL plus a real queue becomes necessary for multiple backend replicas or materially higher throughput.

## Approaches

1. **Normalized messaging core with adapters (recommended)** — New durable message/thread/contact records; Telegram, Baileys, internal agent, and external webhooks are ports around the core.
   - Pros: Meets delayed reply semantics; provider-neutral; testable; supports idempotency, CRM, handoff, and future Cloud API migration.
   - Cons: More schema and worker design; duplicates some text between canonical `Message` and AI `Conversation`; requires explicit reconciliation rules.
   - Effort: High.

2. **Extend `Session`, `Conversation`, and `Notification` directly** — Add channel/provider/status fields to current tables and branch inside `ChatService`.
   - Pros: Fewer initial files and tables; fastest demo.
   - Cons: Couples domain logic to providers, cannot naturally model external ownership/delayed replies, overloads campaign notifications, complicates deduplication, and forces channel-only contacts into `Customer`.
   - Effort: Medium initially, high maintenance.

3. **External messaging platform/service** — Put channel normalization, queueing, and CRM outside FastAPI; keep this app as the internal-agent API.
   - Pros: Strong isolation and independent scaling.
   - Cons: Largest operational jump, duplicates persistence/business ownership, exceeds the “continue existing stack” intent, and adds network failure modes before product rules are settled.
   - Effort: High; not justified for MVP.

## Baileys versus WhatsApp Cloud API

Baileys is accepted for version one, but the domain must not depend on its payloads or session model.

| Topic | Baileys v1 | Official Cloud API |
|---|---|---|
| Integration | TypeScript WebSocket client using WhatsApp Web multi-device behavior; best isolated in a Node sidecar. | Official HTTPS Graph API for sends and webhooks for inbound/status events. |
| Authentication | QR/pairing plus frequently updated credential state; `creds.update` must be persisted securely. | Meta access token in `Authorization: Bearer` plus WABA/phone configuration. |
| Event model | `messages.upsert`, `connection.update`, and explicit reconnect handling; protocol changes can break the client. | Supported webhook contract, asynchronous status events, managed scaling and published limits. |
| Product constraints | Fast first setup and can use an existing linked account, but it is an unofficial client with session/logout/device and policy risk. | Business onboarding, templates outside the customer-service window, opt-in/policy obligations, and platform pricing. |
| Operations | Sidecar lifecycle, QR UX, encrypted auth volume, reconnect/backoff, single active owner, health, and protocol upgrades are application responsibilities. | Meta manages transport availability; the application manages webhook verification, tokens, templates, rate limits, and policy compliance. |
| Strategic fit | Suitable only as the requested replaceable MVP adapter. | Recommended production target when compliance, supportability, and scale matter. |

Current Baileys documentation confirms WebSocket socket creation, `messages.upsert`, `sendMessage`, `connection.update`, and mandatory persistence on `creds.update`: <https://github.com/WhiskeySockets/Baileys>. Current Meta documentation states that Cloud API uses HTTPS sends, webhooks for inbound/status events, bearer tokens, opt-in/templates, and that unauthorized third-party tools are prohibited: <https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform> (updated June 2, 2026).

Telegram can use the official Bot API directly from FastAPI through existing `httpx`. `setWebhook(secret_token=...)` supplies `X-Telegram-Bot-Api-Secret-Token`; this provider secret is separate from this product's external API keys. Use Telegram `update_id` as an ingress deduplication key.

## Security and operational requirements

- Accept external API keys only from a named header such as `X-API-Key`; never query strings or request bodies. Hash stored keys, compare in constant time, scope them (`messages:reply`, `crm:read`, `crm:write`), support rotation/revocation, and audit use.
- Authenticate channel-adapter ingress separately: Telegram secret-token header, a scoped sidecar key for Baileys, and HMAC-signed outbound webhook deliveries with timestamp/replay limits.
- Encrypt Telegram bot tokens and Baileys auth state at rest. Return only masked metadata from Settings APIs and never log QR contents, tokens, keys, raw auth blobs, or sensitive message payloads.
- Validate external webhook URLs against SSRF: HTTPS, approved hosts or resolved public addresses, redirect restrictions, timeouts, payload limits, and DNS rebinding protections.
- Commit before acknowledging ingress. Deduplicate provider events and external replies with database constraints. Require an `Idempotency-Key` header on reply and CRM mutation APIs.
- Define retry classes, exponential backoff with jitter, maximum attempts, dead-letter visibility, and manual replay. Do not retry permanent `4xx` responses except explicit throttling.
- Preserve per-thread ordering and prevent simultaneous internal/external responders. Route changes need a version or effective boundary so already accepted messages keep deterministic ownership.
- Add retention/deletion rules and redact sensitive contact/message data from logs and analytics.
- SQLite and in-process workers require a single active worker. Multiple replicas need PostgreSQL/queue coordination before scale-out.

## Phased MVP and chained PR slices

Delivery is force-chained. Use a draft/no-merge feature tracker because the end-to-end feature should integrate before main. Every child must stay at or below 400 authored changed lines (`additions + deletions`), include its own tests, state dependencies/out-of-scope work, and target the immediate parent branch so its diff contains only that slice. Estimates must be refined in `sdd-tasks`.

```text
tracker/multicanal
  └─ PR1 Security + migration seam
      └─ PR2 Normalized contact/thread/message model
          └─ PR3 Durable ingress, routing, and external reply API
              └─ PR4 Telegram adapter
                  └─ PR5 Baileys sidecar
                      └─ PR6 CRM/contact API
                          └─ PR7 Multichannel + Settings shell
                              └─ PR8 Inbox/CRM UI + dashboard metrics
```

| Slice | Reviewable outcome | Verification | Budget guard |
|---|---|---|---|
| PR1 | Header API-key dependency, scopes, key hashing/rotation contract, migration mechanism, and auth tests. | Auth allow/deny/scope/rotation tests; migration replay test. | Split migration tooling from auth if forecast exceeds 400. |
| PR2 | `Contact`, channel identity, thread, canonical message, and delivery-attempt persistence with uniqueness constraints. | Model and repository tests for dedupe, links, stage validation, and claims. | No transport or UI. |
| PR3 | `202` durable ingress, route dispatcher, non-blocking external webhook delivery, delayed authenticated reply, idempotency, retry/dead-letter states. | API and worker tests including duplicate, timeout, stale claim, route change, and replay. | Likely two slices: ingress/routing then external callback/reply. |
| PR4 | Telegram webhook verification, normalization, send adapter, and status/error mapping. | Recorded contract fixtures; update dedupe; secret rejection; send retry classification. | Text only; defer media. |
| PR5 | Node 20 Baileys sidecar with QR/connect state, encrypted persistent auth volume, normalized ingress, send endpoint, reconnect and health. | TypeScript unit/contract tests plus backend-side adapter tests. | Split pairing lifecycle from message transport if needed. |
| PR6 | Paginated contact/thread APIs and CRM stage/assignment mutation from API with audit/idempotency. | CRUD, filter, concurrency, authorization, and transition tests. | Keep dashboard aggregates out. |
| PR7 | Top-level Multichannel and Settings navigation, masked channel configuration, route selector, connection status, and minimal frontend test harness. | Vitest component/client tests and strict TypeScript build. | No inbox rendering. |
| PR8 | Inbox/contact CRM UI, stage updates, customer linking, and selected channel/CRM dashboard KPIs. | Component/API tests, analytics tests, and build. | Split dashboard enrichment if above budget. |

Media, multi-tenant administration, human-agent tooling, bulk campaigns through the normalized ledger, Cloud API migration, and production queue/PostgreSQL scale-out should remain explicit follow-ups unless product answers pull them into MVP.

## Highest-value product questions

1. **Operator security and tenant scope:** Is this a single private Colsubsidio deployment, and how must human operators authenticate? Are channel configs, contacts, routes, and API keys global or organization/tenant scoped?
2. **CRM semantics:** Does “closer/closed” mean assignment to a closer, successful closure, or both? Is the required pipeline exactly `lead → pending payment → closed`, and are `closed_won`, `closed_lost`, reopen, history, reason, and responsible owner required?
3. **Routing ownership:** Is routing configured per channel connection only, or can it vary by contact/thread? When a route changes mid-thread, who owns already queued messages and may the internal agent ever respond while an external integration owns the thread?
4. **Delayed reply contract:** What maximum delay is acceptable, can multiple replies target one inbound message, and should replies reference `thread_id`, `inbound_message_id`, or both? What happens after the channel's reply/service window expires?
5. **Handoff behavior:** Is human takeover part of MVP? What triggers it, how is AI paused/resumed, and must queued AI/external replies be cancelled when ownership changes?
6. **Contact identity:** Should unknown channel users create lightweight contacts automatically? Which fields are mandatory, and what deterministic rule links/merges them with the existing document-based `Customer`?
7. **Retries and idempotency:** What retry horizon and dead-letter/manual replay behavior are expected? Will callers reliably provide an `Idempotency-Key`, and for how long must keys be retained?
8. **Business rules:** Are proactive messages in scope for both channels, what consent/opt-out and quiet-hour rules apply, and which route owns responses to existing outbound campaigns?
9. **Media:** Is MVP text-only? If not, which media types, maximum sizes, storage/retention, virus scanning, transcription, and outbound URL lifetime are required?
10. **Dashboard outcome:** Which decisions should the enriched dashboard support first: volume by channel, response time, backlog/failures, conversion by CRM stage, agent-vs-external performance, or contact growth?

## Risks

- Baileys is an unofficial WhatsApp Web client. Account enforcement, protocol drift, logout, and corrupted credential state can interrupt service; official Cloud API should remain the migration target.
- No operator authentication exists. Shipping Settings, contacts, CRM mutation, or integration keys before defining that boundary would expose high-impact controls and personal data.
- Current specs and implementation already drift on message persistence timing; asynchronous guarantees need new authoritative requirements and failure tests.
- Current SQLite `create_all()` and one manual migration script are fragile for the number of new constraints and tables. Idempotent migration/version tracking is a prerequisite.
- In-process scheduling and in-memory rate limiting are single-process mechanisms. Running multiple replicas can duplicate sends and bypass effective limits.
- Existing Customer constraints do not fit anonymous channel contacts; forced reuse would create false identity data.
- Existing outbound endpoints are unauthenticated and documented as internal-by-convention. Exposing them or new reply APIs without scoped keys is unsafe.
- Duplicate persistence between canonical `Message` and AI `Conversation` can diverge unless one write workflow and reconciliation rule are specified.
- Frontend TDD is blocked by the absence of a test runner; adding a minimal harness consumes part of a review slice.
- External webhook routing introduces SSRF, data exfiltration, replay, slow dependency, and retry-storm risks.

## Ready for Proposal

No. The architecture is feasible in the current stack, with a required Node sidecar for Baileys, but the orchestrator should first obtain answers to questions 1-4: operator/tenant security, CRM stage meaning, routing ownership, and delayed reply correlation. Those answers determine the authorization model and canonical schema. Media, handoff, proactive messaging, and dashboard priorities can then be bounded explicitly as MVP or follow-up scope.
