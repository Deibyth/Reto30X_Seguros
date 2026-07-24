"""Tests for TTS, STT, and AudioDecision services (Strict TDD)."""

import json
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tts import TTSService
from app.services.stt import STTService
from app.services.audio_decision import AudioDecisionEngine, AudioContext


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tts_budget_path(tmp_path: Path) -> Path:
    budget_file = tmp_path / "tts_budget.json"
    budget_file.write_text(json.dumps({"month": "2026-07", "chars_used": 0}))
    return budget_file


@pytest.fixture
def tts_static_dir(tmp_path: Path) -> Path:
    audio_dir = tmp_path / "static" / "audio"
    audio_dir.mkdir(parents=True)
    return audio_dir


@pytest.fixture
def tts_service(tts_static_dir: Path, tts_budget_path: Path) -> TTSService:
    return TTSService(
        api_key="test-key",
        voice_id="test-voice",
        static_dir=str(tts_static_dir),
        budget_path=str(tts_budget_path),
    )


@pytest.fixture
def stt_service() -> STTService:
    return STTService(api_key="test-key")


# ── TTSService Tests ────────────────────────────────────────────────────


class TestTTSService:
    """RED: test TTSService.generate() behavior."""

    @pytest.mark.asyncio
    async def test_generate_cache_hit(self, tts_service: TTSService, tts_static_dir: Path):
        """Cache hit returns URL without calling API."""
        text = "Hola, soy Anna"
        md5 = hashlib.md5(text.encode()).hexdigest()
        cache_file = tts_static_dir / f"{md5}.mp3"
        cache_file.write_bytes(b"fake audio data")

        result = await tts_service.generate(text)

        assert result == f"/audio/{md5}.mp3"

    @pytest.mark.asyncio
    async def test_generate_cache_miss_api_success(self, tts_service: TTSService):
        """Cache miss calls API, saves file, returns URL."""
        text = "Hola, soy Anna"
        md5 = hashlib.md5(text.encode()).hexdigest()

        with patch.object(tts_service, "_call_elevenlabs", new=AsyncMock(return_value=b"mp3 data")):
            result = await tts_service.generate(text)

        assert result == f"/audio/{md5}.mp3"
        cache_path = Path(tts_service._static_dir) / f"{md5}.mp3"
        assert cache_path.exists()
        assert cache_path.read_bytes() == b"mp3 data"

    @pytest.mark.asyncio
    async def test_generate_api_failure_returns_none(self, tts_service: TTSService):
        """API failure does not raise, returns None."""
        text = "Hola, soy Anna"

        with patch.object(tts_service, "_call_elevenlabs", new=AsyncMock(return_value=None)):
            result = await tts_service.generate(text)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_budget_exceeded(self, tts_service: TTSService, tts_budget_path: Path):
        """Over-budget request returns None."""
        budget = json.loads(tts_budget_path.read_text())
        budget["chars_used"] = 9500
        tts_budget_path.write_text(json.dumps(budget))

        text = "a" * 100  # Would exceed 9500 budget
        result = await tts_service.generate(text)

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_budget_near_limit_allowed(self, tts_service: TTSService, tts_budget_path: Path):
        """At 9499 chars, a 1-char text should still work."""
        budget = json.loads(tts_budget_path.read_text())
        budget["chars_used"] = 9499
        tts_budget_path.write_text(json.dumps(budget))

        text = "x"
        md5 = hashlib.md5(text.encode()).hexdigest()

        with patch.object(tts_service, "_call_elevenlabs", new=AsyncMock(return_value=b"mp3")):
            result = await tts_service.generate(text)

        assert result == f"/audio/{md5}.mp3"

    def test_cache_key(self, tts_service: TTSService):
        """Cache key is MD5 hex digest of text."""
        text = "Hola"
        expected = hashlib.md5(text.encode()).hexdigest()
        assert tts_service._cache_key(text) == expected


# ── STTService Tests ────────────────────────────────────────────────────


class TestSTTService:
    """RED: test STTService.transcribe() behavior."""

    @pytest.mark.asyncio
    async def test_transcribe_success(self, stt_service: STTService):
        """Successful transcription returns text."""
        audio_bytes = b"fake audio bytes"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"text": "quiero un seguro de vida"})

        with patch.object(stt_service, "_call_scribe", new=AsyncMock(return_value=mock_response)):
            result = await stt_service.transcribe(audio_bytes)

        assert result == "quiero un seguro de vida"

    @pytest.mark.asyncio
    async def test_transcribe_api_error_returns_none(self, stt_service: STTService):
        """API error returns None."""
        audio_bytes = b"fake"
        with patch.object(stt_service, "_call_scribe", new=AsyncMock(return_value=None)):
            result = await stt_service.transcribe(audio_bytes)

        assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_empty_text_returns_none(self, stt_service: STTService):
        """Empty transcribed text returns None."""
        audio_bytes = b"silence"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"text": ""})

        with patch.object(stt_service, "_call_scribe", new=AsyncMock(return_value=mock_response)):
            result = await stt_service.transcribe(audio_bytes)

        assert result is None


