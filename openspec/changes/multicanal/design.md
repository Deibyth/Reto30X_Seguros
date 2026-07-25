# Design: Multichannel Messaging and Lightweight CRM

## Technical approach

On `feature/multicanal`, extend the existing FastAPI tree; preserve `/chat` and do not clone the backend. Provider-neutral application ports have SQLAlchemy, Telegram, Baileys HTTP, webhook, vault, and `InternalAgentResponder` adapters. The latter calls existing `ChatService.process_message()` through linked `Session`; providers never enter `ChatService`.

```text
Telegram/Baileys -> ingress -> SQLite inbox -> router -> ChatService wrapper | signed webhook
operator/external API -----------------------> outbox -> channel adapter
                                      ownership/config snapshots guard both paths
```

## Decisions and defaults

| Decision | Choice and rationale | Rejected/tradeoff |
|---|---|---|
| Isolation | `main` stays untouched/runnable; code/artifacts stay on `feature/multicanal` until explicit merge; runtime database/volume are separate. | Branch isolation cannot isolate shared data. |
| Auth | Argon2id `Operator`; opaque Secure/HttpOnly/Strict cookie (8h idle/24h absolute), CSRF, CLI bootstrap. | Revocable now; OIDC later, not JWT. |
| Keys/secrets | `mc_live_<8-id>_<43-base64url>`; indexed ID + constant-time peppered HMAC-SHA-256; scopes/audit/revocation/24h overlap. AES-256-GCM under mounted key; redact. | No browser/shared/reversible keys. |
| Queue | One worker; 60s lease/20s heartbeat; 8 attempts; full-jitter `5s*2^n`, 15m cap, bounded `Retry-After`, then dead letter. | Scale needs PostgreSQL/broker; crash-window is at-least-once. |
| Retention | Idempotency 30d; delayed reply 24h; content 180d; attempts/dead letters 90d; audit 365d; migration evidence permanent; configurable. | Privacy-first. |

## Concrete SQLite model

UUID `VARCHAR(36)`, UTC, FKs on. Tables: operators/sessions; keys/scopes; encrypted configurations; contacts optionally linked to existing `customers`; identities UQ `(connection,provider_user)`; chats optionally linked to existing `sessions`, with checked stage, closer/owner, ownership/config versions, sequence; messages UQ `(chat,sequence)`/`(connection,provider_event)`; work UQ `(message,kind,cycle)` with snapshots/claims; attempts UQ `(work,attempt)`; idempotency UQ `(actor,key)`; stage/closer histories, append-only audit, singleton worker lease, notification bridge. Index claims, ordering, stage, contacts, audit, retention. Message states `accepted|queued|sending|sent|retrying|failed|cancelled|unsupported|redacted`; work `ready|claimed|retry_wait|succeeded|dead|cancelled`.

## Consistency and workers

Ingress stores identity/contact/chat/message/work and route/config/ownership snapshots atomically before `202`; duplicates return original. Short `BEGIN IMMEDIATE` claims block overtaking, require matching tokens, and recover expiry; network I/O is outside transactions.

Takeover increments ownership and cancels unsent automation atomically. Generation and fenced delivery recheck ownership. Transfer is atomic; release never revives suppression. Sends are idempotent; replay requires no success and audit.

## HTTP contracts

Errors: `401` unauthenticated, `403` forbidden, `404` hidden/missing, `409` conflict, `422` invalid, `429` throttled, `503` unavailable.

| Surface | Contract |
|---|---|
| Operator | `POST /api/auth/login` 200+cookie; `POST /logout` 204; `GET /me` 200. |
| Settings/connections | `GET/PUT /api/settings` (`If-Match`); `GET/POST/PATCH /api/connections[/{id}]`; explicit secret delete; validate/pair; masked reads, atomic replacement. |
| Inbox/CRM | List chats/history/contacts; mutate contact/customer/stage/closer/owner; cursor pages, canonical IDs, `If-Match`, `Idempotency-Key`. |
| Sends | Human `POST /api/chats/{chat_id}/messages`; external `POST /api/integrations/replies` body exactly `{chat_id,text}`; 202 status URL, 200 replay, owner-only, no provider IDs. |
| Channels | Telegram webhook verifies secret; Baileys ingress requires `channel:ingress`; new/duplicate 202, bad secret 401, unsupported 415. Work status/replay endpoints; legacy `/outbound/*` semantics with `legacy:outbound`. |

Webhook signs canonical IDs/timestamp/delivery with HMAC-SHA256; replay window 5m. Require HTTPS/443+allowlist; re-resolve, reject non-global/metadata IPs, pin IP with TLS/SNI, forbid redirects, time out 2s connect/10s total, ignore bodies. Any 2xx succeeds; 408/425/429/5xx/network retry; other 4xx permanent.

## Adapters, UI, tests, and operations

Telegram maps `update_id`/`sendMessage`. Node 20 Baileys uses socket message/connection/credential events and send; QR is transient, logout/corruption pause reconnect, health is explicit, and a volume lock enforces one owner. Normalized authenticated HTTP keeps replaceability.

Extend `App`/`Header` with protected Multichannel/Settings. TanStack containers feed typed presentational Settings, Inbox/Composer, CRM and metric panels. Add Vitest+jsdom+RTL; strict TDD covers migrations, auth, ordering/handoff, SSRF/signatures, adapters/APIs, UI secrets/conflicts/partial metrics.

## Isolation, migration, and rollback

Original: current Compose, `/app/data/proteccion360.db`, `proteccion360_data`. Feature-only `docker-compose.multicanal.yml` profile: `APP_PROFILE=multicanal`, `/app/multicanal-data/proteccion360_multicanal.db`, `proteccion360_multicanal_data`; sidecar has a separate auth volume.

Dedicated `python -m app.migrations migrate --profile multicanal --database-url ...` has no implicit target. Before opening SQLite it resolves symlinks; requires exact root/basename, sentinel `proteccion360-multicanal-v1`, and database identity; rejects original path/volume or wrong profile without writing. Startup runs this guard and checksummed migrations before multichannel readiness; failure blocks it, not `/chat`. `create_all` is test-only.

Before migration, stop multichannel workers/sidecar, checkpoint and back up its database/auth volumes; rollback restores only identity-matching backups. Original needs no migration/restore. RED tests hash original bytes/schema before/after isolated migration; wrong-path, symlink, original-volume and missing-sentinel cases fail before access. Compose tests assert distinct storage. Metrics expose profile/version/queue/health safely.

## Delivery, files, traceability

Tested ≤400-line chain: isolation/migrations → auth/models → worker/handoff → webhook/reply → Telegram → Baileys/Compose → CRM API → Settings → inbox/metrics; split oversize slices and target immediate parent. Seams: backend modules, `frontend/src/features/`, sidecar, multichannel Compose.

Traceability: security→sessions/keys/vault/audit; messaging→ledger/order/queue; routing→snapshots/fence; adapters→ports; CRM→contacts/history/APIs; UI→protected containers; `data-models`→constraints/guarded migrations; outbound→legacy/replies/webhooks; `docker-infrastructure`→profiles/isolated volumes/sidecar. Assumption: only an explicit maintainer merge may move feature code toward `main`.

## Threat matrix and remaining risks

Baileys HTTP executes no user commands. Documentation paths, Git selection, commit/push state, and PR commands are **N/A**: no classification/VCS automation. Risks: Baileys drift, SQLite limits, crash-window duplicates, DNS pinning, local passwords; later use Cloud API, PostgreSQL/broker, OIDC.
