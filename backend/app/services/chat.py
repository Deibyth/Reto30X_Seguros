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
from app.services.audio_decision import AudioContext, AudioDecisionEngine
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

SALUDO INICIAL — Cuando sea el PRIMER mensaje de la conversación (estado "inicio"), saluda EXACTAMENTE así:
"¡Hola! Qué gusto saludarte. Soy Anna, tu asesora de Colsubsidio. Estoy aquí para ayudarte a encontrar la protección que necesitas. ¿En qué puedo ayudarte?"

No uses "déjame ver" ni otras variaciones en el saludo inicial. Después del primer mensaje ya puedes usar expresiones naturales.

PERSONALIDAD:
- Cálida, cercana, genuina. Hablas como una persona real, no como un bot.
- Varias tu forma de expresarte. No suenas repetitiva ni estructurada.
- Expresiones naturales: "déjame ver", "claro que sí", "con gusto", "te entiendo", "tranquilo".
- Si alguien no sabe algo, normalízalo: "no te preocupes, eso es común".

REGLAS DE ORO (sobre cualquier otra instrucción):
1. Cuando el usuario diga QUÉ proteger, MUESTRA INTERÉS genuino y pregunta el nombre
   ANTES de recomendar. Ej: "¡Qué bien que quieras proteger a [lo que dijo]! ¿Cuál es tu nombre?"
   (No te vuelvas a presentar — ya lo hiciste en el saludo inicial.)
2. Después del nombre, ANTES de recomendar, pregunta 1-2 detalles clave del bien a
   asegurar según el tipo (ver ABAJO). Así la recomendación es más completa y personalizada.
   IMPORTANTE: NO digas "te recomiendo" todavía. Solo pregunta los detalles.
    Ej: "Genial, Alfredo. ¿Qué raza es y qué edad tiene?"
3. ⚠️ CRÍTICO — NO ES OPCIONAL: Cuando tengas el nombre + los detalles clave,
   DEBES llamar recommend_insurance(profile) con todo lo que hayas recopilado.
   NO describas productos de memoria. Si respondes sin llamar recommend_insurance,
   estás INCUMPLIENDO las reglas. La herramienta es la única fuente válida de
   recomendaciones.
4. Guarda el nombre con save_form_field(campo="nombre", valor="...") y USALO siempre.
5. Si el usuario ACEPTA una recomendación → llama quote_insurance(product_id, profile)
   INMEDIATAMENTE. NUNCA des precios de memoria.
6. NUNCA preguntes "¿quieres saber más?" — recomienda y cotiza ya.
7. NUNCA inventes productos, precios ni categorías que no vengan de las herramientas.
8. Sé BREVE. Máximo 2-3 oraciones. Una pregunta por turno.
9. CRÍTICO: Cuando preguntes por una mascota, usa SIEMPRE "raza" y NUNCA "tipo".
   Correcto: "¿Qué raza es?"
   Incorrecto: "¿Qué tipo de perro tienes?"

PREGUNTAS CLAVE POR CATEGORÍA (haz 1-2 ANTES de recommend_insurance,
integradas en la charla, no como formulario):

- VIDA / FAMILIA:
  1. "¿Es para ti o para tu familia?"
  2. Si familiar: "¿Cuántos son y qué edades tienen?" (clave para auxilio educativo)

- VEHÍCULO:
  1. "¿Qué tipo de vehículo? ¿Carro, moto, bicicleta, camión?"
  2. "¿Es uso particular o de trabajo?"

- MASCOTA:
   1. "¿Qué mascota tienes? ¿Perro, gato, conejo...?"
   2. "¿Qué raza es?" — IMPORTANTE: usa SIEMPRE la palabra "raza", NUNCA "tipo". Ej: "¿Qué raza es?" no "¿Qué tipo de perro es?"
   3. "¿Qué edad tiene?"

- VIVIENDA / HOGAR:
  1. "¿Es casa o apartamento?"
  2. "¿Es propia o alquilada?"

- VIAJES:
  1. "¿El viaje es nacional o internacional?"
  2. "¿Viajas solo o con familia?"

- ACCIDENTES:
  1. "¿Es para ti o para alguien más?"
  2. "¿Qué actividad o riesgo quieres cubrir?"

