# Design: ElevenLabs TTS + STT for Anna (WhatsApp Voice)

## Technical Approach

Voice-as-a-layer: TTS and STT are standalone services injected into the existing chat pipeline. The chat service remains the orchestrator; voice services add optional audio to responses and optionally receive audio input. No changes to the AI tool loop, session state machine, or database.

## Architecture Decisions

### Decision: Service Pattern

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single `VoiceService` class | Couples TTS/STT; single responsibility violated | Rejected |
| Separate `TTSService` + `STTService` | Clean separation, independent testing, easy fallback | **Chosen** |
| Mixin on ChatService | Tight coupling, harder to test | Rejected |

### Decision: TTS Cache

| Option | Tradeoff | Decision |
|--------|----------|----------|
| In-memory dict | Lost on restart | Rejected |
| MD5 hash → `.mp3` file | Simple, survives restart, no DB needed | **Chosen** |
| Redis/DB | Overkill for free-tier volume | Rejected |

Files stored under `static/audio/{hash}.mp3`. Served via FastAPI `StaticFiles` at `/audio`.

### Decision: Audio Decision Engine

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Pure LLM prompt | Unpredictable, no hard guarantees | Rejected |
| Pure hard rules | No variability, robotic | Rejected |
| Prompt + post-processing | Rules guarantee safety, LLM adds context | **Chosen** |
| Prompt + rules + randomness | Natural variability, covers all cases | **Chosen** |

Post-processing applies hard NEVER rules (URLs, errors, etc.) as a safety layer AFTER LLM decides. The LLM prompt includes guidelines for when audio is appropriate; the post-processing layer enforces invariants.

### Decision: Character Budget Tracking

Simple JSON file `data/tts_budget.json` with `{ "month": "2026-07", "chars_used": 0 }`. Checked before each TTS call. Does not persist failures. Does not reset — manual reset at month boundary or when free tier resets.

### Decision: STT Endpoint

Separate `POST /chat/transcribe` endpoint that accepts `UploadFile(audio)`, returns `{ "text": "..." }`. The connector calls this endpoint when it receives an incoming audio message from WhatsApp.

## Data Flow

```
── TTS (outgoing) ───────────────────────────────────────────

  ChatService.process_message() → LLM reply (text)
       │
       ▼
  AudioDecisionEngine.should_send_audio?(reply, context)
       │
       ├─ NO  → return ChatResult(reply=text, audio_url=None)
       │
       └─ YES → TTSService.generate(reply)
                    │
                    ├─ Cache HIT → return audio_url
                    └─ Cache MISS → ElevenLabs API → save .mp3
                                      │
                                      └─ return audio_url
                  
       return ChatResult(reply=text, audio_url="/audio/hash.mp3")

── STT (incoming) ───────────────────────────────────────────

  POST /chat/transcribe (audio_file)
       │
       ▼
  STTService.transcribe(audio_bytes)
       │
       ├─ ElevenLabs Scribe → return text
       └─ Error → return None

── Connector (Reto30X_whatsapp) ─────────────────────────────

  Incoming audio webhook:
       POST /chat/transcribe (raw audio bytes)
       ← { "text": "quiero un seguro..." }
       → continue normal text flow with transcribed text

  Outgoing response:
       IF result.audio_url:
            download MP3 → send as WhatsApp audio (ptt=true)
       ELSE:
            send as text message
```

## File Changes

### Backend (Reto30X_Credit)

