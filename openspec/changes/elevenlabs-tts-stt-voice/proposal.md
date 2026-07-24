# Proposal: ElevenLabs TTS + STT para Anna (WhatsApp Voice)

## Intent
Incorporar voz al asistente Anna: convertir respuestas de texto a audio (TTS) usando ElevenLabs, y transcribir audios entrantes del usuario (STT) usando ElevenLabs Scribe. La voz se entrega como nota de WhatsApp (`ptt=true`) con volumen bajo (<10K chars/mes, free tier alcanza).

## Business Problem
El asistente Anna hoy solo responde por texto en WhatsApp. La voz aporta cercanía, confianza y una experiencia más natural — especialmente para clientes que prefieren hablar antes que escribir.

## Scope
- **Backend** (Reto30X_Credit): servicio TTS, servicio STT, caché de audio, endpoints, integración con chat
- **Connector** (Reto30X_whatsapp): enviar audio como nota de voz, reenviar audio entrante al backend
- **No incluye**: limpieza de audios viejos (bajo volumen no lo requiere), UI web, historial de audios

## Approach

### TTS Decision System (key differentiator)
Anna NO responde con audio el 100% del tiempo. Es un sistema híbrido con variabilidad:

1. **HARD NEVER rules** → siempre texto: URLs, teléfonos, emails, confirmaciones cortas, errores
2. **STRONG SIGNALS** → alta probabilidad de audio: saludo inicial a cliente potencial, cliente preguntó por un seguro específico, cliente envió audio, respuesta informativa >200 chars
3. **VARIABILITY FACTOR** → mismo texto no siempre produce audio (randomness controlado, ~60-70% en casos borderline)
4. **Anna decide** → el prompt del LLM incluye instrucciones para decidir cuándo usar audio según contexto

### Stack
- ElevenLabs voice ID: `21m00Tcm4TlvDq8ikWAM` (Rachel)
- Model: `eleven_multilingual_v2`
- STT: ElevenLabs Scribe v1
- Caché: MD5 hash del texto → archivo .ogg, expiración no necesaria por bajo volumen
- Fallback: si ElevenLabs falla → responde solo texto, nunca bloquea

### Architecture Sketch
```
WhatsApp ← audio → Connector ← audio_bytes → Backend STT → texto → Chat LLM
WhatsApp ← ptt.mp3 ← Connector ← audio_url ← Backend TTS ← texto ← Chat LLM
```

### Idiomas
100% español. ElevenLabs configurado en español.

### Compliance
Sin restricciones — se usa ElevenLabs bajo ToS estándar.

## Key Decisions
| Decision | Choice |
|---|---|
| Dónde transcribir (STT) | En el backend (unificado) |
| Idioma | 100% español |
| Cacheo | MD5 hash → archivo .ogg |
| Fallback | Texto plano si ElevenLabs falla |
| Variabilidad audio | Reglas + random factor, no 100% |
