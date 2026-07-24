# TTS Service Specification

## Purpose

Convert Anna's text responses to spoken audio (Spanish) using ElevenLabs API, cache the results as `.ogg` files, and serve them as static URLs. The service MUST fail gracefully — never block the chat flow.

## Requirements

### Requirement: TTS Generation

The system MUST generate audio from text using the ElevenLabs Text-to-Speech API.

- **Voice ID**: `21m00Tcm4TlvDq8ikWAM` (Rachel)
- **Model**: `eleven_multilingual_v2`
- **Output format**: `.ogg` (Opus in Ogg container, compatible with WhatsApp voice notes)

#### Scenario: Successful TTS generation

- GIVEN a text string in Spanish (e.g., "Hola, soy Anna tu asesora de Colsubsidio")
- WHEN the system calls `generate_audio(text)`
- THEN it returns the URL path to a cached `.ogg` file
- AND the audio content plays the spoken version of the input text

#### Scenario: ElevenLabs API returns an error

- GIVEN a text string and the ElevenLabs API returns HTTP 5xx
- WHEN the system calls `generate_audio(text)`
- THEN it returns `None` (no audio available)
- AND it logs the failure at WARNING level

#### Scenario: ElevenLabs API rate limit hit (429)

- GIVEN a text string and ElevenLabs responds with 429 Too Many Requests
- WHEN the system calls `generate_audio(text)`
- THEN it returns `None`
- AND it logs the rate-limit event with retry-after info

### Requirement: Audio Cache

The system MUST cache generated audio to avoid redundant ElevenLabs API calls.

- **Cache key**: MD5 hex digest of the input text
- **Cache storage**: `backend/app/static/audio/` directory
- **File naming**: `{md5_hash}.ogg`

#### Scenario: Cache hit

- GIVEN a previously generated text
- WHEN the system calls `generate_audio(text)`
- THEN it returns the cached `.ogg` URL without calling the ElevenLabs API

#### Scenario: Cache miss

- GIVEN a text never seen before
- WHEN the system calls `generate_audio(text)`
- THEN it calls the ElevenLabs API, saves the response to `static/audio/{md5}.ogg`, and returns the new URL

### Requirement: Audio URL Serving

The system MUST serve cached audio files via a predictable static URL.

#### Scenario: Audio URL format

- GIVEN a cached `.ogg` file at `static/audio/abc123.ogg`
- WHEN the system constructs the audio URL
- THEN the URL MUST be `/{static_path}/audio/{md5}.ogg` (e.g., `/static/audio/abc123.ogg`)
- AND the file MUST be accessible via FastAPI's `StaticFiles` mount

### Requirement: Configuration

The service MUST be configurable via environment variables with Pydantic Settings.

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | `""` | ElevenLabs API key (REQUIRED) |
| `ELEVENLABS_VOICE_ID` | `"21m00Tcm4TlvDq8ikWAM"` | Voice ID for TTS |
| `ELEVENLABS_MODEL` | `"eleven_multilingual_v2"` | TTS model ID |
| `ELEVENLABS_API_BASE` | `"https://api.elevenlabs.io/v1"` | API base URL |

#### Scenario: Missing API key

- GIVEN no `ELEVENLABS_API_KEY` in environment or `.env`
- WHEN the system starts
- THEN TTS generation MUST return `None` for all calls
- AND a warning MUST be logged at startup

#### Scenario: Free tier character budget

- GIVEN ElevenLabs free tier (10,000 chars/month)
- WHEN cumulative monthly TTS usage reaches 9,500 characters
- THEN the system SHOULD stop generating new audio and return `None`
- AND it MUST log a warning about the approaching limit
