"""AES-256-GCM vault with deployment-provided master-key references."""

import base64
import os
import secrets
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import record_audit


class SecretUnavailable(RuntimeError):
    """A secret cannot safely be decrypted; never contains secret material."""


class Vault:
    SCHEMA = """CREATE TABLE IF NOT EXISTS vault_secrets (
        name TEXT PRIMARY KEY, ciphertext BLOB NOT NULL, nonce BLOB NOT NULL,
        key_version INTEGER NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);"""

    def __init__(self, keys: dict[int, bytes], current_version: int):
        if current_version not in keys or any(len(key) != 32 for key in keys.values()):
            raise ValueError("invalid vault key configuration")
        self.keys, self.current_version = keys, current_version

    @classmethod
    def from_reference(cls, reference: str, version: int = 1):
        encoded = os.getenv(reference)
        if not encoded:
            raise SecretUnavailable("master key reference unavailable")
        try:
            key = base64.urlsafe_b64decode(encoded.encode())
        except Exception as error:
            raise SecretUnavailable("master key reference unavailable") from error
        return cls({version: key}, version)

    async def put(self, db: AsyncSession, actor: str, name: str, secret: str) -> None:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self.keys[self.current_version]).encrypt(nonce, secret.encode(), name.encode())
        now = int(time.time())
        await db.execute(text("INSERT INTO vault_secrets(name,ciphertext,nonce,key_version,created_at,updated_at) VALUES (:name,:cipher,:nonce,:version,:now,:now) ON CONFLICT(name) DO UPDATE SET ciphertext=:cipher,nonce=:nonce,key_version=:version,updated_at=:now"),
                         {"name": name, "cipher": ciphertext, "nonce": nonce, "version": self.current_version, "now": now})
        try:
            await record_audit(db, actor, "vault.put", name, "success")
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def get(self, db: AsyncSession, name: str) -> str:
        row = (await db.execute(text("SELECT ciphertext,nonce,key_version FROM vault_secrets WHERE name=:name"), {"name": name})).first()
        if not row or row[2] not in self.keys:
            raise SecretUnavailable("secret unavailable")
        try:
            return AESGCM(self.keys[row[2]]).decrypt(row[1], row[0], name.encode()).decode()
        except (InvalidTag, ValueError, UnicodeDecodeError, TypeError) as error:
            raise SecretUnavailable("secret unavailable") from error

    async def metadata(self, db: AsyncSession, name: str) -> dict:
        row = (await db.execute(text("SELECT key_version,updated_at FROM vault_secrets WHERE name=:name"), {"name": name})).first()
        return {"name": name, "present": bool(row), "key_version": row[0] if row else None, "updated_at": row[1] if row else None}