La lógica: cada pregunta reduce opciones y da contexto para una recomendación más precisa.
Suena natural, como quien quiere entender bien antes de aconsejar.

TONO — REGLA ESTRICTA:
- Usa SIEMPRE "tú" (tuteo colombiano neutro). NUNCA uses "vos" ni voseo.
- Verbos conjugados en tuteo: "tú cuentas", "tú tienes", "tú hablas", "tú eres",
  "tú recomiendas", "tú preguntas", "tú llamas".
- NUNCA uses: "contás", "tenés", "hablás", "sos", "recomendás", "preguntás",
  "llamá", "pedí", "normalizalo".
- Ejemplo correcto: "Juan, por lo que me cuentas te recomiendo..."
- Ejemplo INCORRECTO: "Juan, con lo que me contás te recomiendo..."

REGLAS DE FLUJO — PRODUCTOS COLSUBSIDIO (canal "🏢 COLSUBSIDIO"):
- Cuando tengas el resultado de recommend_insurance, preséntalo personalizado:
  "[nombre], por lo que me cuentas te recomiendo..."
- Cuando tengas el resultado de quote_insurance: "El plan estándar sale a $XX.XXX mensuales".
- Después de cotizar, pide el documento: "[nombre], para la póliza necesito tu número de documento".
- Cuando tengas el documento, pregunta por la aceptación de datos:
  "Perfecto. Antes de seguir, quiero que sepas que acá cuidamos tus datos personales.
   Puedes revisar nuestra política en https://www.colsubsidio.com/transparencia-acceso-informacion/tratamiento-datos-personales
   ¿Aceptas?"
- Si acepta, primero guarda save_form_field(campo="acepta_terminos", valor="true") y luego llama create_policy(documento="...", producto="..."). No necesitas pasar form_data — se carga automáticamente de la sesión.

REGLAS DE FLUJO — PRODUCTOS EXTERNOS (canal "🔗 EXTERNO"):
- Los productos marcados como EXTERNO no se venden en este chat.
- Preséntalos con la misma calidez: "[nombre], también hay una opción con [aseguradora]..."
- Describe brevemente el producto y luego dale el link de compra directa.
- Ejemplo: "Para comprarlo, puedes ir directamente a este enlace: [url_compra]"
- NO intentes cotizar ni crear póliza de productos externos — no hay herramienta para eso.
- Si el usuario pregunta por precio de un externo, dile que lo puede consultar en el enlace.
- Puedes recomendar AMBOS tipos juntos: primero los de Colsubsidio (venta directa aquí)
  y luego las alternativas externas con sus links.

REINICIO / CAMBIO DE OPINIÓN:
- Si el usuario dice "quiero otro producto", "empezar de nuevo", "cambiar", o similar,
  reinicia el flujo como si fuera el primer mensaje. No te quedes estancada.
- Ofrece ayuda: "Claro, sin problema. ¿Qué te gustaría proteger ahora?"

DESPUÉS DE CREAR LA PÓLIZA:
- Felicita al usuario de forma cálida: "¡Listo, [nombre]! Tu póliza ya está activa."
- Ofrece ayuda adicional: "¿Hay algo más en lo que pueda ayudarte?"
- Si el usuario dice que no, despídete amablemente.

IMPORTANTE — Formato de herramientas:
Llama una función por línea, sin texto antes ni después.
Ejemplo: <function=save_form_field>{"campo": "nombre", "valor": "Juan"}

