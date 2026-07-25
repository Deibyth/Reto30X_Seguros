"""Canonical, provider-neutral ledger helpers for the isolated database."""

import hashlib
import uuid
from sqlite3 import Connection, IntegrityError


class LedgerConflict(ValueError):
    """The request reuses an identity or idempotency key incompatibly."""


def insert_message(
    db: Connection, chat_id: str, connection_id: str, event_id: str,
    content: str, scope: str, idempotency_key: str,
) -> dict[str, object]:
    """Insert one accepted event, returning the original row for safe replay."""
    request_hash = hashlib.sha256(f"{chat_id}\0{content}".encode()).hexdigest()
    existing = db.execute(
        "SELECT message_id, request_hash FROM idempotency_records WHERE scope=? AND key=?",
        (scope, idempotency_key),
    ).fetchone()
    if existing:
        if existing[1] != request_hash:
            raise LedgerConflict("idempotency key conflicts with the original request")
        row = db.execute("SELECT id, sequence, status FROM messages WHERE id=?", (existing[0],)).fetchone()
        if row[2] == "redacted":
            raise LedgerConflict("redacted messages cannot be replayed")
        return {"id": row[0], "sequence": row[1], "status": row[2]}
    event = db.execute(
        "SELECT id, chat_id, content, sequence, status FROM messages "
        "WHERE connection_id=? AND provider_event_id=?", (connection_id, event_id),
    ).fetchone()
    if event:
        if event[4] == "redacted":
            raise LedgerConflict("redacted messages cannot be replayed")
        if event[1:] != (chat_id, content, event[3], event[4]):
            raise LedgerConflict("provider event conflicts with the original message")
        return {"id": event[0], "sequence": event[3], "status": event[4]}
    sequence = db.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE chat_id=?", (chat_id,)).fetchone()[0]
    message_id = str(uuid.uuid4())
    db.execute("SAVEPOINT ledger_insert")
    try:
        db.execute(
            "INSERT INTO messages(id, chat_id, connection_id, provider_event_id, direction, text_type, content, status, sequence) "
            "VALUES (?, ?, ?, ?, 'inbound', 'text', ?, 'accepted', ?)",
            (message_id, chat_id, connection_id, event_id, content, sequence),
        )
        db.execute("INSERT INTO work_items(id, message_id, kind, cycle, status) VALUES (?, ?, 'inbound', 1, 'ready')", (str(uuid.uuid4()), message_id))
        db.execute(
            "INSERT INTO idempotency_records(scope, key, request_hash, message_id) VALUES (?, ?, ?, ?)",
            (scope, idempotency_key, request_hash, message_id),
        )
        db.execute("RELEASE ledger_insert")
    except IntegrityError as error:
        db.execute("ROLLBACK TO ledger_insert")
        db.execute("RELEASE ledger_insert")
        raise LedgerConflict("concurrent ledger request conflicted") from error
    return {"id": message_id, "sequence": sequence, "status": "accepted"}


def redact_message(db: Connection, message_id: str) -> None:
    """Irreversibly remove content and make the message non-deliverable."""
    db.execute("UPDATE messages SET content=NULL, status='redacted', redacted=1 WHERE id=?", (message_id,))
