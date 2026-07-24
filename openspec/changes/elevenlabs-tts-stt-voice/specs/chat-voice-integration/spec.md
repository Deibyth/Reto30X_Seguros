# Chat Voice Integration Specification

## Purpose

Define how Anna decides when to respond with audio, how the chat service integrates TTS/STT, and how the response payload carries audio information to the WhatsApp connector.

## Requirements

### Requirement: TTS Decision Rules

Anna MUST follow a decision system with three layers to determine when to include audio:

1. **HARD NEVER rules** (always text-only — no audio even if generated):
   - Message contains a URL, phone number, email, or user address
   - Message is a short confirmation (<100 chars, e.g., "Listo", "Gracias")
   - Message is an error or fallback ("Lo siento, no pude procesar...")
   - The system is in a state that requires user data collection (perfilando, recopilando_datos_seguro)

2. **STRONG SIGNALS** (high probability, audio SHOULD be generated):
   - First greeting to a new potential client
   - User explicitly asked about a specific insurance product
   - User sent an audio message (mirroring the channel)
   - Informative response >200 characters explaining a product

3. **VARIABILITY FACTOR**: For messages matching neither rule set, the system SHOULD decide probabilistically (~60-70% audio) to avoid predictability.

#### Scenario: Hard NEVER rule triggered

- GIVEN Anna's reply contains a phone number ("Llámame al 3001234567")
- WHEN the system evaluates whether to generate audio
- THEN `should_generate_audio(reply, context)` returns `False`

#### Scenario: Strong signal with audio

- GIVEN a new user says "Hola" and Anna greets them with "¡Hola! Soy Anna, tu asesora de Colsubsidio"
- WHEN the system evaluates
- THEN `should_generate_audio(reply, context)` returns `True`

#### Scenario: Variability factor applied

- GIVEN an informative reply that matches no hard rules or strong signals
- WHEN the system evaluates
- THEN it uses a random factor seeded per-session to decide ~60-70% of the time

### Requirement: System Prompt Extension

The LLM system prompt MUST be extended to instruct Anna about audio decisions.

#### Scenario: Audio instructions in prompt

- GIVEN the chat service builds the system prompt
- WHEN Anna is about to respond
- THEN the prompt MUST include an instruction explaining that Anna can choose to respond with voice notes for warmer responses, but MUST NOT use voice for URLs, phone numbers, emails, or confirmations

### Requirement: Chat Response Envelope

The `ChatResult` and `ChatResponse` models MUST include an optional `audio_url` field.

#### Scenario: Response with audio

- GIVEN a chat reply that triggered audio generation
- WHEN the chat service returns `ChatResult`
- THEN `audio_url` MUST contain the path to the cached `.ogg` file (e.g., `/static/audio/abc123.ogg`)

#### Scenario: Response without audio

- GIVEN a chat reply that did not trigger audio (hard rule or LLM chose text)
- WHEN the chat service returns `ChatResult`
- THEN `audio_url` MUST be `None`

### Requirement: User Audio Input Handling

The chat endpoint MUST accept an optional audio message alongside or instead of text.

#### Scenario: Audio received as input

- GIVEN the POST /chat receives audio bytes (not text) or both text and audio
- WHEN the chat service processes the request
- THEN it MUST transcribe the audio via STT service
- AND use the transcribed text as the `user_message`
- AND if both text and audio exist, prefer the audio transcription

#### Scenario: STT transcription fails

- GIVEN audio input that returns `None` from STT
- WHEN the chat service processes the message
- THEN it MUST return a response asking the user to write their message instead

### Requirement: Fallback

The voice integration MUST NOT block the chat flow under any circumstances.

#### Scenario: ElevenLabs service unavailable

- GIVEN ElevenLabs API is unreachable during TTS generation
- WHEN the chat service processes a message
- THEN the reply MUST be returned as text-only with `audio_url: None`
- AND the chat flow completes normally
