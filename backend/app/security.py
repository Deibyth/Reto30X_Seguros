"""Operator sessions, CSRF, permissions, and append-only audit persistence."""

import hashlib
import hmac
import secrets
import time
import uuid
from collections.abc import Callable

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db

SESSION_IDLE = 8 * 60 * 60
SESSION_ABSOLUTE = 24 * 60 * 60
COOKIE = "operator_session"
_hasher = PasswordHasher()

SCHEMA = """CREATE TABLE IF NOT EXISTS operators (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, permissions TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS operator_sessions (id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, csrf_token TEXT NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL, expires_at INTEGER NOT NULL, revoked_at INTEGER);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, actor_id TEXT, action TEXT NOT NULL, target TEXT NOT NULL, outcome TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL);"""


async def initialize_security(db: AsyncSession, settings: Settings) -> None:
    for statement in SCHEMA.split(";"):
        if statement.strip():
            await db.execute(text(statement))
    await db.execute(text("CREATE TRIGGER IF NOT EXISTS audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END"))
    await db.execute(text("CREATE TRIGGER IF NOT EXISTS audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END"))
    if settings.operator_bootstrap_username and settings.operator_bootstrap_password:
        exists = await db.scalar(text("SELECT id FROM operators WHERE username=:u"), {"u": settings.operator_bootstrap_username})
        if not exists:
            await db.execute(text("INSERT INTO operators VALUES (:id,:u,:p,:permissions,1)"), {
                "id": str(uuid.uuid4()), "u": settings.operator_bootstrap_username,
                "p": _hasher.hash(settings.operator_bootstrap_password),
                "permissions": settings.operator_bootstrap_permissions,
            })
    await db.commit()


async def record_audit(db: AsyncSession, actor: str | None, action: str, target: str, outcome: str, details: str = "") -> None:
    safe = hashlib.sha256(details.encode()).hexdigest() if details else ""
    await db.execute(text("INSERT INTO audit_events VALUES (:id,:actor,:action,:target,:outcome,:details,:now)"), {
        "id": str(uuid.uuid4()), "actor": actor, "action": action, "target": target,
        "outcome": outcome, "details": safe, "now": int(time.time()),
    })


async def operator(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    session_id = request.cookies.get(COOKIE)
    row = await db.execute(text("SELECT s.id,s.csrf_token,s.operator_id,s.last_seen,s.expires_at,o.username,o.permissions FROM operator_sessions s JOIN operators o ON o.id=s.operator_id WHERE s.id=:id AND s.revoked_at IS NULL AND o.active=1"), {"id": session_id or ""})
    value = row.mappings().first()
    now = int(time.time())
    if not value or now > min(value["expires_at"], value["last_seen"] + SESSION_IDLE):
        raise HTTPException(401, "Authentication required")
    await db.execute(text("UPDATE operator_sessions SET last_seen=:now WHERE id=:id"), {"now": now, "id": value["id"]})
    await db.commit()
    return dict(value)


def require_permission(permission: str) -> Callable:
    async def dependency(actor: dict = Depends(operator), db: AsyncSession = Depends(get_db)) -> dict:
        if permission not in actor["permissions"].split(","):
            await record_audit(db, actor["operator_id"], "permission", permission, "denied")
            await db.commit()
            raise HTTPException(403, "Permission denied")
        return actor
    return dependency


async def require_csrf(request: Request, actor: dict = Depends(operator), db: AsyncSession = Depends(get_db)) -> dict:
    if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), actor["csrf_token"]):
        await record_audit(db, actor["operator_id"], "csrf", request.url.path, "denied")
        await db.commit()
        raise HTTPException(403, "CSRF validation failed")
    return actor


class Login(BaseModel):
    username: str
    password: str


async def authenticate(payload: Login, request: Request, db: AsyncSession) -> tuple[dict, str]:
    row = await db.execute(text("SELECT id,password_hash,permissions FROM operators WHERE username=:u AND active=1"), {"u": payload.username})
    found = row.mappings().first()
    valid = False
    if found:
        try:
            valid = _hasher.verify(found["password_hash"], payload.password)
        except Exception:
            valid = False
    if not valid:
        try:
            await record_audit(db, found["id"] if found else None, "login", payload.username, "denied")
            await db.commit()
        except Exception as error:
            await db.rollback()
            raise HTTPException(503, "Security audit unavailable") from error
        raise HTTPException(401, "Invalid credentials")
    now = int(time.time())
    session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    await db.execute(text("INSERT INTO operator_sessions VALUES (:id,:operator,:csrf,:now,:now,:expires,NULL)"), {
        "id": session_id, "operator": found["id"], "csrf": csrf, "now": now, "expires": now + SESSION_ABSOLUTE,
    })
    try:
        await record_audit(db, found["id"], "login", payload.username, "success")
        await db.commit()
    except Exception as error:
        await db.rollback()
        raise HTTPException(503, "Security audit unavailable") from error
    return {"id": found["id"], "username": payload.username, "permissions": found["permissions"]}, (session_id, csrf)
