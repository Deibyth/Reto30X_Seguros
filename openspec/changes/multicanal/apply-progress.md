# Apply Progress: Multicanal

## Completed work units

- [x] S1 — Isolation and guarded migrations
- [x] S2 — Operator security foundation
- [x] S3 — API keys and encrypted vault
- [x] S4 — Canonical ledger
- [x] S5 — Worker, routing, and handoff
- [x] S6a — Canonical reply boundary
- [ ] S6b–S14 — Not started

## S1 evidence

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12.13 in `python:3.12-slim` |
| RED | `docker exec reto30x-s1-py312 python -m pytest -c backend/pyproject.toml backend/tests/test_multicanal_isolation.py -q` → collection failed: `No module named 'app.migrations'` |
| GREEN/refactor | Same focused command → 9 passed; combined isolation + legacy router command → 18 passed, 2 existing deprecation warnings |
| Original immutability | Rejected and successful migration tests compare SHA-256 bytes and ordered `sqlite_master` schema before/after; all assertions passed |
| Compose render | `docker compose -f docker-compose.multicanal.yml --profile multicanal config --quiet` → exit 0 |
| Migration dry run | Compose project `reto30x-s1-evidence` → target `/app/multicanal-data/proteccion360_multicanal.db`, pending `[1]`, applied `[]` |
| Migration runtime | Same isolated project → applied `[1]`; query returned `(1, proteccion360-multicanal-v1)` |
| Existing `/chat` | `backend/tests/test_routers.py` included in combined command; 9 legacy router tests passed |

## TDD cycle evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| S1 | `backend/tests/test_multicanal_isolation.py` | Integration | `test_routers.py`: 9 passed | Missing migration module | 9 passed | rejection matrix, alias, replay, URL, Compose | target policy/checksum seam; 18 passed |

## Work unit evidence

| Evidence | Required value |
|---|---|
| Focused test | Python 3.12 command above; 9 passed in 1.35s |
| Runtime harness | Compose dry-run and real migration commands above; isolated version row verified |
| Rollback boundary | Remove only S1 files/edits and the `proteccion360_multicanal_data` volume; never remove `proteccion360_data` |

## Changed paths and budget

`backend/app/config.py`, `backend/app/main.py`, `backend/app/migrations/`, `backend/multicanal-identity.json`, `backend/tests/test_multicanal_isolation.py`, `docker-compose.multicanal.yml`, `openspec/changes/multicanal/{tasks.md,apply-progress.md}`.

Authored count: 343 additions + deletions (298 implementation/test/config + 2 task checkbox + 43 evidence lines). Limit: 400.

## Process and rollback

No S2+ code, branch, commit, push, PR, review lifecycle, or native-attempt command was executed. Original Compose was read only. Cleanup removed test container `reto30x-s1-py312` and project `reto30x-s1-evidence` network, image, and isolated volume; follow-up inspection returned no such volume/network while `reto30x_seguros_proteccion360_data` still existed. Rollback removes the listed S1 paths/edits and feature-only volume; original `/chat`, Compose, database, and volume remain intact.

## S2 evidence — operator security foundation

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12 in disposable `python:3.12-slim`; native Python 3.12 unavailable |
| RED | `docker run --rm -v "${PWD}:/workspace" -w /workspace/backend python:3.12-slim sh -c "pip install --quiet -r requirements.txt pytest pytest-asyncio httpx argon2-cffi && python -m pytest -c pyproject.toml tests/test_operator_auth.py -q"` → 6 failed: auth routes/security module absent |
| GREEN | Same focused command → 6 passed in 2.04s |
| TRIANGULATE | Same Docker runner with `tests/test_operator_auth.py tests/test_multicanal_isolation.py tests/test_routers.py` → 25 passed, 2 existing deprecation warnings |
| Runtime harness | TestClient login harness proved 200 login, opaque cookie, CSRF denial, logout revocation, idle expiry, permission denial, and audit failure 503; `docker compose -f docker-compose.multicanal.yml --profile multicanal config --quiet` → exit 0 |
| Migration | Isolated migration tests proved pending `[1, 2]`, applied `[1, 2]`, replay `[]`, security tables/triggers, and original database hash/schema unchanged |
| Cleanup | Every test container used `--rm`; no persistent container, network, volume, original database, commit, push, PR, review lifecycle, or native-attempt command was run |

## S2 TDD cycle evidence

| Task | Test file | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| S2 | `backend/tests/test_operator_auth.py` | Integration | S1 isolation + legacy router baseline: 18 passed | Missing auth module/routes; 6 failures | 6 passed | unauthorized, invalid credentials, expiry/revocation, CSRF, permission, audit failure | Session constants, safe audit detail hashing, append-only triggers; 25 combined passed |

