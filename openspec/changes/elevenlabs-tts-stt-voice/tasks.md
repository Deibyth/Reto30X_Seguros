# Tasks: ElevenLabs TTS + STT for Anna (WhatsApp Voice)

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend services + endpoint + chat integration | Single PR | `pytest tests/ -k "tts or stt or audio" -v` | Start backend, `curl POST /chat` with mock TTS | Revert `backend/` changes, remove `httpx` dep |
| 2 | WhatsApp connector audio | Single PR (same PR) | `npm test` in connector repo | Run connector with backend test server | Revert connector files |

## Phase 1: Foundation / Config

- [x] 1.1 Add `elevenlabs_api_key`, `elevenlabs_voice_id` to `backend/app/config.py` (from env, optional)
- [x] 1.2 Add `httpx` to `backend/pyproject.toml` or `requirements.txt`
- [x] 1.3 Create `backend/static/audio/` dir with `.gitkeep`
- [x] 1.4 Create `backend/data/tts_budget.json` with `{"month": "2026-07", "chars_used": 0}`

## Phase 2: TTS Service

- [x] 2.1 Create `backend/app/services/tts.py` — `TTSService` class with `generate(text) -> str | None`

## Phase 3: STT Service

- [x] 3.1 Create `backend/app/services/stt.py` — `STTService` class with `transcribe(audio_bytes) -> str | None`

## Phase 4: Audio Decision Engine

- [x] 4.1 Create `backend/app/services/audio_decision.py`

## Phase 5: Chat Integration

- [x] 5.1 Add `audio_url: str | None = None` to `ChatResult` dataclass in `services/chat.py`
- [x] 5.2 Add voice prompt fragment to system prompt
- [x] 5.3 In `process_message()`, TTS post-processing via `_add_audio_to_result()`
- [x] 5.4 Pass `user_sent_audio` context through `process_message()`

## Phase 6: Endpoint + Router

- [x] 6.1 Add `audio_url: str | None = None` to `ChatResponse` in `routers/chat.py`
- [x] 6.2 Add `POST /chat/transcribe` endpoint
- [x] 6.3 Mount `StaticFiles(directory="static/audio")` at `/audio` in `main.py`
- [x] 6.4 Init TTS/STT in lifespan (only if `elevenlabs_api_key` is set)

## Phase 7: Testing

- [x] 7.1 Test `TTSService`: cache hit, cache miss, budget exhausted, API failure → None
- [x] 7.2 Test `STTService`: success, empty audio, API error → None
- [x] 7.3 Test `AudioDecisionEngine`: NEVER rules, strong signals, variability
- [x] 7.4 Test `POST /chat` returns `audio_url: None` when no key set
- [x] 7.5 Test `POST /chat/transcribe` with mock audio file
- [x] 7.6 Test budget tracking: near-limit allows, over-limit blocks

## Phase 8: WhatsApp Connector

- [x] 8.1 Add `transcribeAudio(audioBytes)` to connector's API client
- [x] 8.2 Handle incoming audio webhook → call transcribe → text
- [x] 8.3 Handle outgoing audio: fetch MP3 → send as WhatsApp ptt=true
- [x] 8.4 Fallback: if audio fetch fails, send as text
