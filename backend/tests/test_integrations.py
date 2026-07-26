import asyncio
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.integrations.replies import ReplyDenied, enqueue_reply
from app.config import Settings
from app.main import create_app
from app.migrations import migrate
from app.multichannel.handoff import take_over
from app.database import get_db
from app.routers.integrations import ReplyBody, router
from app.security_api_keys import KeyResult
from app.security_api_keys import ApiKeyService


@pytest.fixture
def database(tmp_path):
    tmp_path.joinpath(".multicanal-identity.json").write_text(
        '{"sentinel":"proteccion360-multicanal-v1","deployment_id":"test"}', encoding="utf-8"
    )
    target = tmp_path / "proteccion360_multicanal.db"
    migrate("multicanal", target, tmp_path, "test")
    with sqlite3.connect(target) as db:
        db.executescript("""INSERT INTO channel_connections VALUES ('conn','telegram','ready');
        INSERT INTO contacts(id,display_name) VALUES ('contact','Ada');
        INSERT INTO channel_identities VALUES ('identity','conn','contact','provider-id',NULL);
        INSERT INTO chats(id,identity_id) VALUES ('chat','identity');""")
    return target


def test_reply_is_caller_scoped_idempotent_and_canonical(database):
    with sqlite3.connect(database) as db:
        first = enqueue_reply(db, "key-a", "chat", "hello", "same-key")
        assert enqueue_reply(db, "key-a", "chat", "hello", "same-key") == {**first, "replay": True}
        with pytest.raises(ValueError, match="conflicts"):
            enqueue_reply(db, "key-a", "chat", "changed", "same-key")
        assert enqueue_reply(db, "key-b", "chat", "hello", "same-key")["id"] != first["id"]
        assert db.execute("SELECT content FROM messages WHERE id=?", (first["id"],)).fetchone() == ("hello",)


def test_takeover_cancels_queued_reply_and_blocks_new_enqueue(database):
    with sqlite3.connect(database) as db:
        reply = enqueue_reply(db, "key-a", "chat", "hello", "key")
        take_over(db, "chat", "operator-a")
        assert db.execute("SELECT status FROM work_items WHERE message_id=?", (reply["id"],)).fetchone() == ("cancelled",)
        with pytest.raises(ReplyDenied):
            enqueue_reply(db, "key-a", "chat", "later", "later-key")


def test_reply_body_rejects_provider_ids():
    assert ReplyBody(chat_id="chat", text="hello").chat_id == "chat"
    with pytest.raises(ValidationError):
        ReplyBody(chat_id="chat", text="hello", provider_id="provider-id")


def test_post_reply_returns_canonical_status_url_and_replay(database):
    session = type("Session", (), {"bind": type("Bind", (), {"url": type("Url", (), {"database": str(database)})()})()})()
    actor = KeyResult("key-a", None, {})
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    for route in app.routes:
        if route.path.startswith("/api/integrations/replies"):
            app.dependency_overrides[route.dependant.dependencies[1].call] = lambda: actor
    with TestClient(app) as client:
        first = client.post("/api/integrations/replies", headers={"Idempotency-Key": "key"}, json={"chat_id": "chat", "text": "hello"})
        replay = client.post("/api/integrations/replies", headers={"Idempotency-Key": "key"}, json={"chat_id": "chat", "text": "hello"})
        assert first.status_code == 202 and replay.status_code == 200 and first.json() == replay.json()
        assert client.get(first.json()["status_url"]).json()["status"] == "queued"


def test_reply_routes_are_multicanal_only():
    paths = lambda profile: {route.path for route in create_app(Settings(app_profile=profile)).routes}
    assert "/api/integrations/replies" not in paths("original")
    assert "/api/integrations/replies" in paths("multicanal")


def _reply_app(database, actor):
    session = type("Session", (), {"bind": type("Bind", (), {"url": type("Url", (), {"database": str(database)})()})()})()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    for route in app.routes:
        if route.path.startswith("/api/integrations/replies"):
            app.dependency_overrides[route.dependant.dependencies[1].call] = lambda: actor
    return app


def test_reply_route_denies_missing_or_insufficient_key_before_enqueue(database, monkeypatch):
    from app import database as database_module

    monkeypatch.setenv("MULTICANAL_API_KEY_PEPPER", "test-pepper")
    database_module.init_engine(f"sqlite+aiosqlite:///{database}")

    async def issue_read_only_key():
        async with database_module.async_session_maker() as session:
            return await ApiKeyService(b"test-pepper").issue(session, "operator", "read-only", {"crm:read"})

    key = asyncio.run(issue_read_only_key()).plaintext
    app = FastAPI()
    app.include_router(router)
    try:
        with TestClient(app) as client:
            missing = client.post("/api/integrations/replies", headers={"Idempotency-Key": "missing"}, json={"chat_id": "chat", "text": "hello"})
            insufficient = client.post("/api/integrations/replies", headers={"Idempotency-Key": "read-only", "X-Multicanal-Api-Key": key}, json={"chat_id": "chat", "text": "hello"})
        with sqlite3.connect(database) as db:
            assert (missing.status_code, insufficient.status_code) == (401, 403)
            assert db.execute("SELECT COUNT(*) FROM messages").fetchone() == (0,)
            assert db.execute("SELECT COUNT(*) FROM work_items").fetchone() == (0,)
    finally:
        asyncio.run(database_module.dispose_engine())


def test_unknown_chat_is_hidden_without_enqueue_or_cross_caller_disclosure(database):
    app = _reply_app(database, KeyResult("caller-a", None, {}))
    with TestClient(app) as client:
        unknown = client.post("/api/integrations/replies", headers={"Idempotency-Key": "unknown"}, json={"chat_id": "missing", "text": "hello"})
        created = client.post("/api/integrations/replies", headers={"Idempotency-Key": "known"}, json={"chat_id": "chat", "text": "hello"})
    with sqlite3.connect(database) as db:
        assert unknown.status_code == 404 and "provider-id" not in unknown.text
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone() == (1,)
        assert db.execute("SELECT COUNT(*) FROM work_items").fetchone() == (1,)
    other = _reply_app(database, KeyResult("caller-b", None, {}))
    with TestClient(other) as client:
        assert client.get(created.json()["status_url"]).status_code == 404


def test_ownership_change_between_validation_and_fenced_insert_creates_no_work(database, monkeypatch):
    from app.integrations import replies

    original_chat = replies._chat

    def take_over_after_validation(db, chat_id):
        chat = original_chat(db, chat_id)
        with sqlite3.connect(database) as racer:
            take_over(racer, chat_id, "operator-a")
        return chat

    monkeypatch.setattr(replies, "_chat", take_over_after_validation)
    app = _reply_app(database, KeyResult("caller-a", None, {}))
    with TestClient(app) as client:
        response = client.post("/api/integrations/replies", headers={"Idempotency-Key": "race"}, json={"chat_id": "chat", "text": "hello"})
    with sqlite3.connect(database) as db:
        assert response.status_code == 403
        assert db.execute("SELECT owner_id, owner_version FROM chats WHERE id='chat'").fetchone() == ("operator-a", 1)
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM work_items").fetchone() == (0,)
