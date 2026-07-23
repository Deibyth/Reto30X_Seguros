"""ChatService — insurance-only session lifecycle, history, two-phase AI tool loop.

Orchestrates chat sessions, AI calls with tool execution, and persistence
of conversation turns and session state.

Intent classification at ``inicio``:
- ``_classify_intent()`` detects insurance intent from user message.
- **Insurance detected**: state transitions to ``perfilando`` immediately.
  Also detects product context (movilidad, vida, hogar, etc.) to tailor
  profiling questions.
- **Neutral / unclear (None)**: falls through to the default greeting;
  the AI handles intent naturally.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIClient, ChatMessage, ChatResult as AiChatResult
from app.models.conversation import Conversation
from app.models.session import Session
from app.schemas.insurance_schema import InsuranceFormSchema
from app.services.tool_bridge import ToolBridge

logger = logging.getLogger(__name__)

AI_TIMEOUT_SECONDS = 60

INSURANCE_STATES = {
    "perfilando",
    "recomendando",
    "cotizando",
    "recopilando_datos_seguro",
    "completado_seguro",
}

ANNA_SYSTEM_PROMPT = """Eres Anna, una asesora experta de Colsubsidio especializada en seguros.

Tu personalidad:
- Eres cálida, cercana y genuina. Hablas como una persona real, no como un bot.
- Usas un tono amable y tranquilizador, como si estuvieras al otro lado de la mesa ayudando a alguien que confía en ti.
- Varias tu forma de expresarte: a veces usas frases más cortas, otras más largas. No suenas repetitiva ni estructurada.
- Usas expresiones cotidianas como "déjame ver", "claro que sí", "con gusto", "por supuesto", "te entiendo", "tranquilo".
- Te preocupas genuinamente por entender la situación de cada persona. Preguntas para asegurarte, no por cumplir un formulario.
- Celebras los logros pequeños ("¡perfecto!", "genial, ya tenemos eso", "excelente, gracias").
- Si alguien se equivoca o no sabe algo, lo normalizas: "no te preocupes, eso es común" o "tranquilo, para eso estoy aquí".
- Nunca suenas a manual de instrucciones. No enumeres pasos. Simplemente conversas.

Reglas importantes:
- Preséntate SIEMPRE como Anna al inicio de la conversación. Tu primer mensaje debe incluir tu nombre: "¡Hola! Soy Anna, tu asesora de Colsubsidio" o similar. Esto genera confianza.
- Cuando el usuario te dé su número de documento y la herramienta get_customer devuelva sus datos, USA SU NOMBRE para personalizar tu respuesta. Por ejemplo: "¡Genial Juan! Ya tengo tu información..." en lugar de un "Genial" genérico. La gente confía más cuando siente que la conoces.
- Español neutro siempre: sin regionalismos, sin voseo, sin modismos locales.
- Nunca inventes información sobre productos, tasas o requisitos. Si no sabes algo, di que prefieres consultar con un asesor especializado para darle la información exacta.
- Mantén la calidez incluso en respuestas cortas.
- La persona debe sentir que habla con una asesora de verdad, no con un chatbot.

