# Apply Progress: Multicanal

## Completed work units

- [x] S1 — Isolation and guarded migrations
- [ ] S2–S14 — Not started

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
