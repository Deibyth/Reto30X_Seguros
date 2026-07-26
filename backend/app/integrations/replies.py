"""Canonical, caller-scoped external reply enqueueing."""

import hashlib
import sqlite3
import uuid


class ReplyDenied(ValueError):
    """A reply cannot cross the canonical ownership boundary."""


def _chat(db: sqlite3.Connection, chat_id: str):
    return db.execute("""SELECT c.owner_version, c.owner_id, i.connection_id FROM chats c
        JOIN channel_identities i ON i.id=c.identity_id WHERE c.id=? AND c.redacted=0""", (chat_id,)).fetchone()


def enqueue_reply(db: sqlite3.Connection, caller: str, chat_id: str, text: str, key: str) -> dict[str, object]:
    """Commit one provider-neutral reply, fencing ownership immediately before insert."""
    request_hash, scope = hashlib.sha256(f"{chat_id}\0{text}".encode()).hexdigest(), f"reply:{caller}"
    existing = db.execute("SELECT request_hash,message_id FROM idempotency_records WHERE scope=? AND key=?", (scope, key)).fetchone()
    if existing:
        if existing[0] != request_hash:
            raise ValueError("idempotency key conflicts with the original request")
        status = db.execute("SELECT status FROM messages WHERE id=?", (existing[1],)).fetchone()
        if not status:
            raise ReplyDenied("reply is unavailable")
        return {"id": existing[1], "status": status[0], "replay": True}
    chat = _chat(db, chat_id)
    if not chat:
        raise LookupError("chat not found")
    if chat[1] is not None:
        raise ReplyDenied("chat is human-owned")
    message_id = str(uuid.uuid4())
    sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM messages WHERE chat_id=?", (chat_id,)).fetchone()[0]
    inserted = db.execute("""INSERT INTO messages(id,chat_id,connection_id,provider_event_id,direction,text_type,content,status,sequence)
        SELECT ?,?,?,?,'outbound','text',?,'queued',? WHERE EXISTS
        (SELECT 1 FROM chats WHERE id=? AND owner_id IS NULL AND owner_version=?)""",
        (message_id, chat_id, chat[2], f"reply:{message_id}", text, sequence, chat_id, chat[0])).rowcount
    if inserted != 1:
        raise ReplyDenied("ownership changed before enqueue")
    db.execute("INSERT INTO work_items(id,message_id,kind,cycle,status,owner_version) VALUES (?,?,'outbound',1,'ready',?)", (str(uuid.uuid4()), message_id, chat[0]))
    db.execute("INSERT INTO idempotency_records(scope,key,request_hash,message_id) VALUES (?,?,?,?)", (scope, key, request_hash, message_id))
    return {"id": message_id, "status": "queued", "replay": False}


def reply_status(db: sqlite3.Connection, caller: str, message_id: str) -> dict[str, str]:
    row = db.execute("""SELECT m.id,m.status FROM idempotency_records r JOIN messages m ON m.id=r.message_id
        WHERE r.scope=? AND m.id=?""", (f"reply:{caller}", message_id)).fetchone()
    if not row:
        raise LookupError("reply not found")
    return {"id": row[0], "status": row[1]}
