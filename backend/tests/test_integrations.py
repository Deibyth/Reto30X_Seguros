import asyncio
import sqlite3
import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.integrations.replies import ReplyDenied, enqueue_reply
from app.integrations.webhook import Destination, Delivery, Response, WebhookConfig, build_delivery, concrete_https_transport, validate_destination, verify_signature
from app.config import Settings
from app.main import create_app
from app.migrations import migrate
from app.multichannel.handoff import take_over
from app.multichannel.worker import WorkerCoordinator, claim_next, deliver_external_webhook
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


def test_webhook_uses_canonical_signed_payload_and_rejects_replay_escape():
    resolve = lambda host: ["8.8.8.8"]
    delivery = build_delivery("work", "chat", "message", "hello", "secret", 100, "https://hooks.example.com/path", {"hooks.example.com"}, resolve)
    assert delivery.body == b'{"chat_id":"chat","delivery_id":"work","message_id":"message","text":"hello","timestamp":100}'
    assert delivery.headers["X-Webhook-Signature"].startswith("sha256=")
    assert delivery.destination.address == "8.8.8.8" and delivery.destination.sni == "hooks.example.com"
    assert verify_signature(delivery.body, delivery.headers, "secret", now=399)
    assert not verify_signature(delivery.body, delivery.headers, "secret", now=401)
    with pytest.raises(ValueError, match="rebound"):
        validate_destination("https://hooks.example.com", {"hooks.example.com"}, lambda host: ["8.8.8.8"], lambda host: ["1.1.1.1"])


@pytest.mark.parametrize("url", [
    "http://hooks.example.com", "https://private.example.com", "https://hooks.example.com:8443",
    "https://blocked.example.com", "https://hooks.example.com/" + "x" * 2049,
])
def test_webhook_rejects_unsafe_destinations(url):
    addresses = {"private.example.com": ["127.0.0.1"], "blocked.example.com": ["8.8.8.8"]}
    with pytest.raises(ValueError):
        validate_destination(url, {"hooks.example.com"}, lambda host: addresses.get(host, ["8.8.8.8"]), lambda host: addresses.get(host, ["8.8.8.8"]))


def test_webhook_classifies_2xx_without_body_and_retryable_failures():
    delivery = build_delivery("work", "chat", "message", "hello", "secret", 100, "https://hooks.example.com", {"hooks.example.com"}, lambda host: ["8.8.8.8"])
    assert delivery.classify(Response(204, b"ignored")) == (True, False)
    assert delivery.classify(Response(429, b"retry")) == (False, True)
    assert delivery.classify(Response(400, b"permanent")) == (False, False)
    assert delivery.classify(Response(302, b"redirect", redirect=True)) == (False, False)


def test_worker_dispatches_claimed_webhook_with_bounds_and_retry_dead_letter(database):
    with sqlite3.connect(database) as db:
        reply = enqueue_reply(db, "key-a", "chat", "hello", "key")
        WorkerCoordinator(db, "worker").acquire(now=1)
        sent = []
        def retry(delivery, **bounds):
            sent.append((delivery, bounds))
            return Response(503, b"ignored")
        claim = claim_next(db, "worker", now=1)
        db.execute("UPDATE work_items SET kind='external_webhook',route='external_webhook' WHERE id=?", (claim.work_id,))
        result = deliver_external_webhook(db, claim, WebhookConfig("https://hooks.example.com", "secret", {"hooks.example.com"}), retry, lambda host: ["8.8.8.8"], now=2)
        assert result.status == "retry_wait" and sent[0][1] == {"connect_address": "8.8.8.8", "tls_server_name": "hooks.example.com", "connect_timeout": 2, "total_timeout": 10, "max_response_bytes": 16384, "allow_redirects": False}
        for now in range(7, 700):
            WorkerCoordinator(db, "worker").acquire(now=now)
            claim = claim_next(db, "worker", now=now)
            if claim:
                result = deliver_external_webhook(db, claim, WebhookConfig("https://hooks.example.com", "secret", {"hooks.example.com"}), retry, lambda host: ["8.8.8.8"], now=now + 1)
            if result.status == "dead":
                break
        assert result.status == "dead" and db.execute("SELECT status FROM work_items WHERE message_id=?", (reply["id"],)).fetchone() == ("dead",)


def test_worker_revalidates_ownership_immediately_before_send(database):
    with sqlite3.connect(database) as db:
        enqueue_reply(db, "key-a", "chat", "hello", "key")
        WorkerCoordinator(db, "worker").acquire(now=1)
        claim = claim_next(db, "worker", now=1)
        take_over(db, "chat", "operator")
        result = deliver_external_webhook(db, claim, WebhookConfig("https://hooks.example.com", "secret", {"hooks.example.com"}), lambda *_args, **_kwargs: pytest.fail("network send"), lambda host: ["8.8.8.8"], now=2)
        assert result.status == "cancelled" and db.execute("SELECT lease_token FROM work_items WHERE id=?", (claim.work_id,)).fetchone() == (None,) and db.execute("SELECT status FROM delivery_attempts WHERE work_id=?", (claim.work_id,)).fetchone() == ("cancelled",)


