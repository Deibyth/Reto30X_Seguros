"""External, canonical reply API for the multicanal profile."""

import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.integrations.replies import ReplyDenied, enqueue_reply, reply_status
from app.security_api_keys import KeyResult, require_api_key

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class ReplyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chat_id: str
    text: str


def _connection(db: AsyncSession) -> sqlite3.Connection:
    path = db.bind.url.database if db.bind else None
    if not path:
        raise HTTPException(503, "Reply storage unavailable")
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@router.post("/replies")
async def post_reply(body: ReplyBody, idempotency_key: str = Header(alias="Idempotency-Key"),
                     db: AsyncSession = Depends(get_db), actor: KeyResult = Depends(require_api_key("messages:reply"))):
    try:
        with _connection(db) as connection:
            reply = enqueue_reply(connection, actor.key_id, body.chat_id, body.text, idempotency_key)
    except LookupError:
        raise HTTPException(404, "Chat not found") from None
    except ReplyDenied as error:
        raise HTTPException(403, str(error)) from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    location = f"/api/integrations/replies/{reply['id']}"
    return JSONResponse({"id": reply["id"], "status_url": location}, 200 if reply["replay"] else 202, headers={"Location": location})


@router.get("/replies/{message_id}")
async def get_reply(message_id: str, db: AsyncSession = Depends(get_db),
                    actor: KeyResult = Depends(require_api_key("messages:reply"))):
    try:
        with _connection(db) as connection:
            return reply_status(connection, actor.key_id, message_id)
    except LookupError:
        raise HTTPException(404, "Reply not found") from None