## S2 changed paths, budget, and rollback

`backend/app/config.py`, `backend/app/main.py`, `backend/app/migrations/__init__.py`, `backend/app/security.py`, `backend/app/routers/auth.py`, `backend/requirements.txt`, `backend/tests/test_operator_auth.py`, `backend/tests/test_multicanal_isolation.py`, `openspec/changes/multicanal/{tasks.md,apply-progress.md}`.

Authored changed lines: 279 additions + deletions (including tests and this evidence; below the 390 S2 limit). Rollback boundary: revert only these S2 paths/edits and remove only migration version 2/security tables from the isolated multichannel database; never alter `proteccion360.db`, `proteccion360_data`, legacy `/chat`, or S1 path guards.

## S2 status

Only S2 was checked complete. S3 API keys/vault, Settings UI, and all later slices remain pending and were not started.

## S2 bounded correction — review-bc6eee09ff819bc1

- Scope: original-profile security isolation and transactional/replay-safe migration 2 only; no S3 work.
- RED: new isolation and interruption tests failed before the correction (unconditional security init; missing transactional helper).
- GREEN: Python 3.12 focused correction command → 2 passed; combined `tests/test_operator_auth.py tests/test_multicanal_isolation.py tests/test_routers.py -q` → 27 passed, 2 existing datetime deprecation warnings.
- Exact focused command: `docker run --rm ... python -m pytest -c pyproject.toml tests/test_operator_auth.py::test_original_profile_startup_does_not_add_operator_schema tests/test_multicanal_isolation.py::test_interrupted_security_migration_rolls_back_and_replays -q`.
- Changed paths: `backend/app/main.py`, `backend/app/migrations/__init__.py`, `backend/tests/test_operator_auth.py`, `backend/tests/test_multicanal_isolation.py`.
- Delta: 127 authored additions + deletions, within maximum 144.
- Authority: lineage `review-bc6eee09ff819bc1`; target `sha256:bc6eee09ff819bc141c67c49c441d432c49613e091d3e5171013759533696a28`; revision `sha256:9f2115312a7eb22468a984e9f1acbdcd31f72500289aafe97d85b3ce1a993e41`.
- Original database/volume were not opened or changed; disposable `--rm` Python 3.12 containers were cleaned up.
- Process/evidence artifact: `openspec/changes/multicanal/apply-progress.md`; no new residuals; existing datetime deprecation warnings remain.

Correction complete. S3 through S14 remain pending.

## S3 evidence — API keys and vault

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12 in disposable `python:3.12-slim`; no repository secrets added |
| RED | `docker run --rm -v "${PWD}:/workspace" -w /workspace/backend python:3.12-slim sh -c "pip install --quiet -r requirements.txt pytest pytest-asyncio httpx argon2-cffi cryptography && python -m pytest -c pyproject.toml tests/test_keys_vault.py tests/test_multicanal_isolation.py -q"` → collection failed: `app.security.api_keys` absent |
| GREEN/refactor | Same focused command → 15 passed |
| Triangulation | `docker run --rm -v "${PWD}:/workspace" -w /workspace/backend python:3.12-slim sh -c "pip install --quiet -r requirements.txt pytest pytest-asyncio httpx argon2-cffi cryptography && python -m pytest -c pyproject.toml tests/test_keys_vault.py tests/test_operator_auth.py tests/test_multicanal_isolation.py tests/test_routers.py -q"` → 31 passed, 2 existing datetime deprecation warnings |
| Runtime harness | `docker compose -f docker-compose.multicanal.yml --profile multicanal config --quiet` → exit 0; migration replay/isolation tests passed |
| Security evidence | Header-only lookup; scoped HMAC verification uses constant-time comparison; plaintext is returned only by issuance result, never stored/audited; AES-256-GCM ciphertext, nonce, and key version persist; tamper/missing-key reads fail closed |
| Changed paths | `backend/app/security_api_keys.py`, `backend/app/vault.py`, `backend/app/migrations/__init__.py`, `backend/app/config.py`, `backend/requirements.txt`, `backend/tests/test_keys_vault.py`, `backend/tests/test_multicanal_isolation.py`, `openspec/changes/multicanal/{tasks.md,apply-progress.md}` |
| Authored count | 331 additions + deletions including tests and evidence; below the 390 S3 limit |
| Cleanup | All Python runs used `--rm`; no persistent container, volume, network, original database, original Compose, commit, push, PR, review lifecycle, or native-attempt command was used |
| Rollback boundary | Revert only the S3 paths above, remove migration version 3 (`api_keys`/`vault_secrets`) from the isolated multichannel database, and remove `cryptography`; retain S1/S2 guards, security tables, original `/chat`, original database, and original volume |

