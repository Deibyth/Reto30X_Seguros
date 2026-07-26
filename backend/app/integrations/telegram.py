"""Provider-isolated Telegram text adapter primitives."""

from dataclasses import dataclass
import hmac
import sqlite3
import uuid

from app.models.multichannel import insert_message


@dataclass(frozen=True)
class TelegramConfig:
    connection_id: str
    secret: str
    token: str = ""


@dataclass(frozen=True)
class TelegramResponse:
    status: int
    receipt: str | None = None

    @property
    def retryable(self) -> bool:
        return self.status == 429 or self.status >= 500


def health(config: TelegramConfig | None) -> dict[str, str]:
    return {"status": "ready" if config and config.secret and config.token else "unconfigured"}


def accept_telegram(db: sqlite3.Connection, config: TelegramConfig, secret: str | None, update: dict) -> dict[str, object]:
    """Authenticate and normalize one Telegram text update before durable acceptance."""
    if not secret or not hmac.compare_digest(secret, config.secret):
        raise PermissionError("invalid Telegram secret")
    message, update_id = update.get("message"), update.get("update_id")
    chat = message.get("chat") if isinstance(message, dict) else None
    text = message.get("text") if isinstance(message, dict) else None
    if update_id is None or not isinstance(chat, dict) or chat.get("id") is None or not isinstance(text, str) or not text:
        raise ValueError("Telegram update is not supported text")
    provider_user = str(chat["id"])
    row = db.execute("SELECT c.id FROM channel_identities i JOIN chats c ON c.identity_id=i.id WHERE i.connection_id=? AND i.provider_user_id=?", (config.connection_id, provider_user)).fetchone()
    if not row:
        contact_id, identity_id, chat_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        db.execute("INSERT INTO contacts(id,display_name) VALUES (?,?)", (contact_id, str(chat.get("first_name") or provider_user)))
        db.execute("INSERT INTO channel_identities(id,connection_id,contact_id,provider_user_id) VALUES (?,?,?,?)", (identity_id, config.connection_id, contact_id, provider_user))
        db.execute("INSERT INTO chats(id,identity_id) VALUES (?,?)", (chat_id, identity_id))
    else:
        chat_id = row[0]
    return insert_message(db, chat_id, config.connection_id, f"telegram:{update_id}", text, f"telegram:{config.connection_id}", str(update_id))
