import hashlib
import json
import sqlite3

import pytest

from app.migrations import MIGRATIONS, migrate
from app.models.multichannel import LedgerConflict, insert_message, redact_message


def identity(root):
    root.joinpath(".multicanal-identity.json").write_text(
        json.dumps({"sentinel": "proteccion360-multicanal-v1", "deployment_id": "test"}),
        encoding="utf-8",
    )


@pytest.fixture
def database(tmp_path):
    identity(tmp_path)
    target = tmp_path / "proteccion360_multicanal.db"
    migrate("multicanal", target, tmp_path, "test")
    return target


def test_migration_four_is_canonical_and_replay_safe(database):
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT version FROM multicanal_schema_migrations ORDER BY version").fetchall() == [(1,), (2,), (3,), (4,), (5,)]
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"contacts", "channel_identities", "chats", "messages", "work_items", "idempotency_records", "delivery_attempts", "event_ledger"} <= names
    assert migrate("multicanal", database, database.parent, "test")["applied"] == []


def test_identity_and_event_uniqueness_reuses_existing_message(database):
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("INSERT INTO channel_connections VALUES ('conn', 'telegram', 'ready')")
        db.execute("INSERT INTO contacts(id, display_name) VALUES ('contact', 'Ada')")
        db.execute("INSERT INTO channel_identities VALUES ('identity', 'conn', 'contact', 'user-1', NULL)")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO channel_identities VALUES ('identity-2', 'conn', 'contact', 'user-1', NULL)")
        db.execute("INSERT INTO chats(id, identity_id) VALUES ('chat', 'identity')")
        first = insert_message(db, "chat", "conn", "event-1", "hello", "scope", "key-1")
        assert insert_message(db, "chat", "conn", "event-1", "hello", "scope", "key-1") == first
        with pytest.raises(LedgerConflict):
            insert_message(db, "chat", "conn", "event-1", "changed", "scope", "key-1")
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM work_items").fetchone()[0] == 1


def test_ordering_replay_conflict_and_redaction_are_safe(database):
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO channel_connections VALUES ('conn', 'whatsapp', 'ready')")
        db.execute("INSERT INTO contacts(id, display_name) VALUES ('contact', 'Bob')")
        db.execute("INSERT INTO channel_identities VALUES ('identity', 'conn', 'contact', 'user-2', NULL)")
        db.execute("INSERT INTO chats(id, identity_id) VALUES ('chat', 'identity')")
        first = insert_message(db, "chat", "conn", "event-1", "one", "scope", "key-1")
        second = insert_message(db, "chat", "conn", "event-2", "two", "scope", "key-2")
        assert first["sequence"] < second["sequence"]
        redact_message(db, first["id"])
        row = db.execute("SELECT content, status, redacted FROM messages WHERE id=?", (first["id"],)).fetchone()
        assert row == (None, "redacted", 1)
        with pytest.raises(LedgerConflict):
            insert_message(db, "chat", "conn", "event-3", "three", "scope", "key-1")


def test_invalid_parent_cannot_create_partial_ledger_rows(database):
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO messages(id, chat_id, connection_id, provider_event_id, direction, text_type, content, status, sequence) VALUES ('x', 'missing', 'missing', 'event', 'inbound', 'text', 'x', 'accepted', 1)")
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


def test_migration_checksum_is_recorded(database):
    with sqlite3.connect(database) as db:
        checksum = db.execute("SELECT checksum FROM multicanal_schema_migrations WHERE version=4").fetchone()[0]
    assert checksum == hashlib.sha256(MIGRATIONS[4].encode()).hexdigest()