CRÍTICO: Responde al usuario en ESPAÑOL NATURAL y cálido. No describas tu
razonamiento ni tu plan. Simplemente HAZ lo que dice la regla y RESPONDE
directamente."""

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
        # Pet-specific — weight 2 because mentioning a pet IS the insurance intent
        "perro": 2,
        "perrito": 2,
        "gato": 2,
        "gatito": 2,
        "mascota": 2,
        "mascotas": 2,
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
        "mascota", "perro", "perrito", "gato", "gatito",
        "mascotas", "perros", "perritos", "gatos", "gatitos",
        "canino", "felino", "can", "peludito", "peludo",
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
    audio_url: str | None = None
    buttons: list[dict] | None = None  # [{"label": "Sí", "value": "sí"}, ...]


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
        tts_service: object | None = None,
        stt_service: object | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._ai_client = ai_client
        self._tool_bridge = tool_bridge
        self.tts_service = tts_service
        self.stt_service = stt_service

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
    def _wants_reset(message: str) -> bool:
        """Detect if the user wants to restart the conversation flow.

        Matches common reset phrases in Spanish.
        """
        msg_lower = message.lower().strip()
        reset_patterns = [
            "empezar de nuevo", "empezar de cero", "comenzar de nuevo",
            "otro producto", "otro seguro", "cambiar de producto",
            "cambiar de seguro", "quiero otro", "mejor otro",
            "reiniciar", "volver a empezar", "desde el inicio",
            "desde cero", "quiero cambiar", "no ese", "prefiero otro",
        ]
        return any(pat in msg_lower for pat in reset_patterns)

    @staticmethod
    def _classify_intent(message: str) -> str | None:
        """Classify user intent at ``inicio`` state.

        Uses weighted keyword scoring against ``_INTENT_KEYWORDS``.
        Returns ``"insurance"`` or ``None`` (neutral/unclear).

        Two-path logic:
        1. If keyword score >= ``_INTENT_THRESHOLD`` (2) → insurance.
        2. Fallback: if a specific product was mentioned (via product-context
           keywords) AND at least one insurance keyword matched → insurance.
           This catches messages like "proteger a mi familia" or
           "cuidar a mi perrito" where direct keyword weight is insufficient.
        """
        msg_lower = message.lower()
        score = 0
        for kw, weight in _INTENT_KEYWORDS["insurance"].items():
            if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                score += weight

        if score >= _INTENT_THRESHOLD:
            return "insurance"

        # Fallback: product-context + at least one insurance signal
        if score > 0 and ChatService._detect_product_context(message):
            return "insurance"

        return None

    @staticmethod
    def _detect_product_context(message: str) -> str | None:
        """Detect the specific insurance product the user is asking about.

        Scans the message for product-specific keywords and returns the
        matching product ID (``"movilidad"``, ``"vida"``, ``"hogar"``, etc.)
        or ``None`` if no specific product is mentioned.

        For pet-related keywords, also matches variants like ``perrito``
        (diminutive) without requiring exact full-word boundaries.
        """
        msg_lower = message.lower()
        for product_id, keywords in _PRODUCT_CONTEXT_KEYWORDS.items():
            for kw in keywords:
                # Use strict word boundary for most contexts, but for
                # mascotas allow substring match so "perrito" matches "perro"
                if product_id == "mascotas":
                    if kw in msg_lower:
                        return product_id
                elif re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                    return product_id
        return None

    # ------------------------------------------------------------------
    # Dynamic system prompt
    # ------------------------------------------------------------------

    def _build_system_prompt(self, session: Session) -> str:
        """Build the dynamic system prompt for insurance-only flow.

        Two distinct modes:
        - ``perfilando`` → profiling + recommend only (NO form schema)
        - ``recopilando_datos_seguro`` / ``completado_seguro`` → full form schema
        """
        is_insurance = self._is_insurance_state(session.estado_actual)
        is_collecting = session.estado_actual in (
            "recopilando_datos_seguro", "completado_seguro",
        )

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

            # --- Perfilando mode: NO form collection ---
            if session.estado_actual == "perfilando":
                parts.append(
                    "--- MODO PERFILADO — ENTENDER, PREGUNTAR NOMBRE, Y RECOMENDAR ---\n"
                    "Estás en modo PERFILADO. Tu objetivo es entender la necesidad y\n"
                    "RECOMENDAR un producto usando recommend_insurance.\n"
                    "SÍ puedes usar save_form_field para guardar el NOMBRE del usuario\n"
                    "(campo='nombre'). NO recolectes otros datos del formulario todavía.\n"
                    "Solo habla con el usuario para saber qué necesita, guarda su nombre,\n"
                    "y llama recommend_insurance con los datos recolectados.\n"
                    "Una vez que el usuario elija un producto y cotices, ahí pasas\n"
                    "a recolectar más datos del formulario."
                )

                # --- Anonymous salary profiling (only during profiling) ---
                profile = session.insurance_profile or {}
                if not profile.get("categoria_afiliacion"):
                    parts.append(
                        "--- PERFILACIÓN SIN DOCUMENTO ---\n"
                        "El usuario NO tiene documento registrado. Para recomendar seguros,\n"
                        "necesitamos su rango salarial. Pregunta de forma BREVE y NATURAL:\n"
                        "'¿En qué rango de ingresos estás? Así te recomiendo lo que mejor se ajusta.'\n\n"
                        "Asignación:\n"
                        "- Más de $4.500.000 → Categoría A\n"
                        "- Entre $2.000.000 y $4.500.000 → Categoría B\n"
                        "- Menos de $2.000.000 → Categoría C\n\n"
                        "Llama a set_category con el valor A, B o C.\n"
                        "Si prefiere no compartir, asigna Categoría C y continúa."
                    )

        # --- Active form schema + collection state (ONLY in data collection) ---
        if is_collecting:
            parts.append("--- ESQUEMA DEL FORMULARIO DE SEGURO ---")
            parts.append(
                "Usa esta estructura para guiar la recolección de datos del seguro. "
                "Pregunta los campos de a UNO por turno, en orden lógico por sección. "
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

        # --- Tool instructions (ONLY in data collection) ---
        if is_collecting:
            parts.append(
                "--- INSTRUCCIONES DE RECOLECCIÓN (SEGURO) ---\n"
                "1. Ya conoces el nombre del usuario. Úsalo siempre.\n"
                "2. Pregunta los campos de a UNO por turno.\n"
                "3. Guarda cada respuesta con save_form_field:\n"
                "   <function=save_form_field>{\"campo\": \"nombre\", \"valor\": \"respuesta\"}\n"
                "4. Si el usuario no quiere dar un campo opcional, guarda con valor=None.\n"
                "5. Prioriza campos REQUERIDOS antes que opcionales.\n"
                "6. Cuando todos los REQUERIDOS estén completos, presenta un RESUMEN BREVE\n"
                "   (2-3 líneas) y pregunta '[nombre], ¿confirmas la solicitud?'.\n"
                 "7. Si confirma, guarda save_form_field(campo=\"acepta_terminos\", valor=\"true\") y luego usa create_policy(documento=\"...\", producto=\"...\").\n"
                "8. Si quiere cambiar algo, pregunta qué desea modificar."
            )

        # --- Voice instructions (TTS available) ---
        if self.tts_service is not None:
            parts.append(self._build_voice_prompt())

        return "\n\n".join(parts)

    @staticmethod
    def _build_voice_prompt() -> str:
        """Build voice/Audio system prompt fragment."""
        return (
            "--- INSTRUCCIONES DE VOZ ---\n"
            "Tienes la capacidad de responder con AUDIO (nota de voz) además de texto.\n\n"
            "CUÁNDO USAR AUDIO:\n"
            "- Saludos iniciales a clientes potenciales (genera confianza)\n"
            "- Cuando el usuario te haya enviado un audio (responde en el mismo formato)\n"
            "- Explicaciones de productos, coberturas, o recomendaciones (información útil en voz)\n"
            "- Respuestas informativas largas\n\n"
            "CUÁNDO NO USAR AUDIO:\n"
            "- NUNCA cuando respondas con URLs, teléfonos, correos electrónicos\n"
            "- NUNCA en mensajes de error o confirmaciones muy cortas\n"
            "- No es necesario usar audio siempre — la variedad es buena\n\n"
            "Tú decides cuándo es natural usar audio. Si crees que el momento lo amerita, "
            "marca tu respuesta para audio. Si no, solo texto está bien."
        )

    @staticmethod
    def _build_profiling_instructions(product_context: str | None) -> str:
        """Build context-aware profiling instructions based on the product
        the user asked about.

        When the user already said what to protect (product_context is set),
        the tool-call instruction goes FIRST so the AI sees it before any
        general profiling preamble.

        When no product context is detected, uses the general profiling flow.
        """
        lines: list[str] = [
            "--- PERFILACIÓN CONVERSACIONAL (SEGUROS) ---",
        ]

        if product_context == "movilidad":
            lines.extend([
                "",
                "⚠️ VEHÍCULO — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: tipo de vehículo, uso (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"tiene_vehiculo\": true, \"tipo\": \"carro\"}",
            ])
        elif product_context == "vida":
            lines.extend([
                "",
                "⚠️ VIDA — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: para quién, edades (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"familia_con_hijos\": true}",
            ])
        elif product_context == "hogar":
            lines.extend([
                "",
                "⚠️ HOGAR — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: casa/apartamento, propia/alquilada (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"es_propietario_vivienda\": true}",
            ])
        elif product_context == "mascotas":
            lines.extend([
                "",
                "⚠️ MASCOTAS — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: raza y edad (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"tiene_mascota\": true}",
            ])
        elif product_context == "viajes":
            lines.extend([
                "",
                "⚠️ VIAJES — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: nacional/internacional, solo/acompañado (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"viaja_frecuentemente\": true}",
            ])
        elif product_context == "accidentes":
            lines.extend([
                "",
                "⚠️ ACCIDENTES — SIGUE LAS REGLAS DE ORO 1-2-3 EN ORDEN:",
                "1. Pregunta el nombre del usuario (Regla de Oro #1).",
                "2. Pregunta 1-2 detalles: para quién, qué riesgo cubrir (Regla de Oro #2).",
                "   NO digas 'te recomiendo' todavía.",
                "3. DESPUÉS de tener nombre + detalles, llama recommend_insurance",
                "   con los datos. ES OBLIGATORIO. No describas productos de memoria.",
                "Ejemplo: <function=recommend_insurance>{\"edad\": 30}",
            ])

        # General profiling preamble — goes AFTER the product-specific action
        # so the AI reads "call the tool NOW" before any general guidance.
        lines.extend([
            "",
            "INSTRUCCIONES GENERALES DE PERFILADO:",
            "- NUNCA preguntes 'qué seguro quieres' — pregunta sobre su situación.",
            "- Con 2-3 datos clave YA puedes recomendar. No esperes a tener todo.",
            "- recommend_insurance espera campos ESPECÍFICOS en el profile.",
            "- NO inventes nombres de campos como 'tipo_cobertura'.",
            "- Después de llamar recommend_insurance, puedes refinar con más preguntas.",
        ])

        if product_context is None:
            lines.extend([
                "",
                "SIN CONTEXTO ESPECÍFICO: Pregunta de forma general para entender su situación.",
                "",
                "PREGUNTAS CLAVE (una por turno):",
                "- ¿Qué le gustaría proteger? (vehículo, familia, hogar, mascota)",
                "- Según la respuesta, haz 1-2 preguntas más sobre ese tema.",
                "",
                "▶ CUANDO LLAMES recommend_insurance, pasa en profile los campos del",
                "   contexto detectado (según la respuesta del usuario).",
            ])

        lines.extend([
            "",
            "CUANDO RECIBAS EL RESULTADO DE recommend_insurance:",
            "1. PRESENTALO al usuario textualmente. No inventes errores ni digas que faltan datos.",
            "2. recommend_insurance ya tiene suficiente información para recomendar.",
            "3. Si el usuario pide más detalles o un precio exacto, usa quote_insurance.",
            "4. NUNCA digas 'no se proporcionaron los campos necesarios' — eso es falso.",
        ])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main processing
    # ------------------------------------------------------------------

    async def _add_audio_to_result(
        self, reply: str, result: ChatResult, session: Session,
        *, user_sent_audio: bool = False,
    ) -> ChatResult:
        """Post-process a ChatResult: decide if audio is appropriate and generate it.

        Detects greeting context and product mentions automatically from the reply.
        If TTS service is not available or audio decision says no, returns unmodified.
        """
        if self.tts_service is None:
            return result

        # Auto-detect context signals
        is_greeting = session.estado_actual == "inicio" or "Soy Anna" in reply or "soy Anna" in reply
        has_product_keywords = any(
            kw in reply.lower()
            for kw in ("seguro", "vida", "hogar", "movilidad", "mascota", "viaje", "accidente")
        )

        context = AudioContext(
            is_greeting=is_greeting,
            user_sent_audio=user_sent_audio,
            product_mentioned=has_product_keywords,
            text_length=len(reply),
        )

        if AudioDecisionEngine.should_send_audio(reply, context):
            audio_url = await self.tts_service.generate(reply)
            result.audio_url = audio_url

        return result

    async def process_message(
        self, session: Session, user_message: str,
        *, user_sent_audio: bool = False,
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
        # --- 0a. Reset detection (any state) ---
        # If user wants to start over, reset to 'inicio' so intent classification runs.
        if session.estado_actual != "inicio" and self._wants_reset(user_message):
            logger.info("User requested reset from state %s", session.estado_actual)
            async with self._session_maker() as db:
                db_session = await db.get(Session, session.id)
                if db_session:
                    db_session.estado_actual = "inicio"
                    db_session.insurance_profile = {}
                    db_session.campos_diligenciados = {}
                    db_session.updated_at = datetime.now(timezone.utc)
                    await db.commit()
            session.estado_actual = "inicio"
            session.insurance_profile = {}
            session.campos_diligenciados = {}

        # --- 0b. Intent classification at 'inicio' ---
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
                       "Por favor intenta de nuevo.",
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
            result = ChatResult(
                session_id=session.id,
                reply=phase1.reply,
                model=phase1.model,
                campos_actualizados=campos_actualizados,
                completitud_pct=self._compute_completitud_pct(session),
            )
            result = await self._add_audio_to_result(phase1.reply, result, session, user_sent_audio=user_sent_audio)
            return result

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
            # IMPORTANT: NO tools in Phase 2 — the model must NOT call
            # more tools, it must respond to the user with the tool results.
            self._ai_client.chat_raw(phase2_messages, tools=None),
        )

        if phase2 is None:
            # Phase 2 timed out — user message already persisted, return error
            return ChatResult(
                session_id=session.id,
                reply="Lo siento, la solicitud tardó demasiado. "
                       "Por favor intenta de nuevo.",
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

        result = ChatResult(
            session_id=session.id,
            reply=phase2.reply,
            model=phase2.model,
            campos_actualizados=campos_actualizados,
            completitud_pct=completitud_pct,
        )

        # --- Add Sí/No buttons for data treatment acceptance ---
        # Show buttons when all required fields are complete AND
        # data treatment hasn't been accepted yet
        if (completitud_pct >= 100
                and session.estado_actual == "recopilando_datos_seguro"
                and not self._data_treatment_accepted(session)):
            result.buttons = [
                {"label": "Sí, acepto", "value": "sí"},
                {"label": "No, no acepto", "value": "no"},
            ]

        result = await self._add_audio_to_result(phase2.reply, result, session, user_sent_audio=user_sent_audio)
        return result

    # ------------------------------------------------------------------
    # Insurance state helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_insurance_state(estado: str) -> bool:
        """Return True if the given state is an insurance-specific state."""
        return estado in INSURANCE_STATES

    @staticmethod
    def _data_treatment_accepted(session: Session) -> bool:
        """Check if the user has already accepted data treatment.

        Checks both ``acepta_terminos`` (saved by the AI per prompt rule 5)
        and ``acepta_tratamiento_datos`` (legacy field name).
        """
        campos = session.campos_diligenciados or {}
        return (
            campos.get("acepta_tratamiento_datos") is True
            or campos.get("acepta_terminos") is True
        )

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

            # --- Profile pre-seed from get_customer ---
            if "get_customer" in tool_names and is_insurance:
                for tc in tool_calls:
                    if tc.function.name == "get_customer":
                        try:
                            args = json.loads(tc.function.arguments)
                            doc = args.get("documento_identidad")
                            if doc:
                                from app.services.segment_data import SegmentDataService
                                try:
                                    svc = SegmentDataService.get_instance()
                                    if svc and svc.is_loaded():
                                        info = svc.lookup_by_documento(doc)
                                        if info:
                                            # Create NEW dict so SQLAlchemy detects the change
                                            profile = dict(session.insurance_profile or {})
                                            existing_keys = set(profile.keys())
                                            if info.get("categoria"):
                                                profile["categoria_afiliacion"] = info["categoria"]
                                            if info.get("segmento"):
                                                profile["segmento_grupo_familiar"] = info["segmento"]
                                            session.insurance_profile = profile
                                            new_keys = set(profile.keys()) - existing_keys
                                            if new_keys:
                                                logger.debug(
                                                    "Profile pre-seeded from get_customer: %s", new_keys
                                                )
                                except Exception:
                                    logger.debug("Profile pre-seed skipped (segment data unavailable)")
                        except (json.JSONDecodeError, KeyError):
                            logger.debug("Could not parse get_customer args for pre-seed")

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
