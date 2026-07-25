"""Chat router — POST /chat with ChatService orchestration.

Uses ChatService (initialized in app lifespan) for session management,
history loading, two-phase AI tool loop, and conversation persistence.
Falls back to echo stub if no AIClient is configured.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
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
    audio_url: str | None = None
    buttons: list[dict] | None = None


class TranscribeResponse(BaseModel):
    """Response from the speech-to-text transcription endpoint."""

    text: str | None = None
    error: str | None = None


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
            buttons=result.buttons,
            audio_url=result.audio_url,
        )

    except Exception as exc:
        logger.error("Chat handler error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible en este momento.",
        ) from exc


@router.post("/chat/transcribe", response_model=TranscribeResponse)
async def transcribe_handler(
    audio: UploadFile = File(...),
    http_request: Request = None,  # type: ignore[assignment]
) -> TranscribeResponse:
    """Transcribe an audio file to text using ElevenLabs Scribe.

    Accepts an audio upload, returns transcribed text.
    Returns ``text: None`` and an ``error`` message on failure.
    """
    chat_service: ChatService | None = getattr(
        http_request.app.state, "chat_service", None
    )

    if chat_service is None or chat_service.stt_service is None:
        return TranscribeResponse(
            text=None,
            error="Speech-to-text service is not available.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        return TranscribeResponse(
            text=None,
            error="No audio data received.",
        )

    try:
        text = await chat_service.stt_service.transcribe(audio_bytes)
        return TranscribeResponse(text=text, error=None if text else "Transcription returned no text.")
    except Exception as exc:
        logger.error("Transcribe handler error: %s", exc)
        return TranscribeResponse(text=None, error="Transcription service error.")
