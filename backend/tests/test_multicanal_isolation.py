import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import app.migrations as migrations
from app.migrations import MigrationTargetError, database_path, migrate


IDENTITY = "proteccion360-multicanal-v1"
DATABASE = "proteccion360_multicanal.db"


def snapshot(database: Path) -> tuple[str, tuple[str, ...]]:
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    with sqlite3.connect(database) as connection:
        schema = tuple(
            row[0]
            for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
            )
        )
    return digest, schema


def write_identity(root: Path, deployment_id: str = IDENTITY) -> Path:
    sentinel = root / ".multicanal-identity.json"
    sentinel.write_text(
        json.dumps({"sentinel": IDENTITY, "deployment_id": deployment_id}),
        encoding="utf-8",
    )
    return sentinel


@pytest.fixture
def databases(tmp_path):
    original_root = tmp_path / "data"
    multicanal_root = tmp_path / "multicanal-data"
    original_root.mkdir()
    multicanal_root.mkdir()
    original = original_root / "proteccion360.db"
    with sqlite3.connect(original) as connection:
        connection.execute("CREATE TABLE original_records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO original_records VALUES ('untouched')")
    return original, multicanal_root


@pytest.mark.parametrize("case", ["profile", "original", "missing", "sentinel", "identity"])
def test_rejected_targets_fail_before_database_access(monkeypatch, databases, case):
    original, root = databases
    before = snapshot(original)
    target = root / DATABASE
    profile = "multicanal"
    deployment_id = IDENTITY
    if case != "missing":
        write_identity(root, "other-deployment" if case == "identity" else IDENTITY)
    if case == "profile":
        profile = "development"
    elif case == "original":
        target = original
    elif case == "sentinel":
        (root / ".multicanal-identity.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "app.migrations.sqlite3.connect",
        lambda *_args, **_kwargs: pytest.fail("SQLite opened before target validation"),
    )
    with pytest.raises(MigrationTargetError):
        migrate(profile, target, root, deployment_id)
    monkeypatch.undo()
    assert snapshot(original) == before
    assert not (root / DATABASE).exists()


def test_symlink_alias_is_rejected_before_database_access(monkeypatch, databases):
    original, root = databases
    write_identity(root)
    alias = root.parent / "alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    monkeypatch.setattr(
        "app.migrations.sqlite3.connect",
        lambda *_args, **_kwargs: pytest.fail("SQLite opened through path alias"),
    )
    with pytest.raises(MigrationTargetError):
        migrate("multicanal", alias / DATABASE, root, IDENTITY)
    monkeypatch.undo()
    assert not (root / DATABASE).exists()
    assert snapshot(original)[1] == ("CREATE TABLE original_records (value TEXT NOT NULL)",)


def test_versioned_migration_only_touches_isolated_database(databases):
    original, root = databases
    write_identity(root)
    before = snapshot(original)
    target = root / DATABASE

    dry_run = migrate("multicanal", target, root, IDENTITY, dry_run=True)
    assert dry_run == {"target": str(target), "pending": [1, 2], "applied": []}
    assert not target.exists()

    result = migrate("multicanal", target, root, IDENTITY)
    replay = migrate("multicanal", target, root, IDENTITY)
    with sqlite3.connect(target) as connection:
        row = connection.execute(
            "SELECT version, deployment_id FROM multicanal_schema_migrations"
        ).fetchone()
    assert result["applied"] == [1, 2]
    assert replay["applied"] == []
    assert row == (1, IDENTITY)
    assert snapshot(original) == before


def test_existing_foreign_database_is_rejected_without_mutation(databases):
    _original, root = databases
    write_identity(root)
    target = root / DATABASE
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE foreign_records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO foreign_records VALUES ('preserve me')")
    before = snapshot(target)

    with pytest.raises(MigrationTargetError):
        migrate("multicanal", target, root, IDENTITY)

    assert snapshot(target) == before


def test_interrupted_security_migration_rolls_back_and_replays(databases, monkeypatch):
    _original, root = databases
    write_identity(root)
    target = root / DATABASE
    checksum = hashlib.sha256(migrations.MIGRATION_SQL.encode()).hexdigest()
    with sqlite3.connect(target) as connection:
        connection.execute(migrations.MIGRATION_SQL)
        connection.execute(
            "INSERT INTO multicanal_schema_migrations(version, checksum, deployment_id) "
            "VALUES (1, ?, ?)", (checksum, IDENTITY)
        )

    def interrupt(connection, sql):
        connection.execute("CREATE TABLE operators (id TEXT PRIMARY KEY)")
        raise RuntimeError("simulated interruption")

    monkeypatch.setattr(migrations, "_execute_migration_sql", interrupt)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        migrate("multicanal", target, root, IDENTITY)

    with sqlite3.connect(target) as connection:
        tables = tuple(connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        applied = tuple(connection.execute(
            "SELECT version FROM multicanal_schema_migrations ORDER BY version"
        ))
    assert ("operators",) not in tables
    assert applied == ((1,),)

    monkeypatch.undo()
    assert migrate("multicanal", target, root, IDENTITY)["applied"] == [2]
    assert migrate("multicanal", target, root, IDENTITY)["applied"] == []


def test_absolute_sqlalchemy_url_resolves_to_compose_target():
    assert database_path(
        "sqlite+aiosqlite:////app/multicanal-data/proteccion360_multicanal.db"
    ) == Path("/app/multicanal-data/proteccion360_multicanal.db")


def test_compose_declares_an_isolated_profile_path_and_volume():
    root = Path(__file__).parents[2]
    original = (root / "docker-compose.yml").read_text(encoding="utf-8")
    multicanal = (root / "docker-compose.multicanal.yml").read_text(encoding="utf-8")
    assert "proteccion360_data:/app/data" in original
    assert "profiles: [multicanal]" in multicanal
    assert "proteccion360_multicanal_data:/app/multicanal-data" in multicanal
    assert "/app/multicanal-data/proteccion360_multicanal.db" in multicanal
    assert "proteccion360_data" not in multicanal