# ── AudioDecisionEngine Tests ────────────────────────────────────────────


class TestAudioDecisionEngine:
    """RED: test AudioDecisionEngine.should_send_audio() rules."""

    def test_never_url_in_text(self):
        """URLs must never trigger audio."""
        text = "Visita nuestra web en https://ejemplo.com"
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=True, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is False

    def test_never_phone_in_text(self):
        """Phone numbers must never trigger audio."""
        text = "Llama al 3001234567 para más info"
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=True, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is False

    def test_never_email_in_text(self):
        """Email addresses must never trigger audio."""
        text = "Escríbenos a info@seguros.com"
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=True, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is False

    def test_never_error_short(self):
        """Very short error-like responses never get audio."""
        text = "Lo siento, no entendí"
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=False, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is False

    def test_strong_signal_greeting(self):
        """Greetings to potential client should send audio."""
        text = "¡Hola! Soy Anna, tu asesora de Colsubsidio. ¿En qué puedo ayudarte?"
        context = AudioContext(is_greeting=True, user_sent_audio=False, product_mentioned=False, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is True

    def test_strong_signal_user_sent_audio(self):
        """If user sent audio, Anna responds with audio."""
        text = "Claro, te explico los seguros de vida disponibles."
        context = AudioContext(is_greeting=False, user_sent_audio=True, product_mentioned=True, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is True

    def test_strong_signal_product_question(self):
        """Product explanation for specific insurance should send audio."""
        text = "El seguro de vida cubre fallecimiento por cualquier causa, y accidentes personales. Coberturas desde $10.000.000."
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=True, text_length=len(text))
        assert AudioDecisionEngine.should_send_audio(text, context) is True

    def test_borderline_variability(self):
        """Borderline long text without strong signals uses variability (~60%)."""
        text = (
            "Gracias por tu interés en nuestros seguros de vida y hogar. He "
            "revisado tu perfil detenidamente y tengo varias opciones que "
            "podrían ajustarse muy bien a lo que estás buscando. ¿Te parece "
            "si te explico las coberturas principales de cada una y luego "
            "decidimos juntos cuál es la mejor opción para tu caso particular?"
        )
        context = AudioContext(is_greeting=False, user_sent_audio=False, product_mentioned=False, text_length=len(text))

        results = set()
        for _ in range(200):
            results.add(AudioDecisionEngine.should_send_audio(text, context))

        # With ~60% probability, in 200 tries we should see both outcomes
        assert len(results) == 2, "Variability should produce both True and False"


# ── Integration Tests ────────────────────────────────────────────────────


class TestChatAudioIntegration:
    """Test audio_url field appears in chat responses."""

    def test_echo_chat_response_has_audio_url(self, echo_client):
        """Echo fallback should include audio_url: None."""
        response = echo_client.post("/chat", json={"message": "Hola"})
        assert response.status_code == 200
        body = response.json()
        assert "audio_url" in body
        assert body["audio_url"] is None

    def test_chat_response_has_audio_url(self, test_client):
        """Full chat response should include audio_url (None when no TTS)."""
        response = test_client.post("/chat", json={"message": "Hola"})
        assert response.status_code == 200
        body = response.json()
        assert "audio_url" in body
        assert body["audio_url"] is None

    def test_transcribe_without_tts_returns_error(self, echo_client):
        """Transcribe without STT service returns error response."""
        response = echo_client.post(
            "/chat/transcribe",
            files={"audio": ("test.mp3", b"", "audio/mpeg")},
        )
        assert response.status_code == 200  # Error is returned as JSON, not HTTP error
        body = response.json()
        assert "text" in body
        assert body["text"] is None
        assert "error" in body

    def test_chat_response_shape(self, test_client):
        """Verify ChatResponse shape when audio_url is absent."""
        response = test_client.post("/chat", json={"message": "seguro de vida"})
        assert response.status_code == 200
        body = response.json()
        # All expected fields present
        assert "reply" in body
        assert "session_id" in body
        assert "model" in body
        assert "timestamp" in body
        assert "campos_actualizados" in body
        assert "completitud_pct" in body
        assert "audio_url" in body