## S3 status

Only S3 is checked complete. S4–S14 remain pending and untouched. Residual risks: key/vault services are not yet exposed through Settings or channel configuration (deferred to S11); existing S2 datetime deprecation warnings remain.

## S3 authorized review follow-up — ordinal 6

- API-key verification now rolls back after audit-storage failure and returns only bounded HTTP 503 `API key verification unavailable`; audit internals are chained as the exception cause, not exposed in the response.
- Rotation resolves the original public prefix to its UUID `api_keys.id` before storing `rotated_from`; prefix lookup and overlap behavior remain unchanged.
- Strict-TDD RED tests failed for both defects, then focused `tests/test_keys_vault.py` passed 5 tests and combined S3/S2/S1/legacy `/chat` passed 32 tests with 2 existing SQLAlchemy datetime deprecation warnings.
- Changed paths: `backend/app/security_api_keys.py`, `backend/tests/test_keys_vault.py`, `openspec/changes/multicanal/{tasks.md,apply-progress.md}`.
- Authored follow-up count: 53 additions + deletions; cumulative S3 work remains within the authorized 120-line follow-up cap.
- Rollback boundary: revert only this follow-up in the two backend files and these progress entries; S1/S2, later slices, original `/chat`, database, and volumes remain untouched.

## S4 evidence — canonical ledger

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12 in disposable `python:3.12-slim`; no secrets or provider/runtime code added |
| RED | Focused `tests/test_multichannel_models.py` collection failed because `app.models.multichannel` was absent |
| GREEN/refactor | Focused `tests/test_multichannel_models.py tests/test_multicanal_isolation.py` → 16 passed; final combined S4 + S3 keys/vault + S2 auth + S1 isolation + legacy routers → 37 passed, 2 pre-existing SQLAlchemy datetime deprecation warnings |
| Schema/migration | Migration 4 creates connections, contacts, identities, chats, messages, work, idempotency, attempts, event ledger, indexes, retention state, and monotonic version guards; replay applies `[]` and checksum is recorded |
| Constraint evidence | Unique `(connection, provider_user_id)`, `(connection, provider_event_id)`, `(chat, sequence)`, scoped idempotency, and `(message, kind, cycle)` constraints; foreign-parent rejection and redaction non-replay tested |
| Runtime harness | `docker compose -f docker-compose.multicanal.yml --profile multicanal config --quiet` → exit 0; disposable Docker test runs used `--rm` |
| TDD cycle | RED → GREEN → triangulation for duplicate identity/event, conflicting replay, ordering, foreign references, redaction, checksum, and migration replay |
| Changed paths | `backend/app/migrations/__init__.py`, `backend/app/models/{__init__.py,multichannel.py}`, `backend/tests/{test_multichannel_models.py,test_multicanal_isolation.py}`, `openspec/changes/multicanal/{tasks.md,apply-progress.md}` |
| Authored count | 206 additions + deletions including tests and progress; below the 390-line S4 limit |
| Cleanup | All test containers were disposable; no original database/volume, commit, push, PR, review lifecycle, or native-attempt command was used |
| Rollback boundary | Revert only the S4 model/migration/tests/progress paths and remove isolated migration version 4; retain S1-S3 migrations, guards, security tables, original `/chat`, database, and volume |

## S4 TDD cycle evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| S4 | `backend/tests/test_multichannel_models.py` | Integration | S3/S1 baseline: 31 passed | Missing model module | 16 focused passed | duplicate identity/event, ordering, invalid parent, redaction, checksum/replay | savepoint rollback, indexes, monotonic version triggers; 37 combined passed |

## S4 status

S1, S2, S3, S4, and S5 are checked complete. S6–S14 remain pending. Residual risks: transports, APIs, CRM, UI, and retention execution are intentionally deferred to later slices.

