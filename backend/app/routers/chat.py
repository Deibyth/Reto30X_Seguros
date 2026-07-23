"""Chat router — POST /chat with ChatService orchestration.

Uses ChatService (initialized in app lifespan) for session management,
history loading, two-phase AI tool loop, and conversation persistence.
Falls back to echo stub if no AIClient is configured.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.chat import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming chat message from the user."""

    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    """AI-powered response from the chat endpoint."""

    reply: str
    timestamp: datetime
    session_id: str | None = None
    model: str | None = None
    campos_actualizados: list[str] = Field(default_factory=list)
    completitud_pct: float = Field(default=0.0)


@router.post("/chat", response_model=ChatResponse)
async def chat_handler(
    request: ChatRequest,
    http_request: Request,
    x_session_id: str | None = Header(None, alias="X-Session-Id"),
) -> ChatResponse:
    """Process a chat message using ChatService.

    Creates a new session if no ``X-Session-Id`` header is provided.
    Returns 404 if the provided session ID does not exist.
    """
    chat_service: ChatService | None = getattr(
        http_request.app.state, "chat_service", None
    )

    if chat_service is None:
        # Fallback: echo stub (no API key / service configured)
        logger.debug("ChatService not available — using echo fallback")
        return ChatResponse(
            reply=f"Echo: {request.message}",
            timestamp=datetime.now(timezone.utc),
            session_id=x_session_id,
            model="echo-fallback",
        )

    # Resolve session
    if x_session_id:
        session = await chat_service.get_session_by_id(x_session_id)
        if session is None:
            raise HTTPException(
                status_code=404,
                detail=f"Session '{x_session_id}' not found.",
            )
    else:
        session, _ = await chat_service.get_or_create_session(None)

    # Process message
    try:
        result = await chat_service.process_message(session, request.message)

        return ChatResponse(
            reply=result.reply,
            timestamp=result.timestamp,
            session_id=result.session_id,
            model=result.model,
            campos_actualizados=result.campos_actualizados,
            completitud_pct=result.completitud_pct,
        )

    except Exception as exc:
        logger.error("Chat handler error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible en este momento.",
        ) from exc
