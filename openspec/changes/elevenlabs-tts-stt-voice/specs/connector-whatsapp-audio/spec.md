# Connector WhatsApp Audio Specification

## Purpose

Extend the WhatsApp connector (Reto30X_whatsapp) to send Anna's responses as voice notes (`ptt=true`) when the backend provides an audio URL, and to forward incoming voice messages from users to the backend for STT processing.

## Requirements

### Requirement: Send Audio as Voice Note

The connector MUST send audio as a WhatsApp voice note when the backend response includes an `audio_url`.

#### Scenario: Response with audio URL

- GIVEN the backend returns `{ "reply": "...", "audio_url": "/static/audio/abc123.ogg" }`
- WHEN the connector sends the message to the user
- THEN it MUST fetch the audio from `{BACKEND_API_URL}/static/audio/abc123.ogg`
- AND send it via `sock.sendMessage(jid, { audio: { url: audioBuffer }, ptt: true })`
- AND the text reply SHOULD NOT be sent (audio is sufficient, or sent as caption if supported)

#### Scenario: Response without audio URL

- GIVEN the backend returns `{ "reply": "...", "audio_url": null }`
- WHEN the connector sends the message
- THEN it MUST send the text reply as plain text (existing behavior unchanged)

#### Scenario: Audio fetch fails

- GIVEN the backend returns `audio_url` but fetching the audio file fails (HTTP error, timeout)
- WHEN the connector attempts to send the voice note
- THEN it MUST fall back to sending the text reply as plain text
- AND it MUST log the audio fetch failure

### Requirement: Receive Incoming Audio

The connector MUST detect voice note messages and forward the audio bytes to the backend.

#### Scenario: User sends a voice note

- GIVEN an incoming WhatsApp message with `msg.message?.audioMessage` or `msg.message?.pttMessage`
- WHEN the handler processes the message
- THEN it MUST download the audio using `sock.downloadMedia(msg)`
- AND send the audio bytes to the backend chat endpoint (via multipart or base64-encoded field)
- AND mark the message as read

#### Scenario: Audio download fails

- GIVEN an incoming voice note where `sock.downloadMedia(msg)` throws
- WHEN the connector processes the event
- THEN it MUST send a text reply asking the user to try again or type their message
- AND it MUST log the download error

### Requirement: Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_API_URL` | `"http://localhost:8000"` | Existing — backend base URL |

No new connector-level config variables are required. Audio behavior is driven by the presence/absence of `audio_url` in the backend response.
