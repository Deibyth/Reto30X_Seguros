"""Fail-closed, versioned migrations for isolated multichannel storage."""

import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

SENTINEL = "proteccion360-multicanal-v1"
DATABASE_NAME = "proteccion360_multicanal.db"
SENTINEL_NAME = ".multicanal-identity.json"
MIGRATION_SQL = """CREATE TABLE multicanal_schema_migrations (
version INTEGER PRIMARY KEY, checksum TEXT NOT NULL,
deployment_id TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""
MIGRATIONS = {1: MIGRATION_SQL}
SECURITY_SQL = """CREATE TABLE operators (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 permissions TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE operator_sessions (
 id TEXT PRIMARY KEY, operator_id TEXT NOT NULL REFERENCES operators(id),
 csrf_token TEXT NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL,
 expires_at INTEGER NOT NULL, revoked_at INTEGER);
CREATE TABLE audit_events (
 id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL, target TEXT NOT NULL,
 outcome TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL);
CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END"""
MIGRATIONS[2] = SECURITY_SQL
VAULT_KEYS_SQL = """CREATE TABLE api_keys (
 id TEXT PRIMARY KEY, prefix TEXT NOT NULL UNIQUE, key_hash TEXT NOT NULL,
 name TEXT NOT NULL, scopes TEXT NOT NULL, created_at INTEGER NOT NULL,
 expires_at INTEGER, revoked_at INTEGER, overlap_until INTEGER,
 rotated_from TEXT REFERENCES api_keys(id));
CREATE INDEX api_keys_prefix_idx ON api_keys(prefix);
CREATE TABLE vault_secrets (
 name TEXT PRIMARY KEY, ciphertext BLOB NOT NULL, nonce BLOB NOT NULL,
 key_version INTEGER NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)"""
MIGRATIONS[3] = VAULT_KEYS_SQL
LEDGER_SQL = """CREATE TABLE channel_connections (
 id TEXT PRIMARY KEY, channel TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready');
CREATE TABLE contacts (
 id TEXT PRIMARY KEY, customer_id TEXT, display_name TEXT, created_at INTEGER NOT NULL DEFAULT (unixepoch()), redacted INTEGER NOT NULL DEFAULT 0 CHECK(redacted IN (0,1)));
CREATE TABLE channel_identities (
 id TEXT PRIMARY KEY, connection_id TEXT NOT NULL REFERENCES channel_connections(id), contact_id TEXT NOT NULL REFERENCES contacts(id), provider_user_id TEXT NOT NULL, address TEXT, UNIQUE(connection_id, provider_user_id));
CREATE TABLE chats (
 id TEXT PRIMARY KEY, identity_id TEXT NOT NULL REFERENCES channel_identities(id), stage TEXT NOT NULL DEFAULT 'lead' CHECK(stage IN ('lead','payment_pending','sale_closed')), sequence INTEGER NOT NULL DEFAULT 0, owner_version INTEGER NOT NULL DEFAULT 0, config_version INTEGER NOT NULL DEFAULT 0, retention_until INTEGER, redacted INTEGER NOT NULL DEFAULT 0 CHECK(redacted IN (0,1)));
CREATE TABLE messages (
 id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id), connection_id TEXT NOT NULL REFERENCES channel_connections(id), provider_event_id TEXT NOT NULL, direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')), text_type TEXT NOT NULL CHECK(text_type='text'), content TEXT, status TEXT NOT NULL CHECK(status IN ('accepted','queued','sending','sent','retrying','failed','cancelled','unsupported','redacted')), sequence INTEGER NOT NULL, correlation_id TEXT, accepted_at INTEGER NOT NULL DEFAULT (unixepoch()), redacted INTEGER NOT NULL DEFAULT 0 CHECK(redacted IN (0,1)), UNIQUE(connection_id, provider_event_id), UNIQUE(chat_id, sequence));
CREATE TABLE work_items (
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id), kind TEXT NOT NULL, cycle INTEGER NOT NULL DEFAULT 1 CHECK(cycle > 0), status TEXT NOT NULL CHECK(status IN ('ready','claimed','retry_wait','succeeded','dead','cancelled')), UNIQUE(message_id, kind, cycle));
CREATE TABLE idempotency_records (
 scope TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL, message_id TEXT NOT NULL REFERENCES messages(id), expires_at INTEGER, created_at INTEGER NOT NULL DEFAULT (unixepoch()), PRIMARY KEY(scope, key));
CREATE TABLE delivery_attempts (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES work_items(id), attempt INTEGER NOT NULL CHECK(attempt > 0), status TEXT NOT NULL, created_at INTEGER NOT NULL DEFAULT (unixepoch()), UNIQUE(work_id, attempt));
CREATE TABLE event_ledger (
 id TEXT PRIMARY KEY, connection_id TEXT NOT NULL REFERENCES channel_connections(id), provider_event_id TEXT NOT NULL, message_id TEXT NOT NULL REFERENCES messages(id), received_at INTEGER NOT NULL DEFAULT (unixepoch()), UNIQUE(connection_id, provider_event_id));
CREATE INDEX messages_chat_order ON messages(chat_id, sequence);
CREATE INDEX work_status ON work_items(status);
CREATE INDEX retention_messages ON messages(accepted_at, redacted);
CREATE TRIGGER chats_owner_version_monotonic BEFORE UPDATE OF owner_version ON chats
WHEN NEW.owner_version < OLD.owner_version BEGIN SELECT RAISE(ABORT, 'owner version cannot decrease'); END;
CREATE TRIGGER chats_config_version_monotonic BEFORE UPDATE OF config_version ON chats
WHEN NEW.config_version < OLD.config_version BEGIN SELECT RAISE(ABORT, 'config version cannot decrease'); END;"""
MIGRATIONS[4] = LEDGER_SQL
WORKER_SQL = """ALTER TABLE chats ADD COLUMN owner_id TEXT;
ALTER TABLE work_items ADD COLUMN lease_owner TEXT;
ALTER TABLE work_items ADD COLUMN lease_token TEXT;
ALTER TABLE work_items ADD COLUMN lease_expires_at INTEGER;
ALTER TABLE work_items ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_items ADD COLUMN available_at INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_items ADD COLUMN owner_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_items ADD COLUMN config_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_items ADD COLUMN route TEXT;
CREATE TABLE worker_leases (
 owner TEXT PRIMARY KEY, lease_token TEXT NOT NULL, expires_at INTEGER NOT NULL
);"""
MIGRATIONS[5] = WORKER_SQL
MIGRATIONS[6] = "ALTER TABLE delivery_attempts ADD COLUMN provider_receipt TEXT"


class MigrationTargetError(RuntimeError):
    """The requested migration target did not prove its isolation identity."""


def database_path(database_url: str) -> Path:
    """Return an absolute SQLite path from an explicit SQLAlchemy URL."""
    if not database_url.startswith(("sqlite:////", "sqlite+aiosqlite:////")):
        raise MigrationTargetError("the SQLite database URL must contain an absolute path")
    parsed = urlparse(database_url.replace("sqlite+aiosqlite", "sqlite", 1))
    if parsed.scheme != "sqlite" or not parsed.path:
        raise MigrationTargetError("an explicit SQLite database URL is required")
    path = Path("/" + unquote(parsed.path).lstrip("/"))
    if not path.is_absolute():
        raise MigrationTargetError("the SQLite database path must be absolute")
    return path


def _validate_target(profile: str, target: Path, root: Path, deployment_id: str) -> None:
    if profile != "multicanal" or not deployment_id:
        raise MigrationTargetError("multicanal profile and deployment identity are required")
    if not target.is_absolute() or not root.is_absolute() or target.name != DATABASE_NAME:
        raise MigrationTargetError("migration target does not match multicanal path policy")
    if target.parent != root or target.is_symlink() or root.is_symlink():
        raise MigrationTargetError("symlink and path aliases are forbidden")
    try:
        if root.resolve(strict=True) != root or target.parent.resolve(strict=True) != root:
            raise MigrationTargetError("resolved migration root does not match policy")
        identity = json.loads((root / SENTINEL_NAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MigrationTargetError("multicanal identity sentinel is missing or invalid") from error
    if identity != {"sentinel": SENTINEL, "deployment_id": deployment_id}:
        raise MigrationTargetError("multicanal sentinel or deployment identity mismatch")


def _validate_existing_database(target: Path, deployment_id: str) -> None:
    checksum = hashlib.sha256(MIGRATION_SQL.encode()).hexdigest()
    try:
        with sqlite3.connect(f"{target.as_uri()}?mode=ro", uri=True) as connection:
            identity = connection.execute(
                "SELECT checksum, deployment_id FROM multicanal_schema_migrations "
                "WHERE version = 1"
            ).fetchone()
    except sqlite3.Error as error:
        raise MigrationTargetError("existing database has no multicanal identity") from error
    if identity != (checksum, deployment_id):
        raise MigrationTargetError("existing database identity mismatch")


def _execute_migration_sql(connection: sqlite3.Connection, sql: str) -> None:
    statement = ""
    for character in sql:
        statement += character
        if character == ";" and sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        connection.execute(statement)


def migrate(
    profile: str,
    target: Path,
    root: Path,
    deployment_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Validate first, then transactionally apply checksummed migrations once."""
    _validate_target(profile, target, root, deployment_id)
    if target.exists():
        _validate_existing_database(target, deployment_id)
    pending = list(MIGRATIONS)
    if dry_run and not target.exists():
        return {"target": str(target), "pending": pending, "applied": []}

    applied: list[int] = []
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN")
        connection.execute(MIGRATION_SQL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS"))
        rows = {
            row[0]: (row[1], row[2])
            for row in connection.execute(
                "SELECT version, checksum, deployment_id FROM multicanal_schema_migrations"
            )
        }
        for version, sql in MIGRATIONS.items():
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if version in rows:
                if rows[version] != (checksum, deployment_id):
                    raise MigrationTargetError("migration checksum or database identity mismatch")
                pending.remove(version)
            elif not dry_run:
                if version != 1:
                    _execute_migration_sql(connection, sql)
                connection.execute(
                    "INSERT INTO multicanal_schema_migrations(version, checksum, deployment_id) VALUES(?,?,?)",
                    (version, checksum, deployment_id),
                )
                applied.append(version)
                pending.remove(version)
        if dry_run:
            connection.rollback()
    return {"target": str(target), "pending": pending, "applied": applied}


__all__ = ["MigrationTargetError", "database_path", "migrate"]
