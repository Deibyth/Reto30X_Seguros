"""STTService — ElevenLabs Scribe speech-to-text.

Transcribes audio bytes to text using ElevenLabs Scribe API.
Falls back to None on any failure — never raises.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"


class STTService:
    """Transcribe audio to text via ElevenLabs Scribe."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe(self, audio_bytes: bytes) -> str | None:
        """Transcribe *audio_bytes* to text, or None on failure."""
        if not audio_bytes:
            return None

        response = await self._call_scribe(audio_bytes)
        if response is None:
            return None

        try:
            data = response.json()
            text = (data.get("text") or "").strip()
            return text if text else None
        except Exception as exc:
            logger.warning("STT parse error: %s", exc)
            return None

    async def _call_scribe(self, audio_bytes: bytes) -> httpx.Response | None:
        """Call ElevenLabs Scribe API. Returns response or None on failure."""
        headers = {"xi-api-key": self._api_key}
        files = {"audio": ("audio.mp3", audio_bytes, "audio/mpeg")}
        data = {
            "model_id": "scribe_v1",
            "tag_audio_events": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    ELEVENLABS_STT_URL,
                    headers=headers,
                    files=files,
                    data=data,
                )
                resp.raise_for_status()
                return resp
        except httpx.TimeoutException:
            logger.warning("STT API timed out")
        except httpx.HTTPStatusError as exc:
            logger.warning("STT API error %s: %s", exc.response.status_code, exc.response.text[:200])
        except Exception as exc:
            logger.warning("STT API unexpected error: %s", exc)

        return None
