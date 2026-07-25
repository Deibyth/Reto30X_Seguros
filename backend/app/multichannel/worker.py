"""Fenced, ordered SQLite work processing for the single-worker MVP."""

from dataclasses import dataclass
import secrets
import uuid
from sqlite3 import Connection

MAX_ATTEMPTS = 8
LEASE_SECONDS = 60


class WorkerBusy(RuntimeError):
    pass


class StaleClaim(RuntimeError):
    pass


@dataclass(frozen=True)
class Claim:
    work_id: str
    token: str
    attempt: int


@dataclass(frozen=True)
class Completion:
    status: str


class WorkerCoordinator:
    def __init__(self, db: Connection, owner: str):
        self.db, self.owner = db, owner
        self.token = secrets.token_urlsafe(18)

    def acquire(self, now: int) -> str:
        row = self.db.execute("SELECT owner, expires_at FROM worker_leases LIMIT 1").fetchone()
        if row and row[0] != self.owner and row[1] > now:
            raise WorkerBusy("another worker owns processing")
        self.db.execute("DELETE FROM worker_leases WHERE expires_at <= ?", (now,))
        self.db.execute("INSERT OR REPLACE INTO worker_leases VALUES (?,?,?)", (self.owner, self.token, now + LEASE_SECONDS))
        return self.token


def _worker_is_live(db: Connection, worker: str, now: int) -> bool:
    row = db.execute("SELECT owner, expires_at FROM worker_leases LIMIT 1").fetchone()
    return bool(row and row[0] == worker and row[1] > now)


def claim_next(db: Connection, worker: str, now: int) -> Claim | None:
    if not _worker_is_live(db, worker, now):
        return None
    row = db.execute(
        "SELECT w.id, w.attempt_count FROM work_items w JOIN messages m ON m.id=w.message_id "
        "WHERE w.status IN ('ready','retry_wait') AND w.available_at <= ? AND m.redacted=0 "
        "AND NOT EXISTS (SELECT 1 FROM messages earlier JOIN work_items ew ON ew.message_id=earlier.id "
        "WHERE earlier.chat_id=m.chat_id AND earlier.sequence<m.sequence "
        "AND ew.status NOT IN ('succeeded','dead','cancelled')) ORDER BY m.accepted_at, m.sequence LIMIT 1", (now,)
    ).fetchone()
    if not row:
        return None
    token = str(uuid.uuid4())
    attempt = row[1] + 1
    updated = db.execute(
        "UPDATE work_items SET status='claimed', lease_owner=?, lease_token=?, lease_expires_at=?, "
        "attempt_count=? WHERE id=? AND status IN ('ready','retry_wait')", (worker, token, now + LEASE_SECONDS, attempt, row[0])
    ).rowcount
    if not updated:
        return None
    db.execute("INSERT INTO delivery_attempts(id, work_id, attempt, status) VALUES(?,?,?,'started')", (str(uuid.uuid4()), row[0], attempt))
    return Claim(row[0], token, attempt)


def recover_expired(db: Connection, now: int) -> int:
    return db.execute(
        "UPDATE work_items SET status='ready', lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL "
        "WHERE status='claimed' AND lease_expires_at <= ?", (now,)
    ).rowcount


def complete(db: Connection, claim: Claim, *, success: bool, now: int, retryable: bool = False) -> Completion:
    row = db.execute("SELECT lease_expires_at, attempt_count FROM work_items WHERE id=? AND lease_token=? AND status='claimed'", (claim.work_id, claim.token)).fetchone()
    if not row or row[0] <= now:
        raise StaleClaim("claim no longer owns the work item")
    if success:
        status = "succeeded"
    elif retryable and claim.attempt < MAX_ATTEMPTS:
        status = "retry_wait"
    else:
        status = "dead"
    delay = min(900, 5 * (2 ** max(claim.attempt - 1, 0))) if status == "retry_wait" else 0
    db.execute("UPDATE work_items SET status=?, available_at=?, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL WHERE id=? AND lease_token=?", (status, now + delay, claim.work_id, claim.token))
    db.execute("UPDATE delivery_attempts SET status=? WHERE work_id=? AND attempt=?", ("succeeded" if success else status, claim.work_id, claim.attempt))
    return Completion(status)