def test_webhook_dispatch_requires_snapshot_and_pinned_transport_contract(database):
    with sqlite3.connect(database) as db:
        enqueue_reply(db, "key-a", "chat", "hello", "key")
        WorkerCoordinator(db, "worker").acquire(now=1)
        claim = claim_next(db, "worker", now=1)
        config = WebhookConfig("https://hooks.example.com", "secret", {"hooks.example.com"}, version=7)
        db.execute("UPDATE work_items SET kind='external_webhook',route='external_webhook',config_version=7 WHERE id=?", (claim.work_id,))
        captured = {}
        def send(_delivery, *, connect_address, tls_server_name, **bounds):
            captured.update(connect_address=connect_address, tls_server_name=tls_server_name, **bounds)
            return Response(204)
        assert deliver_external_webhook(db, claim, config, send, lambda _host: ["8.8.8.8"], now=2).status == "succeeded"
        assert captured == {"connect_address": "8.8.8.8", "tls_server_name": "hooks.example.com", "connect_timeout": 2, "total_timeout": 10, "max_response_bytes": 16384, "allow_redirects": False}


def test_pre_send_fence_cancellation_is_terminal_and_fenced(database):
    with sqlite3.connect(database) as db:
        enqueue_reply(db, "key-a", "chat", "first", "first")
        WorkerCoordinator(db, "worker").acquire(now=1)
        first = claim_next(db, "worker", now=1)
        config = WebhookConfig("https://hooks.example.com", "secret", {"hooks.example.com"}, version=7)
        assert deliver_external_webhook(db, first, config, lambda *_args, **_kwargs: pytest.fail("network send"), lambda _host: ["8.8.8.8"], now=2).status == "cancelled"
        assert db.execute("SELECT status,lease_owner,lease_token,lease_expires_at FROM work_items WHERE id=?", (first.work_id,)).fetchone() == ("cancelled", None, None, None)
        assert db.execute("SELECT status FROM delivery_attempts WHERE work_id=?", (first.work_id,)).fetchone() == ("cancelled",)
        enqueue_reply(db, "key-a", "chat", "later", "later")
        later = claim_next(db, "worker", now=2)
        assert later and later.work_id != first.work_id
        db.execute("UPDATE work_items SET kind='external_webhook',route='external_webhook',config_version=7,lease_token='stale' WHERE id=?", (later.work_id,))
        assert deliver_external_webhook(db, later, config, lambda *_args, **_kwargs: pytest.fail("network send"), lambda _host: ["8.8.8.8"], now=2).status == "cancelled"
        assert db.execute("SELECT status,lease_token FROM work_items WHERE id=?", (later.work_id,)).fetchone() == ("claimed", "stale")


def _tls_listener(tmp_path, hostname):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    certificate = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(UTC) - timedelta(minutes=1)).not_valid_after(datetime.now(UTC) + timedelta(minutes=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False).sign(key, hashes.SHA256())
    cert, private_key = tmp_path / f"{hostname}.pem", tmp_path / f"{hostname}.key"
    cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    private_key.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    listener, seen = socket.socket(), {"sni": None, "http": 0}
    listener.bind(("127.0.0.1", 0)); listener.listen(1)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, private_key)
    context.set_servername_callback(lambda _socket, server_name, _context: seen.update(sni=server_name))
    def serve():
        try:
            with listener.accept()[0] as raw, context.wrap_socket(raw, server_side=True) as tls:
                if tls.recv(4096):
                    seen["http"] += 1; tls.sendall(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n")
        except ssl.SSLError:
            pass
        finally:
            listener.close()
    thread = threading.Thread(target=serve); thread.start()
    return listener.getsockname()[1], cert, seen, thread


def test_concrete_transport_pins_tcp_ip_and_verifies_sni_certificate(tmp_path):
    hostname = "hooks.example.com"
    port, certificate, seen, thread = _tls_listener(tmp_path, hostname)
    delivery = Delivery(Destination(f"https://{hostname}:{port}/hook", "127.0.0.1", hostname), b"{}", {})
    assert concrete_https_transport(delivery, connect_address="127.0.0.1", tls_server_name=hostname, ca_certs=str(certificate)).status == 204
    thread.join(timeout=1)
    assert seen == {"sni": hostname, "http": 1}

    port, certificate, seen, thread = _tls_listener(tmp_path, "wrong.example.com")
    delivery = Delivery(Destination(f"https://{hostname}:{port}/hook", "127.0.0.1", hostname), b"{}", {})
    with pytest.raises(OSError):
        concrete_https_transport(delivery, connect_address="127.0.0.1", tls_server_name=hostname, ca_certs=str(certificate))
    thread.join(timeout=1)
    assert seen == {"sni": hostname, "http": 0}
