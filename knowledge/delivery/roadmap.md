---
type: roadmap
updated_at: 2026-07-16
---

# Protección Inteligente 360° — Roadmap

> What we intend to build and why. Hackathon MVP con equipo de 1 persona.

## Now (Fase 1-2: Foundation + Conversational Core)

### Fase 1 — Fundación
- [ ] Repositorio y estructura del proyecto (monorepo)
- [ ] FastAPI con configuración base
- [ ] React + Vite + TailwindCSS + shadcn/ui
- [ ] SQLite + SQLAlchemy modelo de datos
- [ ] FastMCP server base
- [ ] Docker + docker-compose

### Fase 2 — Núcleo Conversacional
- [ ] Router de intenciones (nunca responde, solo clasifica)
- [ ] Conversation Hub (contexto y memoria por sesión)
- [ ] Chat UI con streaming SSE
- [ ] Agente de Créditos (máquina de estados completa)
- [ ] Agente de Seguros (máquina de estados completa)
- [ ] Sesión y memoria conversacional

## Next (Fase 3-4: Tools + PDF Elimination)

### Fase 3 — Herramientas
- [ ] Customer Tools (FastMCP)
- [ ] Credit Tools (FastMCP)
- [ ] Insurance Tools (FastMCP)
- [ ] OCR pipeline (Pillow + Tesseract)
- [ ] Notificaciones (Email/WhatsApp)
- [ ] Document Tools (upload, extract, validate)

### Fase 4 — Eliminación del PDF
- [ ] Analizar formularios oficiales de crédito y seguro
- [ ] Convertirlos a contratos JSON (Form Engine)
- [ ] Implementar Form Engine runtime
- [ ] Completado automático de campos durante conversación
- [ ] submit_application() cuando todos los campos OK

## Later (Fase 5-6: Proactive + Demo)

### Fase 5 — IA Proactiva
- [ ] Opportunity Engine (reglas, no IA generativa)
- [ ] Scheduler diario
- [ ] Reglas de elegibilidad
- [ ] Campañas simuladas por WhatsApp
- [ ] Seguimiento automático de respuestas

### Fase 6 — Demo Final
- [ ] Flujo completo: WhatsApp → oferta → conversación → simulación → solicitud → estado
- [ ] Pruebas de integración
- [ ] Pulido de UI/UX
- [ ] Documentación de la demo
- [ ] Despliegue final

## Diferencidor

La propuesta deja de ser un chatbot para convertirse en una **plataforma de agentes inteligentes**
donde la conversación es la interfaz principal. El afiliado no necesita conocer procesos internos,
descargar formularios ni navegar entre módulos. Un único asistente comprende la intención, recupera
el contexto, utiliza herramientas especializadas, completa automáticamente los formularios oficiales
y acompaña al usuario antes, durante y después del proceso. Además, el Opportunity Engine permite
que la plataforma no solo responda sino que **identifique oportunidades y contacte proactivamente**
a los afiliados.
