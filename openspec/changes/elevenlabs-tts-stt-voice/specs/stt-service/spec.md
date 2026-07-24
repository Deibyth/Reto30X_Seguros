# STT Service Specification

## Purpose

Transcribe incoming user audio (voice notes from WhatsApp) into Spanish text using ElevenLabs Scribe v1, so the chat service can process the user's spoken message through the LLM pipeline.

## Requirements

### Requirement: Speech-to-Text Transcription

The system MUST transcribe audio bytes to Spanish text using ElevenLabs Scribe v1.

- **API endpoint**: `POST /speech-to-text`
- **Language**: Spanish (forced, not auto-detect)
- **Input**: Raw audio bytes (any common format: `.ogg`, `.mp3`, `.m4a`, `.wav`)

#### Scenario: Successful transcription

- GIVEN audio bytes of a Spanish voice note saying "Quiero información sobre seguros"
- WHEN the system calls `transcribe_audio(audio_bytes)`
- THEN it returns the string `"Quiero información sobre seguros"`

#### Scenario: Empty or silent audio

- GIVEN audio bytes containing only silence or background noise
- WHEN the system calls `transcribe_audio(audio_bytes)`
- THEN it returns `None`
- AND it logs "Empty transcription result"

#### Scenario: ElevenLabs API failure

- GIVEN audio bytes and a non-retryable API error (5xx, auth failure)
- WHEN the system calls `transcribe_audio(audio_bytes)`
- THEN it returns `None`
- AND it logs the failure at ERROR level

### Requirement: Integration Point

The STT service MUST expose a single async function `transcribe_audio(audio_bytes: bytes) -> str | None` consumed by the chat flow.

#### Scenario: STT consumed before LLM call

- GIVEN audio bytes received from WhatsApp connector
- WHEN the chat service processes the message
- THEN the STT result MUST replace the original audio as the `user_message` in the LLM pipeline
- AND if STT returns `None`, the chat service MUST respond with a fallback text asking the user to try again or write their message

### Requirement: Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | `""` | ElevenLabs API key (shared with TTS) |
| `ELEVENLABS_API_BASE` | `"https://api.elevenlabs.io/v1"` | API base URL |
| `ELEVENLABS_STT_MODEL` | `"scribe_v1"` | STT model identifier |

#### Scenario: Missing API key at startup

- GIVEN no `ELEVENLABS_API_KEY` configured
- WHEN the system starts
- THEN all STT calls MUST return `None`
- AND a startup warning MUST be logged