## S5 evidence — worker, routing, and handoff

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12 in disposable `python:3.12-slim`; no provider transports or secrets added |
| RED | Focused `tests/test_worker_handoff.py` collection failed because `app.multicanal` was absent |
| GREEN | Focused S5 command → 4 passed |
| TRIANGULATION | Combined S5 + S4 ledger + S3 vault + S2 auth + S1 isolation + legacy routers → 41 passed, 2 existing SQLAlchemy datetime deprecation warnings |
| Migration | Checksummed migration 5 adds isolated lease/fence columns and singleton `worker_leases`; replay returns no applied versions; original profile remains untouched |
| Runtime harness | Disposable Python 3.12 worker state-machine harness exercised ordered claim, lease recovery, stale fencing, singleton rejection, retry/dead-letter, route snapshot, takeover, transfer, and release |
| Changed paths | `backend/app/migrations/__init__.py`, `backend/app/multichannel/{__init__,worker,routing,handoff}.py`, `backend/tests/{test_worker_handoff.py,test_multichannel_models.py,test_multicanal_isolation.py}`, `openspec/changes/multicanal/{tasks,apply-progress}.md` |
| Authored count | 298 additions + deletions, below the 380-line S5 limit |
| Cleanup | All test runs used disposable `--rm` containers; no persistent container, volume, network, original database, commit, push, PR, review lifecycle, or native-attempt command was used |
| Rollback boundary | Revert only S5 modules/tests/progress and migration 5; remove only migration-5 lease/fence columns and `worker_leases` from isolated storage; retain S1-S4, original `/chat`, database, and volume |

## S5 TDD cycle evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| S5 | `backend/tests/test_worker_handoff.py` | Integration/unit | S4 + S3 + S2 + S1 + legacy: 37 passed | Missing worker/routing/handoff package | 4 passed | overtaking, stale/competing workers, recovery, retry/dead, route validation, takeover/transfer/release | fenced claims, bounded backoff, atomic suppression; combined 41 passed |

## S5 status

S1, S2, S3, S4, and S5 are checked complete. S6–S14 remain pending. Residual risks: provider transports, HTTP APIs, CRM, UI, retention execution, and operational bridge remain intentionally deferred.

## S6a evidence — canonical reply boundary

| Evidence | Result |
|---|---|
| Mode | Strict TDD, Python 3.12 in disposable `python:3.12-slim` |
| RED | `tests/test_integrations.py` collection failed: `ModuleNotFoundError: app.integrations.replies` |
| GREEN/refactor | Focused command → 5 passed in 0.64s |
| Combined regression | S6a + S1–S5 + legacy routers → 47 passed, 2 existing datetime warnings |
| Runtime harness | FastAPI `TestClient` against isolated migrated SQLite: POST returns 202, matching replay 200, GET canonical status `queued` |
| Boundary | API-key dependency requires `messages:reply`; body forbids provider IDs; caller scope fences idempotency; human takeover cancels queued work and blocks enqueue |
| Changed paths | `backend/app/{integrations/replies.py,routers/integrations.py,main.py}`, `backend/tests/test_integrations.py`, tasks/progress |
| Rollback | Revert only S6a files/registration/tests and this evidence; retain S1–S5, original `/chat`, database, and volume |
| Cleanup | Every Python 3.12 run used `docker run --rm`; no container, volume, network, original storage, stage, commit, push, PR, or lifecycle command was created |

## S6a TDD cycle evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 6a.1–6a.3 | `backend/tests/test_integrations.py` | Integration | S1–S5: 15 passed | missing replies module | 5 passed | replay/conflict/caller scope, takeover, body rejection, HTTP 202/200/status, profile gate | compact canonical boundary; 47 combined passed |

## S6a status

Only S6a is complete. S6b webhook transport/dispatcher and all later slices remain explicitly out of scope.

## S6a boundary-coverage follow-up

| Evidence | Result |
|---|---|
| RED | New three-case command → 2 passed, 1 failed: same-transaction takeover rolled back with the rejected request rather than representing a committed concurrent ownership change. |
| GREEN | Same command after the deterministic second-connection racer → 3 passed; focused `test_integrations.py` → 8 passed. |
| Combined regression | S1–S6a focused backend suite → 50 passed, 2 existing SQLAlchemy datetime warnings. |
| Runtime harness | FastAPI `TestClient` with isolated migrated SQLite proved 401 missing key and 403 insufficient `crm:read` key before message/work creation; unknown-chat 404 without provider disclosure or records; cross-caller status 404; committed ownership race 403 with no records. |
| Cleanup | All Python 3.12 Docker runs used `--rm`; no persistent container, volume, network, stage, commit, push, PR, lifecycle, webhook, worker, transport, or provider work was created. |
| Rollback boundary | Revert only the three coverage cases and this evidence entry; existing S6a reply code and S1–S5 stay unchanged. |

### S6a follow-up TDD cycle evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| Boundary coverage | `backend/tests/test_integrations.py` | Integration | 5 passed | committed-race harness failure | 8 focused passed | missing/insufficient auth, unknown/cross-caller, ownership fence | concurrent SQLite racer; 50 combined passed |
