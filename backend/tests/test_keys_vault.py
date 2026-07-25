import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.security import initialize_security
from app.security_api_keys import ApiKeyService, authenticate_api_key
from app.vault import SecretUnavailable, Vault
from app.config import Settings


def request(headers=None, query=b""):
    return Request({"type": "http", "method": "GET", "path": "/api/test",
                    "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
                    "query_string": query, "scheme": "http", "server": ("test", 80),
                    "client": ("test", 1)})


@pytest.fixture
def session_factory(tmp_path):
    async def build():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'keys.db'}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            await initialize_security(db, Settings(environment="testing"))
            await db.execute(text(ApiKeyService.SCHEMA))
            await db.execute(text(Vault.SCHEMA))
            await db.commit()
        return engine, maker
    return build


@pytest.mark.asyncio
async def test_header_only_scope_and_constant_time_verification(session_factory, monkeypatch):
    engine, maker = await session_factory()
    service = ApiKeyService(b"pepper", clock=lambda: 100)
    async with maker() as db:
        issued = await service.issue(db, "operator", "reply", {"messages:reply"})
        calls = []
        original = service.compare
        monkeypatch.setattr(service, "compare", lambda left, right: (calls.append(True), original(left, right))[1])
        actor = await authenticate_api_key(request({"X-Multicanal-Api-Key": issued.plaintext}), db, "messages:reply", service)
        assert actor.key_id == issued.key_id and calls
        with pytest.raises(HTTPException) as denied:
            await authenticate_api_key(request(query=issued.plaintext.encode()), db, "messages:reply", service)
        assert denied.value.status_code == 401
        with pytest.raises(HTTPException) as scope:
            await authenticate_api_key(request({"X-Multicanal-Api-Key": issued.plaintext}), db, "crm:read", service)
        assert scope.value.status_code == 403
    await engine.dispose()


@pytest.mark.asyncio
async def test_issue_is_one_time_and_rotation_expiry_revocation(session_factory):
    engine, maker = await session_factory()
    service = ApiKeyService(b"pepper", clock=lambda: 100)
    async with maker() as db:
        first = await service.issue(db, "operator", "first", {"crm:read"}, expires_at=500)
        assert first.plaintext.startswith("mc_live_") and len(first.plaintext.split("_", 3)[3]) >= 43
        assert first.metadata["plaintext"] is None
        rotated = await service.rotate(db, "operator", first.key_id, {"crm:read"}, overlap_seconds=10)
        lineage = await db.scalar(text("SELECT rotated_from FROM api_keys WHERE prefix=:prefix"), {"prefix": rotated.key_id})
        original_id = await db.scalar(text("SELECT id FROM api_keys WHERE prefix=:prefix"), {"prefix": first.key_id})
        assert lineage == original_id
        assert await service.verify(db, first.plaintext, "crm:read")
        service.clock = lambda: 111
        assert not await service.verify(db, first.plaintext, "crm:read")
        assert await service.verify(db, rotated.plaintext, "crm:read")
        await service.revoke(db, "operator", rotated.key_id)
        assert not await service.verify(db, rotated.plaintext, "crm:read")
    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_failure_blocks_key_mutation(session_factory, monkeypatch):
    engine, maker = await session_factory()
    service = ApiKeyService(b"pepper")
    async with maker() as db:
        async def fail(*args, **kwargs):
            raise RuntimeError("audit unavailable")
        monkeypatch.setattr("app.security_api_keys.record_audit", fail)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await service.issue(db, "operator", "unsafe", {"crm:read"})
        assert await db.scalar(text("SELECT count(*) FROM api_keys")) == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_verify_audit_failure_returns_bounded_unavailable_error(session_factory, monkeypatch):
    engine, maker = await session_factory()
    service = ApiKeyService(b"pepper")
    async with maker() as db:
        issued = await service.issue(db, "operator", "verified", {"crm:read"})

        async def fail(*args, **kwargs):
            raise RuntimeError("audit internals")

        monkeypatch.setattr("app.security_api_keys.record_audit", fail)
        with pytest.raises(HTTPException) as unavailable:
            await authenticate_api_key(request({"X-Multicanal-Api-Key": issued.plaintext}), db, "crm:read", service)
        assert unavailable.value.status_code == 503
        assert unavailable.value.detail == "API key verification unavailable"
    await engine.dispose()


@pytest.mark.asyncio
async def test_vault_encrypts_versions_and_fails_closed(session_factory):
    engine, maker = await session_factory()
    vault = Vault({1: b"1" * 32, 2: b"2" * 32}, current_version=2)
    async with maker() as db:
        await vault.put(db, "operator", "telegram", "do not persist me")
        row = (await db.execute(text("SELECT ciphertext, nonce, key_version FROM vault_secrets WHERE name='telegram'"))).first()
        assert row and b"do not persist me" not in row[0] and row[2] == 2
        assert await vault.get(db, "telegram") == "do not persist me"
        assert (await vault.metadata(db, "telegram"))["present"] is True
        await db.execute(text("UPDATE vault_secrets SET ciphertext='bad' WHERE name='telegram'"))
        await db.commit()
        with pytest.raises(SecretUnavailable, match="unavailable"):
            await vault.get(db, "telegram")
    await engine.dispose()
