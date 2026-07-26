# Tasks: Multichannel Messaging and Lightweight CRM

## Review Workload Forecast

| Field | Value |
|---|---|
| Total estimate | 4,840 changed lines across the full change |
| S6a forecast | 280 measured workspace lines + up to 96 lines for three boundary-coverage tests (API-key denial, unknown-chat confidentiality/no enqueue, and ownership-change race) = explicit upper bound of 376 changed lines; independently below the 400-line review budget. Rationale: the remaining work is test-only coverage of the existing reply boundary, with no new production scope. |
| S6b forecast | 340 changed lines; independently bounded below 400 |
| Delivery / chain | force-chained / feature-branch-chain |
| Suggested split | Tracker → S6a → S6b; each child targets its immediate predecessor |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| S6a | Canonical reply enqueue and status API | PR S6a; base: S5 | `python -m pytest -c backend/pyproject.toml backend/tests/test_integrations.py -q` | FastAPI reply/status requests against isolated SQLite | `replies.py`, reply routes, registration, and reply tests |
| S6b | External-webhook delivery dispatcher | PR S6b; base: S6a | `python -m pytest -c backend/pyproject.toml backend/tests/test_integrations.py -q` | Fake DNS/transport proves no prohibited connection | `webhook.py`, worker dispatch integration, and webhook tests |

## Work-unit Contract

Each slice is RED → GREEN → REFACTOR in one session, includes tests and evidence, and stops before 400 authored changed lines. Keep `main`, original Compose, database, and volume untouched. S6b depends on S6a's canonical message/status contract; S6a contains no external HTTP delivery, and S6b adds no reply API semantics.

## Dependency-ordered Slices

- [x] **S1 Isolation and guarded migrations (360).** Feature-only profile, storage guard, migrations, and isolation tests. Base: tracker.
- [x] **S2 Operator security foundation (390).** Sessions, permissions, audit, and authorization tests. Base: S1.
- [x] **S3 Keys and vault (390).** Scoped keys, encrypted secrets, rotation, and denial tests. Base: S2.
- [x] **S4 Canonical ledger (390).** Canonical records, constraints, migrations, and concurrency tests. Base: S3.
- [x] **S5 Worker, routing, handoff (380).** Leases, retries/dead letters, routing snapshots, ownership fencing, and race tests. Base: S4.

### Phase 1: S6a — Canonical Reply Boundary (upper bound: 376)

- [x] **6a.1 RED:** In `backend/tests/test_integrations.py`, prove scoped `messages:reply` authorization, canonical-only body, unknown/provider-ID rejection, same-key replay, conflicting reuse, human-owner rejection, and takeover-before-enqueue cancellation.
- [x] **6a.2 GREEN:** Add `backend/app/integrations/replies.py` and `backend/app/routers/integrations.py`: durable caller-scoped idempotent enqueue plus `POST /api/integrations/replies` (`202` first enqueue, `200` replay) and canonical reply-status resource; register only in the multicanal profile.
- [x] **6a.3 REFACTOR:** Keep provider IDs and outbound transport outside the API; record focused test/runtime results and rollback evidence. Base: S5; trace: outbound API, messaging, handoff.

### Phase 2: S6b — Signed External Webhook Delivery (340)

- [ ] **6b.1 RED:** Extend `backend/tests/test_integrations.py` for canonical HMAC payload/replay window, ignored `2xx` body, HTTPS/allowlist/public-DNS/port/size/redirect/rebind rejection, bounded transport, retryable/permanent classification, dead-letter retry integration, and ownership change immediately before send.
- [ ] **6b.2 GREEN:** Add `backend/app/integrations/webhook.py` and worker-owned `external_webhook` dispatch wiring. Deliver claimed work asynchronously with stable delivery ID/timestamp, pinned TLS/SNI destination, 2s connect/10s total/16KiB bounds, no redirects, `retry_wait`/dead-letter outcomes, and pre-send ownership/version fencing.
- [ ] **6b.3 REFACTOR:** Keep response bodies non-authoritative and external delivery out of ingress/reply routes; record fake-network/runtime and rollback evidence. Base: S6a; trace: outbound API, messaging retry/dead letter, handoff.

- [ ] **S7 Telegram adapter (250).** Authenticated text ingress/send/health and provider-stub tests. Base: S6b.
- [ ] **S8 Baileys sidecar foundation (350).** Authenticated Node sidecar, protected state, health, and Compose tests. Base: S7.
- [ ] **S9 CRM API (390).** Cursor reads and idempotent contact/customer/stage/closer/owner mutations. Base: S8.
- [ ] **S10 Frontend test/auth foundation (260).** Vitest harness and protected navigation. Base: S9.
- [ ] **S11 Settings (340).** Versioned configuration and secret-safe Settings UI/API. Base: S10.
- [ ] **S12 Inbox and human reply UI (390).** Ordered inbox, owner composer, and lifecycle state. Base: S11.
- [ ] **S13 CRM UI (320).** Contact/stage/closer editing with conflict retry. Base: S12.
- [ ] **S14 Metrics, legacy bridge, operations (250).** Safe metrics, legacy bridge, retention, and runbook. Base: S13.

## First Apply

Start S6a only. S6b may start only after S6a is independently verified and becomes its immediate chain parent.
