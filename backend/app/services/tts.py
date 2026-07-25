"""TTSService — ElevenLabs TTS with MD5-based audio cache and Cloudinary upload.

Generates speech from text using ElevenLabs API. Caches results by MD5 hash
to avoid redundant API calls. Optionally uploads to Cloudinary for persistent
storage accessible from WhatsApp. Falls back to None on any failure — never raises.
"""

import hashlib
import json
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
BUDGET_LIMIT = 9500  # Leave 500-char margin on free tier (10K/month)


class TTSService:
    """Generate TTS audio from text with caching, budget tracking, and optional Cloudinary upload."""

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        static_dir: str,
        budget_path: str,
        cloudinary_service: object | None = None,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._static_dir = static_dir
        self._budget_path = budget_path
        self._cloudinary = cloudinary_service

    async def generate(self, text: str) -> str | None:
        """Generate audio for *text* and return URL, or None on failure.

        Returns a Cloudinary URL when upload succeeds, otherwise returns the
        local ``/audio/{md5_hash}.mp3`` path.
        """
        if not text:
            return None

        # 1. Check budget
        if not self._check_budget(text):
            logger.warning("TTS budget exceeded — skipping audio for %d chars", len(text))
            return None

        # 2. Check cache
        md5 = self._cache_key(text)
        cache_path = self._get_cache_path(md5)
        if cache_path.exists():
            logger.debug("TTS cache hit: %s", md5)
            # If cached locally, still try to upload if Cloudinary is enabled
            # and we haven't uploaded before (idempotent upload)
            cloudinary_url = await self._upload_to_cloudinary(cache_path, md5)
            if cloudinary_url:
                return cloudinary_url
            return f"/audio/{md5}.mp3"

        # 3. Call API
        audio_data = await self._call_elevenlabs(text)
        if audio_data is None:
            return None

        # 4. Save to cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(audio_data)
        logger.debug("TTS cache saved: %s (%d bytes)", md5, len(audio_data))

        # 5. Upload to Cloudinary (async, best-effort)
        cloudinary_url = await self._upload_to_cloudinary(cache_path, md5)

        # 6. Update budget
        self._update_budget(text)

        if cloudinary_url:
            return cloudinary_url
        return f"/audio/{md5}.mp3"

    async def _upload_to_cloudinary(self, local_path: Path, md5: str) -> str | None:
        """Upload audio to Cloudinary if service is available."""
        if self._cloudinary is None:
            return None
        if not getattr(self._cloudinary, "enabled", False):
            return None
        return await self._cloudinary.upload_audio(
            local_path=local_path,
            public_id=f"anna_audio/{md5}",
        )

    async def _call_elevenlabs(self, text: str) -> bytes | None:
        """Call ElevenLabs TTS API. Returns raw MP3 bytes or None on failure."""
        url = ELEVENLABS_TTS_URL.format(voice_id=self._voice_id)
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self._api_key,
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.content
        except httpx.TimeoutException:
            logger.warning("TTS API timed out for %d chars", len(text))
        except httpx.HTTPStatusError as exc:
            logger.warning("TTS API error %s: %s", exc.response.status_code, exc.response.text[:200])
        except Exception as exc:
            logger.warning("TTS API unexpected error: %s", exc)

        return None

    def _cache_key(self, text: str) -> str:
        """Return MD5 hex digest as cache key."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _get_cache_path(self, md5_hash: str) -> Path:
        return Path(self._static_dir) / f"{md5_hash}.mp3"

    def _check_budget(self, text: str) -> bool:
        """Return True if adding *text* would not exceed the budget limit."""
        try:
            budget = json.loads(Path(self._budget_path).read_text())
            current = budget.get("chars_used", 0)
            return (current + len(text)) <= BUDGET_LIMIT
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("TTS budget file error: %s", exc)
            return True  # If budget file is broken, allow to avoid blocking audio

    def _update_budget(self, text: str) -> None:
        """Persist updated character count to budget file."""
        try:
            budget_path = Path(self._budget_path)
            budget = json.loads(budget_path.read_text())
            budget["chars_used"] = budget.get("chars_used", 0) + len(text)
            budget_path.write_text(json.dumps(budget))
        except Exception as exc:
            logger.warning("Failed to update TTS budget: %s", exc)
