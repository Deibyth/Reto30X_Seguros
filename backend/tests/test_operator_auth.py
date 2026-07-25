import time
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def client(tmp_path: Path, permissions="multichannel:read"):
    (tmp_path / ".multicanal-identity.json").write_text(json.dumps({
        "sentinel": "proteccion360-multicanal-v1",
        "deployment_id": "proteccion360-multicanal-v1",
    }), encoding="utf-8")
    app = create_app(Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'proteccion360_multicanal.db'}",
        app_profile="multicanal", multicanal_root=str(tmp_path),
        multicanal_deployment_id="proteccion360-multicanal-v1", environment="testing",
        operator_bootstrap_username="alice", operator_bootstrap_password="correct horse",
        operator_bootstrap_permissions=permissions,
    ))
    return TestClient(app)


def test_unauthenticated_access_is_rejected(tmp_path):
    with client(tmp_path) as http:
        assert http.get("/api/multichannel/access").status_code == 401


def test_invalid_credentials_are_rejected(tmp_path):
    with client(tmp_path) as http:
        response = http.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        assert response.status_code == 401


def test_login_uses_csrf_and_logout_revokes_session(tmp_path):
    with client(tmp_path) as http:
        login = http.post("/api/auth/login", json={"username": "alice", "password": "correct horse"})
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        assert http.get("/api/auth/me").status_code == 200
        assert http.post("/api/auth/logout").status_code == 403
        assert http.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
        assert http.get("/api/auth/me").status_code == 401


def test_expired_session_is_rejected(monkeypatch, tmp_path):
    with client(tmp_path) as http:
        assert http.post("/api/auth/login", json={"username": "alice", "password": "correct horse"}).status_code == 200
        current = time.time()
        monkeypatch.setattr("app.security.time.time", lambda: current + 9 * 3600)
        assert http.get("/api/auth/me").status_code == 401


def test_csrf_and_permission_denials_do_not_change_state(tmp_path):
    with client(tmp_path, permissions="crm:read") as http:
        login = http.post("/api/auth/login", json={"username": "alice", "password": "correct horse"})
        assert login.status_code == 200
        assert http.get("/api/multichannel/access").status_code == 403
        assert http.post("/api/auth/logout").status_code == 403


def test_audit_failure_blocks_login(monkeypatch, tmp_path):
    import app.security as security

    async def fail(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(security, "record_audit", fail)
    with client(tmp_path) as http:
        response = http.post("/api/auth/login", json={"username": "alice", "password": "correct horse"})
        assert response.status_code == 503


def test_original_profile_startup_does_not_add_operator_schema(tmp_path):
    database = tmp_path / "proteccion360.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE original_records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO original_records VALUES ('untouched')")
        before = tuple(connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
        ))

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database}",
        app_profile="original",
        environment="testing",
        operator_bootstrap_username="alice",
        operator_bootstrap_password="correct horse",
    )
    with TestClient(create_app(settings)):
        pass

    with sqlite3.connect(database) as connection:
        after = tuple(connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL "
            "AND name IN ('original_records', 'operators', 'operator_sessions', 'audit_events') "
            "ORDER BY name"
        ))
    assert after == before