| File | Action | Description |
|------|--------|-------------|
| `backend/app/config.py` | Modify | Add `elevenlabs_api_key: str`, `elevenlabs_voice_id: str` |
| `backend/app/services/tts.py` | Create | `TTSService` — ElevenLabs TTS with MD5 cache |
| `backend/app/services/stt.py` | Create | `STTService` — ElevenLabs Scribe transcription |
| `backend/app/services/audio_decision.py` | Create | `AudioDecisionEngine` — rules + LLM guidance for audio |
| `backend/app/services/chat.py` | Modify | Inject TTS/STT, `ChatResult.audio_url`, post-process audio decision |
| `backend/app/routers/chat.py` | Modify | Add `POST /chat/transcribe`, extend `ChatResponse.audio_url` |
| `backend/app/main.py` | Modify | Init TTS/STT services, mount `StaticFiles("/audio")` |
| `backend/app/__init__.py` or `backend/app/services/__init__.py` | Modify | Export new service modules |
| `.env.example` | Modify | Document `ELEVENLABS_API_KEY` |
| `backend/requirements.txt` or `pyproject.toml` | Modify | Add `httpx` |

### WhatsApp Connector (Reto30X_whatsapp)

| File | Action | Description |
|------|--------|-------------|
| `src/handler.ts` or equivalent | Modify | Handle incoming audio webhook → call backend `/chat/transcribe` |
| `src/api-client.ts` | Modify | Add `transcribeAudio()`, handle `audio_url` in chat response |
| `src/types.ts` | Modify | Add audio-related types |

## Interfaces / Contracts

```python
# ── TTSService ──
class TTSService:
    def __init__(self, api_key: str, voice_id: str, static_dir: str, budget_path: str): ...
    
    async def generate(self, text: str) -> str | None:
        """Generate audio and return URL path (e.g. '/audio/abc123.mp3'), or None on failure."""
    
    def _cache_key(self, text: str) -> str: ...
    def _get_cache_path(self, md5_hash: str) -> Path: ...
    def _check_budget(self, text: str) -> bool: ...

# ── STTService ──
class STTService:
    def __init__(self, api_key: str): ...
    
    async def transcribe(self, audio_bytes: bytes) -> str | None:
        """Transcribe audio to text, or None on failure."""

# ── AudioDecisionEngine ──
class AudioDecisionEngine:
    NEVER_RULES: list[re.Pattern]  # URLs, phone numbers, emails, etc.
    STRONG_SIGNAL_THRESHOLD: int    # char count or context hints
    
    def should_send_audio(self, text: str, context: AudioContext) -> bool:
        """Apply rules + variability factor. Returns True if audio should be sent."""

# ── Extended ChatResult ──
@dataclass
class ChatResult:
    session_id: str
    reply: str
    model: str
    timestamp: datetime
    campos_actualizados: list[str]
    completitud_pct: float
    audio_url: str | None = None        # NEW

# ── Extended ChatResponse ──
class ChatResponse(BaseModel):
    reply: str
    timestamp: datetime
    session_id: str | None = None
    model: str | None = None
    campos_actualizados: list[str] = []
    completitud_pct: float = 0.0
    audio_url: str | None = None        # NEW

# ── Transcribe endpoint ──
class TranscribeResponse(BaseModel):
    text: str | None
    error: str | None = None

# ── Connector API client additions ──
interface AudioChatResponse {
  reply: string;
  audio_url?: string;   // URL to download MP3 from backend
  session_id?: string;
  model?: string;
}

interface TranscribeResponse {
  text: string | null;
  error?: string;
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `TTSService.generate()` | Mock httpx, test cache hit/miss, budget enforcement, API failure fallback |
| Unit | `STTService.transcribe()` | Mock httpx, test success/empty/error |
| Unit | `AudioDecisionEngine.should_send_audio()` | Test NEVER rules (URLs, phones), strong signals, variability boundaries, edge cases |
| Unit | Budget tracking | Test near-limit, over-limit, reset |
| Integration | `POST /chat/transcribe` | Test with real audio fixture, verify response shape |
| Integration | ChatResponse with audio | Mock TTS, verify `audio_url` in response |
| E2E | Full TTS pipeline | Process message, verify audio file created, URL returned |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. TTS/STT services are optional — if `ELEVENLABS_API_KEY` is not set, they are not initialized and the system behaves exactly as before (text-only). Enable by adding the env var.

## Open Questions

- None.
