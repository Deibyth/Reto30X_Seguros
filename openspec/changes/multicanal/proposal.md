# Proposal: Multichannel Messaging and Lightweight CRM

## Intent

Give authenticated operators one reliable workspace for Telegram and WhatsApp conversations, contacts, CRM progress, handoff, and configuration. Prevent lost, duplicate, misrouted, or unauthorized replies while preserving the existing stack.

## Scope

### In Scope
- Single-company operator authentication, hashed/scoped API keys, encrypted secrets, and audit-safe Settings.
- Canonical contacts, identities, chats, text messages, deliveries, and stages `lead`, `payment_pending`, and `sale_closed`; closer is a human assignment.
- Durable SQLite inbox/outbox: commit-before-`202`, deduplication, idempotency, retries, dead letters, stale-claim recovery, and one worker.
- Telegram and replaceable WhatsApp/Baileys adapters; Baileys runs in a Node 20 sidecar.
- Multichannel navigation, channel settings, contact/CRM UI and API, human messaging, and incremental metrics.

### Out of Scope
- Media, multi-tenancy, campaign migration, WhatsApp Cloud API, PostgreSQL/broker scale-out, and multiple workers.
- Per-chat external routes or provider identifiers in public reply APIs.

## Capabilities

### New Capabilities
- `operator-access-security`: Operator auth, scoped keys, protected secrets, and auditing.
- `multichannel-messaging`: Canonical chats/messages and durable, ordered, idempotent delivery.
- `agent-routing-handoff`: Agent selection and strict human ownership suppression.
- `channel-adapters`: Telegram and replaceable Baileys transports.
- `contact-crm`: Contacts, customer links, stages, closer assignments, and APIs.
- `multichannel-operations-ui`: Inbox, Settings, CRM, and metrics.

### Modified Capabilities
- `data-models`: Add normalized records and versioned SQLite migrations.
- `outbound-api`: Authenticate and bridge legacy operations incrementally.
- `docker-infrastructure`: Add Baileys and protected persistent state.

## Approach

Use a channel-neutral core around adapters. Agent Configuration is a global/default choice between the internal agent and one external webhook URL. Preserve a future scoped-routing seam without exposing per-chat routing. Human ownership overrides either mode: only the assigned human may send; both automations are suppressed.

External delivery is SSRF-safe, signed, asynchronous, and ignores response bodies. Delayed replies require header API and idempotency keys and only canonical `chat_id`; the backend resolves providers and durably acknowledges enqueueing.

## Affected Areas

| Area | Impact |
|---|---|
| `backend/app/` | Messaging, CRM, auth, routing, workers |
| `frontend/src/` | Operations and Settings UI |
| `docker-compose.yml` | Baileys sidecar |

## Risks

| Risk | Mitigation |
|---|---|
| Baileys instability | Isolate adapter; report health/reconnect state |
| Duplicate sends/ownership races | Constraints, leases, ordering, ownership versions |
| Secret exposure/SSRF | Encryption, scoped auth, strict URL resolution |

## Rollback Plan

Disable connections/workers, revoke keys, stop Baileys, and retain audit rows; existing `/chat` remains available.

## Dependencies and Assumptions

- Assume text-only, one global/default agent configuration, and one worker.
- Add a minimal frontend test harness for strict TDD.

## Delivery

Use a draft/no-merge tracker and force-chained autonomous, tested PRs capped at 400 authored changed lines: security/migrations → model → routing/reply API → Telegram → Baileys → CRM API → Settings → inbox/metrics.

## Success Criteria

- [ ] Duplicate events/replies produce at most one send.
- [ ] Human-owned chats emit no automated replies.
- [ ] Operators securely manage settings, contacts, stages, assignments, chats, and metrics.
- [ ] Both channels recover without losing acknowledged work.
