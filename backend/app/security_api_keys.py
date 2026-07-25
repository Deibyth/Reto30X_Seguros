"""Scoped integration keys; plaintext exists only in issuance response."""

import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security import record_audit

HEADER = "X-Multicanal-Api-Key"
PREFIX = re.compile(r"^mc_live_([a-f0-9]{8})_([A-Za-z0-9_-]{43})$")
SCOPES = {"messages:reply", "crm:read", "crm:write", "legacy:outbound", "channel:ingress"}


@dataclass(frozen=True)
class KeyResult:
    key_id: str
    plaintext: str | None
    metadata: dict


class ApiKeyService:
    SCHEMA = """CREATE TABLE IF NOT EXISTS api_keys (
        id TEXT PRIMARY KEY, prefix TEXT NOT NULL UNIQUE, key_hash TEXT NOT NULL,
        name TEXT NOT NULL, scopes TEXT NOT NULL, created_at INTEGER NOT NULL,
        expires_at INTEGER, revoked_at INTEGER, overlap_until INTEGER,
        rotated_from TEXT REFERENCES api_keys(id));"""

    def __init__(self, pepper: bytes, clock=time.time):
        self.pepper, self.clock = pepper, clock

    @classmethod
    def from_environment(cls, reference="MULTICANAL_API_KEY_PEPPER"):
        value = os.getenv(reference)
        if not value:
            raise HTTPException(503, "API key verification unavailable")
        return cls(value.encode())

    def digest(self, plaintext: str) -> str:
        return hmac.new(self.pepper, plaintext.encode(), hashlib.sha256).hexdigest()

    def compare(self, left: str, right: str) -> bool:
        return hmac.compare_digest(left, right)

    @staticmethod
    def _metadata(row) -> dict:
        return {"id": row[0], "prefix": row[1], "name": row[3], "scopes": row[4].split(","),
                "created_at": row[5], "expires_at": row[6], "revoked_at": row[7]}

    async def issue(self, db: AsyncSession, actor: str, name: str, scopes: set[str],
                    expires_at: int | None = None, rotated_from: str | None = None) -> KeyResult:
        if not scopes or not scopes <= SCOPES:
            raise ValueError("unsupported API key scope")
        key_id, token = secrets.token_hex(4), secrets.token_urlsafe(32)
        plaintext, now = f"mc_live_{key_id}_{token}", int(self.clock())
        row = (str(uuid.uuid4()), key_id, self.digest(plaintext), name, ",".join(sorted(scopes)),
               now, expires_at, None, None, rotated_from)
        await db.execute(text("INSERT INTO api_keys VALUES (:id,:prefix,:hash,:name,:scopes,:created,:expires,:revoked,:overlap,:rotated)"),
                         dict(zip(("id", "prefix", "hash", "name", "scopes", "created", "expires", "revoked", "overlap", "rotated"), row)))
        try:
            await record_audit(db, actor, "api_key.issue", key_id, "success", name)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return KeyResult(key_id, plaintext, {"id": key_id, "prefix": key_id, "name": name, "scopes": sorted(scopes), "expires_at": expires_at, "plaintext": None})

    async def verify(self, db: AsyncSession, plaintext: str, scope: str | None = None) -> KeyResult | None:
        match = PREFIX.fullmatch(plaintext or "")
        prefix = match.group(1) if match else ""
        row = (await db.execute(text("SELECT id,prefix,key_hash,name,scopes,created_at,expires_at,revoked_at,overlap_until,rotated_from FROM api_keys WHERE prefix=:prefix"), {"prefix": prefix})).first()
        candidate, stored = self.digest(plaintext or ""), row[2] if row else "0" * 64
        valid = bool(match and self.compare(candidate, stored) and row and not row[7] and
                     (row[6] is None or row[6] > self.clock()) and (row[8] is None or row[8] > self.clock()))
        if not valid:
            await record_audit(db, None, "api_key.verify", prefix or "unknown", "denied")
            await db.commit()
            return None
        result = KeyResult(row[1], None, self._metadata(row))
        if scope and scope not in row[4].split(","):
            await record_audit(db, row[0], "api_key.scope", scope, "denied")
            await db.commit()
            return None
        await record_audit(db, row[0], "api_key.verify", prefix, "success")
        await db.commit()
        return result

    async def revoke(self, db: AsyncSession, actor: str, key_id: str) -> None:
        await db.execute(text("UPDATE api_keys SET revoked_at=:now WHERE prefix=:id"), {"now": int(self.clock()), "id": key_id})
        try:
            await record_audit(db, actor, "api_key.revoke", key_id, "success")
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def rotate(self, db: AsyncSession, actor: str, key_id: str, scopes: set[str], overlap_seconds=0) -> KeyResult:
        until = int(self.clock()) + max(0, overlap_seconds)
        await db.execute(text("UPDATE api_keys SET overlap_until=:until WHERE prefix=:id"), {"until": until, "id": key_id})
        result = await self.issue(db, actor, "rotated", scopes, rotated_from=key_id)
        return result


async def authenticate_api_key(request: Request, db: AsyncSession, scope: str, service: ApiKeyService | None = None) -> KeyResult:
    value = request.headers.get(HEADER)
    if not value:
        raise HTTPException(401, "API key required")
    principal = await (service or ApiKeyService.from_environment()).verify(db, value, scope)
    if not principal:
        raise HTTPException(403, "API key denied")
    return principal


def require_api_key(scope: str, service: ApiKeyService | None = None):
    async def dependency(request: Request, db: AsyncSession = Depends(get_db)):
        return await authenticate_api_key(request, db, scope, service)
    return dependency
