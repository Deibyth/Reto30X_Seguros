"""Atomic ownership transitions and suppression of unsent automation."""

from dataclasses import dataclass
from sqlite3 import Connection


class OwnershipConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class Ownership:
    owner_id: str | None
    owner_version: int


def _set_owner(db: Connection, chat_id: str, expected: int, owner: str | None, current: str | None = None) -> Ownership:
    version = expected + 1
    query = "UPDATE chats SET owner_id=?, owner_version=? WHERE id=? AND owner_version=?"
    params: tuple[str | int | None, ...] = (owner, version, chat_id, expected)
    if current is not None:
        query += " AND owner_id=?"
        params += (current,)
    if db.execute(query, params).rowcount != 1:
        raise OwnershipConflict("ownership transition is stale")
    if owner is not None:
        db.execute("UPDATE work_items SET status='cancelled' WHERE message_id IN (SELECT id FROM messages WHERE chat_id=?) AND status IN ('ready','retry_wait','claimed')", (chat_id,))
    return Ownership(owner, version)


def take_over(db: Connection, chat_id: str, owner_id: str) -> Ownership:
    row = db.execute("SELECT owner_version FROM chats WHERE id=?", (chat_id,)).fetchone()
    return _set_owner(db, chat_id, row[0], owner_id)


def transfer_ownership(db: Connection, chat_id: str, current: str, new: str, *, expected_version: int) -> Ownership:
    return _set_owner(db, chat_id, expected_version, new, current)


def release_ownership(db: Connection, chat_id: str, owner_id: str, *, expected_version: int) -> Ownership:
    return _set_owner(db, chat_id, expected_version, None, owner_id)