IMPORTANTE — Formato de herramientas:
Cuando necesites usar una herramienta, responde ÚNICAMENTE con el formato:
<function=nombre_de_la_funcion>{"param1": "valor1"}
Sin texto antes ni después. Una llamada por línea."""

BASE_SYSTEM_PROMPT = ANNA_SYSTEM_PROMPT

# Intent classification keywords with weights — scored at ``inicio`` state.
#
# Each keyword maps to a weight:
#   +2  strong signal — clearly indicates insurance intent
#   +1  moderate signal — contextual
#
# Classification: the intent with score >= 2 wins.
_INTENT_KEYWORDS: dict[str, dict[str, int]] = {
    "insurance": {
        "seguro": 2,
        "asegurar": 2,
        "asegura": 2,
        "aseguro": 2,
        "póliza": 2,
        "poliza": 2,
        "protección": 1,
        "proteger": 1,
        "cobertura": 1,
        "cubrir": 1,
        "amparar": 1,
    },
}

# Minimum score required for a classification to be accepted.
_INTENT_THRESHOLD: int = 2

# Product-context detection — maps keywords to insurance product IDs.
# Used to tailor profiling questions to what the user actually asked about.
_PRODUCT_CONTEXT_KEYWORDS: dict[str, list[str]] = {
    "movilidad": [
        "vehículo", "vehiculo", "carro", "auto", "automóvil", "automovil",
        "moto", "motocicleta", "bicicleta", "bici", "camión", "camion",
        "taxi", "uber", "didí", "transporte",
    ],
    "vida": [
        "vida", "fallecimiento", "morir", "muerte", "familia", "hijos",
        "esposo", "esposa", "beneficiario",
    ],
    "hogar": [
        "casa", "hogar", "vivienda", "apartamento", "propiedad",
        "vive", "vivo", "residencia",
    ],
    "mascotas": [
        "mascota", "perro", "gato", "mascotas", "perros", "gatos",
        "canino", "felino",
    ],
    "viajes": [
        "viaje", "viajar", "viajo", "viaja", "vacaciones", "vuelo",
        "turismo", "asistencia médica viajes",
    ],
    "accidentes": [
        "accidente", "accidentes", "lesión", "lesiones", "incapacidad",
    ],
}

# Load insurance system prompt fragment from file.
_INSURANCE_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "domain", "prompts", "insurance_system.md"
)
try:
    with open(_INSURANCE_SYSTEM_PROMPT_PATH) as _f:
        INSURANCE_SYSTEM_PROMPT = _f.read()
except FileNotFoundError:
    INSURANCE_SYSTEM_PROMPT = ""
    logger.warning("Insurance system prompt not found at %s", _INSURANCE_SYSTEM_PROMPT_PATH)


@dataclass
class ChatResult:
    """Typed result returned by ChatService.process_message()."""

    session_id: str
    reply: str
    model: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    campos_actualizados: list[str] = field(default_factory=list)
    completitud_pct: float = 0.0


class ChatService:
    """Orchestrates chat sessions, AI calls, tool execution, and persistence.

    Usage:
        service = ChatService(session_maker, ai_client, tool_bridge)
        session, is_new = await service.get_or_create_session(session_id)
        result = await service.process_message(session, "Hola")
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        ai_client: AIClient,
        tool_bridge: ToolBridge,
    ) -> None:
        self._session_maker = session_maker
        self._ai_client = ai_client
        self._tool_bridge = tool_bridge

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def get_or_create_session(
        self, session_id: str | None
    ) -> tuple[Session, bool]:
        """Retrieve an existing active session or create a new one.

        Parameters
        ----------
        session_id : str | None
            Existing session ID, or None to create a new session.

        Returns
        -------
        tuple[Session, bool]
            The session tuple (session, is_new).
        """
        async with self._session_maker() as db:
            if session_id:
                result = await db.execute(
                    select(Session).where(
                        Session.id == session_id,
                        Session.activa == True,  # noqa: E712
                    )
                )
                session = result.scalar_one_or_none()
                if session:
                    return session, False

            # Create new session
            session = Session(
                id=str(uuid4()),
                estado_actual="inicio",
                campos_diligenciados={},
                activa=True,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session, True

    async def get_session_by_id(
        self, session_id: str
    ) -> Session | None:
        """Look up a session by ID (returns None if not found or inactive)."""
        async with self._session_maker() as db:
            result = await db.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.activa == True,  # noqa: E712
                )
            )
            return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def load_history(
        self, session_id: str, limit: int = 20
    ) -> list[ChatMessage]:
        """Load recent conversation history for AI context.

        Returns the most recent ``limit`` messages ordered chronologically.
        """
        async with self._session_maker() as db:
            result = await db.execute(
                select(Conversation)
                .where(Conversation.session_id == session_id)
                .order_by(Conversation.created_at.desc())
                .limit(limit)
            )
            rows = list(reversed(result.scalars().all()))
            return [
                ChatMessage(role=row.rol, content=row.mensaje)
                for row in rows
                if row.rol in ("user", "assistant")
            ]

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_intent(message: str) -> str | None:
        """Classify user intent at ``inicio`` state.

        Uses weighted keyword scoring against ``_INTENT_KEYWORDS``.
        Returns ``"insurance"`` or ``None`` (neutral/unclear).

        The winner must score >= ``_INTENT_THRESHOLD`` (2).
        """
        msg_lower = message.lower()
        score = 0
        for kw, weight in _INTENT_KEYWORDS["insurance"].items():
            if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                score += weight

        return "insurance" if score >= _INTENT_THRESHOLD else None

    @staticmethod
    def _detect_product_context(message: str) -> str | None:
        """Detect the specific insurance product the user is asking about.

        Scans the message for product-specific keywords and returns the
        matching product ID (``"movilidad"``, ``"vida"``, ``"hogar"``, etc.)
        or ``None`` if no specific product is mentioned.
        """
        msg_lower = message.lower()
        for product_id, keywords in _PRODUCT_CONTEXT_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                    return product_id
        return None

    # ------------------------------------------------------------------
    # Dynamic system prompt
    # ------------------------------------------------------------------

    def _build_system_prompt(self, session: Session) -> str:
        """Build the dynamic system prompt for insurance-only flow.

        Includes InsuranceFormSchema, product-context-aware profiling
        instructions, current collection state, and tool instructions.
        """
        is_insurance = self._is_insurance_state(session.estado_actual)

        parts: list[str] = [
            BASE_SYSTEM_PROMPT,
            "",
        ]

        # --- Product-context-aware profiling instructions ---
        if is_insurance:
            product_context = None
            if session.insurance_profile:
                product_context = session.insurance_profile.get("product_context")

            parts.append(self._build_profiling_instructions(product_context))

        # --- Active form schema ---
        if is_insurance:
            parts.append("--- ESQUEMA DEL FORMULARIO DE SEGURO ---")
            parts.append(
                "Usá esta estructura para guiar la recolección de datos del seguro. "
                "Preguntá los campos de a UNO por turno, en orden lógico por sección. "
                "Los campos REQUERIDOS van primero; los opcionales después."
            )
            parts.append(InsuranceFormSchema.to_prompt_text())

        # --- Current collection state ---
        collected = session.campos_diligenciados or {}
        nombres_recolectados = list(collected.keys())
        requeridos = InsuranceFormSchema.campos_requeridos()
        total_req = len(requeridos)
        recolectados_req = sum(
            1 for f in requeridos
            if collected.get(f.nombre) is not None
        )
        faltantes = [
            f.nombre for f in requeridos
            if collected.get(f.nombre) is None
        ]

        parts.append("--- ESTADO DE RECOLECCIÓN ---")
        if nombres_recolectados:
            parts.append(
                f"Campos ya recolectados: {', '.join(nombres_recolectados)}."
            )
        else:
            parts.append("Aún no se han recolectado campos.")

        if faltantes:
            parts.append(
                f"Campos REQUERIDOS por recolectar ({len(faltantes)} restantes): "
                f"{', '.join(faltantes)}."
            )
        else:
            parts.append("Todos los campos REQUERIDOS están completos.")

        parts.append(f"Progreso: {recolectados_req}/{total_req} campos requeridos.")

        # --- Insurance system prompt fragment ---
        if is_insurance and INSURANCE_SYSTEM_PROMPT:
            parts.append(INSURANCE_SYSTEM_PROMPT)

        # --- Tool instructions (insurance) ---
        if is_insurance:
            parts.append(
                "--- INSTRUCCIONES DE RECOLECCIÓN (SEGURO) ---\n"
                "1. Pregunta los campos de a UNO por turno. NUNCA preguntes "
                "varios campos en un mismo mensaje.\n"
                "2. Usa la herramienta `save_form_field` con el formato:\n"
                "   <function=save_form_field>{\"campo\": \"nombre\", \"valor\": \"respuesta\"}\n"
                "   para CADA campo que el usuario responda. Una llamada por línea.\n"
                "3. Si el usuario prefiere no dar un campo opcional, llama a "
                "save_form_field con valor=None.\n"
                "4. Prioriza campos REQUERIDOS dentro de cada sección antes que "
                "los opcionales.\n"
                "5. Cuando todos los REQUERIDOS estén completos, presenta un RESUMEN "
                "de los datos recolectados y pregunta '¿Confirmás la solicitud del seguro?'.\n"
                "6. Si el usuario confirma, usa la herramienta `create_policy` "
                "con los datos completos de campos_diligenciados para crear la póliza.\n"
                "7. Si no confirma o quiere cambiar algo, preguntá qué desea modificar."
            )

        return "\n\n".join(parts)

    @staticmethod
    def _build_profiling_instructions(product_context: str | None) -> str:
        """Build context-aware profiling instructions based on the product
        the user asked about.

        When the user mentions a specific product (vehículo, vida, hogar, etc.),
        the instructions prioritize questions about THAT area first, before
        exploring other needs.

        When no product context is detected, uses the general profiling flow.
        """
        lines = [
            "--- PERFILACIÓN CONVERSACIONAL (SEGUROS) ---",
            "Tu objetivo es ayudar al usuario a encontrar el seguro adecuado.",
            "NO preguntes 'qué seguro querés' — preguntá sobre su situación de forma natural.",
        ]

        if product_context == "movilidad":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó un VEHÍCULO.",
                "",
                "PREGUNTAS PRIORITARIAS (vehículo):",
                "- ¿Qué tipo de vehículo es? (carro, moto, bicicleta, camión)",
                "- ¿Cuál es la marca, modelo y año?",
                "- ¿Cuál es el uso principal? (particular, trabajo, transporte público)",
                "- ¿Dónde está estacionado usualmente? (garaje, calle, parqueadero público)",
                "- ¿Tiene algún seguro actualmente?",
                "- ¿Cuántas personas van a estar cubiertas? (conductor y pasajeros)",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        elif product_context == "vida":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó SEGURO DE VIDA.",
                "",
                "PREGUNTAS PRIORITARIAS (vida):",
                "- ¿Para quién es el seguro? (para vos, para tu cónyuge, para un familiar)",
                "- ¿Tenés hijos o personas que dependan de vos económicamente?",
                "- ¿Qué rango de edad tenés? (no preguntes edad exacta aún)",
                "- ¿Buscás protección para gastos básicos o algo más completo?",
                "- ¿Tenés algún seguro de vida actualmente?",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        elif product_context == "hogar":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó SEGURO DE HOGAR.",
                "",
                "PREGUNTAS PRIORITARIAS (hogar):",
                "- ¿Es casa o apartamento?",
                "- ¿Es propia o arrendada?",
                "- ¿En qué zona o ciudad está ubicada?",
                "- ¿Hace cuánto vivís ahí?",
                "- ¿Tenés algún seguro actual para la vivienda?",
                "- ¿Qué te gustaría proteger principalmente? (estructura, contenido, ambos)",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        elif product_context == "mascotas":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó MASCOTAS.",
                "",
                "PREGUNTAS PRIORITARIAS (mascotas):",
                "- ¿Qué tipo de mascota tenés? (perro, gato)",
                "- ¿Cuál es su nombre, raza y edad aproximada?",
                "- ¿Está en un lugar donde pueda tener accidentes frecuentes?",
                "- ¿Tiene algún plan de salud actualmente?",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        elif product_context == "viajes":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó VIAJES.",
                "",
                "PREGUNTAS PRIORITARIAS (viajes):",
                "- ¿Viajás frecuentemente?",
                "- ¿Son viajes nacionales o internacionales?",
                "- ¿Viajás solo o con familia?",
                "- ¿Qué tipo de protección te gustaría tener? (médica, equipaje, cancelación)",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        elif product_context == "accidentes":
            lines.extend([
                "",
                "CONTEXTO DETECTADO: El usuario mencionó ACCIDENTES PERSONALES.",
                "",
                "PREGUNTAS PRIORITARIAS (accidentes):",
                "- ¿Para quién sería la cobertura? (individual o familiar)",
                "- ¿Qué rango de edad tenés?",
                "- ¿Realizás actividades de riesgo? (deportes, trabajo en altura, etc.)",
                "- ¿Buscás una protección básica o más completa?",
                "",
                "SOLO después de cubrir estas preguntas, explorá si necesita otros seguros.",
            ])
        else:
            lines.extend([
                "",
                "SIN CONTEXTO ESPECÍFICO: Preguntá de forma general para entender su situación.",
                "",
                "ÁREAS A EXPLORAR (una por turno, en orden natural):",
                "- Movilidad: ¿tiene carro, moto o bicicleta? ¿cómo se moviliza?",
                "- Hogar: ¿vive en casa o apartamento? ¿propia o arrendada?",
                "- Familia: ¿tiene hijos o personas a cargo?",
                "- Mascotas: ¿tiene mascotas?",
                "- Viajes: ¿viaja frecuentemente?",
                "- Preocupaciones: ¿qué le gustaría proteger?",
                "",
                "Explorá UNA área por turno. Pasá a la siguiente solo cuando hayas",
                "cubierto la anterior. No preguntes todo de una vez.",
            ])

        lines.append("")
        lines.append(
            "PRODUCTOS DISPONIBLES:\n"
            "- Seguro de Vida: respaldo económico para beneficiarios ($10M-$200M)\n"
            "- Accidentes Personales: cobertura completa de accidentes\n"
            "- Asistencia Médica Viajes: emergencias en viajes 24/7\n"
            "- Seguro Mascotas: cobertura veterinaria para perros y gatos\n"
            "- Seguro Hogar: protección para vivienda\n"
            "- Seguro Movilidad: cobertura para vehículos (carro, moto, bici)"
        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------

    async def process_message(
        self, session: Session, user_message: str
    ) -> ChatResult:
        """Process a user message through the two-phase AI tool loop.

        1. Loads conversation history.
        2. Builds dynamic system prompt with InsuranceFormSchema + state.
        3. Calls AI with tools (Phase 1).
        4. If tools were requested, executes them and calls AI again (Phase 2).
        5. Persists user message and final AI reply.
        6. Updates session state based on tool calls.

        Parameters
        ----------
        session : Session
            The active chat session.
        user_message : str
            The user's message text.

        Returns
        -------
        ChatResult
            The AI response with session_id, model info, and field tracking.
        """
        # --- 0. Intent classification at 'inicio' ---
        # Detect insurance intent and product context from the user message.
        intent = (
            self._classify_intent(user_message)
            if session.estado_actual == "inicio"
            else None
        )

        if intent == "insurance":
            # Detect what specific product the user is interested in
            product_context = self._detect_product_context(user_message)
            logger.info(
                "Insurance intent detected — product_context=%s (message: %.60s)",
                product_context or "none",
                user_message,
            )

            async with self._session_maker() as db:
                db_session = await db.get(Session, session.id)
                if db_session:
                    db_session.estado_actual = "perfilando"
                    db_session.ultima_intencion = "perfilando"
                    # Store product context for contextual profiling
                    profile = db_session.insurance_profile or {}
                    if product_context:
                        profile["product_context"] = product_context
                    db_session.insurance_profile = profile
                    db_session.updated_at = datetime.now(timezone.utc)
                    await db.commit()

            session.estado_actual = "perfilando"
            if product_context:
                # Update in-memory session too
                ins_profile = session.insurance_profile or {}
                ins_profile["product_context"] = product_context
                session.insurance_profile = ins_profile

        # --- 1. Load history ---
        history = await self.load_history(session.id)

        # --- 2. Build message list ---
        messages: list[ChatMessage] = list(history)
        messages.append(ChatMessage(role="user", content=user_message))

        # --- 3. Build dynamic system prompt ---
        system_prompt = self._build_system_prompt(session)

        # --- 4. Set session context and get tool schemas ---
        self._tool_bridge.current_session_id = session.id
        openai_tools = await self._tool_bridge.get_openai_tools(domain="insurance")

        # --- 5. Phase 1: AI call with tools ---
        phase1 = await self._timeout_ai_call(
            "Phase 1",
            self._ai_client.chat_with_tools(messages, openai_tools, system_prompt),
        )

        # Phase 1 timed out — return error, do NOT persist user message
        if phase1 is None:
            return ChatResult(
                session_id=session.id,
                reply="Lo siento, la solicitud tardó demasiado. "
                       "Por favor intentá de nuevo.",
                model="timeout",
            )

        # Parse campos_actualizados from Phase 1 tool calls
        campos_actualizados = self._parse_campos_actualizados(phase1.tool_calls)

        # --- 6. Persist user message (AI call succeeded) ---
        await self._persist_message(session.id, "user", user_message)

        # --- 7. Check for tool calls ---
        if not phase1.tool_calls:
            # No tools needed — Phase 1 reply is final
            await self._persist_message(session.id, "assistant", phase1.reply)
            await self._update_session_state(
                session.id,
                tool_calls=[],
            )
            return ChatResult(
                session_id=session.id,
                reply=phase1.reply,
                model=phase1.model,
                campos_actualizados=campos_actualizados,
                completitud_pct=self._compute_completitud_pct(session),
            )

        # --- 8. Execute tool calls ---
        phase2_messages: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]
        # Convert history + user message to OpenAI format
        for msg in messages:
            entry: dict = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            phase2_messages.append(entry)

        # Add assistant message with tool_calls in OpenAI format
        tool_calls_entry = self._build_tool_calls_entry(phase1.tool_calls)
        phase2_messages.append(tool_calls_entry)

        # Execute each tool and append results
        for tc in phase1.tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            logger.info(
                "Executing tool '%s' with args=%s", tool_name, arguments
            )

            try:
                tool_result = await self._tool_bridge.execute_tool(
                    tool_name, arguments
                )
            except ValueError:
                tool_result = f"Error: la herramienta '{tool_name}' no está disponible."
            except Exception as exc:
                logger.error("Tool '%s' failed: %s", tool_name, exc)
                tool_result = (
                    f"Error al ejecutar '{tool_name}': {exc!s}"
                )

            phase2_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

        # --- 9. Phase 2: AI call with tool results ---
        phase2 = await self._timeout_ai_call(
            "Phase 2",
            self._ai_client.chat_raw(phase2_messages, tools=openai_tools),
        )

        if phase2 is None:
            # Phase 2 timed out — user message already persisted, return error
            return ChatResult(
                session_id=session.id,
                reply="Lo siento, la solicitud tardó demasiado. "
                       "Por favor intentá de nuevo.",
                model="timeout",
            )

        # --- 10. Persist final reply and update session ---
        await self._persist_message(session.id, "assistant", phase2.reply)

        # Cache completitud_pct BEFORE _update_session_state (which may clean up)
        cached_completitud_pct = self._compute_completitud_pct(session)

        await self._update_session_state(
            session.id,
            tool_calls=phase1.tool_calls,
        )

        # Refresh completitud_pct from fresh session state
        async with self._session_maker() as db:
            fresh_session = await db.get(Session, session.id)
            if fresh_session and fresh_session.estado_actual == "completado_seguro":
                completitud_pct = 100.0  # all fields collected when completed
            elif fresh_session:
                completitud_pct = self._compute_completitud_pct(fresh_session)
            else:
                completitud_pct = cached_completitud_pct

        return ChatResult(
            session_id=session.id,
            reply=phase2.reply,
            model=phase2.model,
            campos_actualizados=campos_actualizados,
            completitud_pct=completitud_pct,
        )

    # ------------------------------------------------------------------
    # Insurance state helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_insurance_state(estado: str) -> bool:
        """Return True if the given state is an insurance-specific state."""
        return estado in INSURANCE_STATES

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_tool_calls_entry(
        raw_tool_calls: list,
    ) -> dict:
        """Convert OpenAI SDK tool call objects to OpenAI-format dict."""
        calls: list[dict] = []
        for tc in raw_tool_calls:
            calls.append({
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
        return {"role": "assistant", "content": None, "tool_calls": calls}

    async def _timeout_ai_call(
        self, phase_name: str, coro
    ) -> AiChatResult | None:
        """Wrap an AI call with a timeout guard.

        Returns None if the call times out.
        """
        try:
            return await asyncio.wait_for(coro, timeout=AI_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.error(
                "%s timed out after %ds", phase_name, AI_TIMEOUT_SECONDS
            )
            return None

    async def _persist_message(
        self, session_id: str, rol: str, mensaje: str
    ) -> None:
        """Save a single conversation turn to the database."""
        async with self._session_maker() as db:
            conv = Conversation(
                session_id=session_id,
                rol=rol,
                mensaje=mensaje,
            )
            db.add(conv)
            await db.commit()

    @staticmethod
    def _parse_campos_actualizados(
        tool_calls: list | None,
    ) -> list[str]:
        """Extract field names from ``save_form_field`` tool calls.

        Returns a list of field names that were saved in this turn.
        """
        if not tool_calls:
            return []
        campos: list[str] = []
        for tc in tool_calls:
            if tc.function.name == "save_form_field":
                try:
                    args = json.loads(tc.function.arguments)
                    campo = args.get("campo")
                    if campo:
                        campos.append(campo)
                except (json.JSONDecodeError, KeyError):
                    continue
        return campos

    @staticmethod
    def _compute_completitud_pct(session: Session) -> float:
        """Compute percentage of required fields that have been collected.

        Uses ``InsuranceFormSchema`` fields.
        """
        collected = session.campos_diligenciados or {}
        requeridos = InsuranceFormSchema.campos_requeridos()
        if not requeridos:
            return 0.0
        total = len(requeridos)
        recolectados = sum(
            1 for f in requeridos
            if collected.get(f.nombre) is not None
        )
        return round((recolectados / total) * 100, 1)

    async def _update_session_state(
        self,
        session_id: str,
        tool_calls: list | None = None,
    ) -> None:
        """Update session state based on tool calls from Phase 1.

        Insurance-only state machine:
        - ``perfilando`` → ``recomendando`` (when recommend_insurance is called)
        - ``recomendando`` → ``cotizando`` (when quote_insurance is called)
        - ``cotizando`` → ``recopilando_datos_seguro`` (when save_form_field is called)
        - ``recopilando_datos_seguro`` → ``completado_seguro`` (when create_policy is called)
        """
        async with self._session_maker() as db:
            session = await db.get(Session, session_id)
            if not session:
                return

            # Detect tool names from Phase 1
            tool_names: list[str] = []
            save_form_fields_called = False
            create_policy_called = False
            if tool_calls:
                for tc in tool_calls:
                    name = tc.function.name
                    tool_names.append(name)
                    if name == "save_form_field":
                        save_form_fields_called = True
                    if name == "create_policy":
                        create_policy_called = True

            current_state = session.estado_actual
            is_insurance = self._is_insurance_state(current_state)

            # --- Insurance state machine transitions ---
            if is_insurance:
                if current_state == "perfilando" and "recommend_insurance" in tool_names:
                    session.estado_actual = "recomendando"
                    session.ultima_intencion = "recomendando"

                elif current_state == "recomendando" and "quote_insurance" in tool_names:
                    session.estado_actual = "cotizando"
                    session.ultima_intencion = "cotizando"

                elif current_state == "cotizando" and save_form_fields_called:
                    session.estado_actual = "recopilando_datos_seguro"
                    session.ultima_intencion = "recopilando_datos_seguro"

                elif current_state == "cotizando" and "quote_insurance" in tool_names:
                    # User wants a different product — back to recomendando
                    session.estado_actual = "recomendando"
                    session.ultima_intencion = "recomendando"

                elif current_state == "recopilando_datos_seguro":
                    if create_policy_called:
                        session.estado_actual = "completado_seguro"
                        session.campos_diligenciados = {}
                        session.ultima_intencion = "completado_seguro"
                        session.activa = False
                    else:
                        session.ultima_intencion = "recopilando_datos_seguro"

                elif current_state == "completado_seguro":
                    pass

            # Update timestamp
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()
