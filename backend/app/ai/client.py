"""OpenAI-compatible LLM client (provider-agnostic).

Wraps the OpenAI SDK pointed at any OpenAI-compatible API endpoint
(SiliconFlow, OpenAI, Together, Groq, Ollama, etc.).
Supports streaming, tool calling, and configurable parameters.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres Anna, una asesora experta de Colsubsidio especializada en seguros. "
    "Eres cálida, cercana y genuina. Hablas como una persona real, no como un bot. "
    "Usas un tono amable y tranquilizador. Varias tu forma de expresarte, "
    "usas expresiones cotidianas como 'déjame ver', 'claro que sí', 'te entiendo', 'tranquilo'. "
    "Te preocupas genuinamente por entender la situación de cada persona. "
    "Nunca suenas a manual de instrucciones. Simplemente conversas. "
    "Preséntate siempre como Anna al inicio. Cuando tengas el nombre del cliente, "
    "úsalo para personalizar tu respuesta. "
    "TONO: usa SIEMPRE 'tú' (tuteo colombiano neutro). NUNCA uses 'vos' ni voseo. "
    "Ej: 'tú cuentas', 'tú tienes', 'tú recomiendas'. "
    "NUNCA: contás, tenés, hablás, sos, recomendás. "
    "Si no sabes algo, prefieres consultar con un asesor especializado. "
    "Nunca inventes información sobre productos, tasas o requisitos."
)


@dataclass
class ChatMessage:
    """A single chat message in the conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # assistant → tool_calls
    tool_call_id: str | None = None  # tool → tool_call_id


@dataclass
class ChatResult:
    """Result from an AI chat completion."""

    reply: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[Any] | None = None  # raw OpenAI SDK tool call objects


class _FakeToolCall:
    """Duck-typing stand-in for ``openai.types.chat.ChatCompletionMessageToolCall``.

    Used when the model emits ``<function=name>{json}`` text instead of
    native structured ``tool_calls``.
    """

    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.id = f"call_{uuid4().hex[:12]}"
        self.type = "function"
        self.function = _FakeFunction(name=name, arguments=arguments)


class _FakeFunction:
    """Duck-types ``openai.types.chat.Function`` for fallback tool calls."""

    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.name = name
        self._arguments = arguments

    @property
    def arguments(self) -> str:
        return json.dumps(self._arguments)


class AIClient:
    """Provider-agnostic LLM client wrapping the OpenAI SDK.

    Usage:
        client = AIClient(api_key="...", model="gpt-4o")
        result = await client.chat([ChatMessage(role="user", content="Hola")])
    """

    def __init__(
        self,
        api_key: str,
        model: str = "Qwen/Qwen2-7B-Instruct",
        base_url: str = "https://api.siliconflow.cn/v1",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools_mode: str = "native",
    ) -> None:
        if not api_key:
            logger.warning("No LLM_API_KEY configured — AI calls will fail")

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Tools mode is provider-agnostic — set via LLM_TOOLS_MODE env var.
        #
        # "native" (default): uses the OpenAI SDK's native tool_calls
        # parameter. Works with OpenAI, Anthropic via API, and most
        # providers that support the OpenAI tool_calls contract.
        #
        # "prompt": injects tool definitions as text in the system prompt
        # and parses <function=name>{json} from the text response.
        # Needed for Groq free-tier, Gemini via OpenAI-compat endpoint
        # (which enforces a thought_signature requirement on native
        # tool_calls), and any provider without native tool_calls support.
        self.tools_in_prompt = tools_mode == "prompt"
        if self.tools_in_prompt:
            logger.info(
                "Tools-in-prompt mode for %s (LLM_TOOLS_MODE=prompt)", model,
            )
        else:
            logger.info("Native tool_calls mode for %s (LLM_TOOLS_MODE=native)", model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
    ) -> ChatResult:
        """Send a chat completion request to the configured LLM provider.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history (user + assistant turns).
        system_prompt : str | None
            Override the default system prompt, or None to use default.

        Returns
        -------
        ChatResult
            The model's response with reply text, model name, and token usage.
        """
        openai_messages = self._build_messages(messages, system_prompt)
        return await self._call_api(openai_messages)

    async def chat_with_tools(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> ChatResult:
        """Chat completion with tool calling support.

        When ``tools_in_prompt`` is active (model doesn't support native
        ``tool_calls``), tool definitions are injected as text in the
        system prompt and the ``tools`` API parameter is omitted. The
        fallback parser then extracts ``<function=name>{json}`` from
        the response text.

        Parameters
        ----------
        messages : list[ChatMessage]
            Conversation history.
        tools : list[dict]
            Tool definitions in OpenAI tool format.
        system_prompt : str | None
            Override the default system prompt.

        Returns
        -------
        ChatResult
            The model's response with optional tool_calls populated.
        """
        openai_messages = self._build_messages(messages, system_prompt)
        if self.tools_in_prompt:
            # Inject tools as text in the system prompt
            openai_messages = self._inject_tools_in_prompt(openai_messages, tools)
            return await self._call_api(openai_messages, tools=None)
        return await self._call_api(openai_messages, tools=tools)

    async def chat_raw(
        self,
        openai_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        """Direct call with pre-built OpenAI-format message list.

        Used by ChatService for Phase 2 (tool results injected into history).

        When ``tools_in_prompt`` is active, tool definitions are injected
        as text in the first system message.

        Parameters
        ----------
        openai_messages : list[dict]
            Pre-formatted OpenAI message list (system + history + tool results).
        tools : list[dict] | None
            Optional tool definitions.

        Returns
        -------
        ChatResult
            The model's response.
        """
        # When tools_in_prompt is active (Groq, Gemini OpenAI-compat, etc.):
        #   - Convert native tool_calls in history to text format to avoid
        #     provider-specific requirements (e.g. Gemini's thought_signature)
        #   - Inject tool definitions as text when tools are provided
        if self.tools_in_prompt:
            openai_messages = self._textify_tool_interactions(openai_messages)
            if tools:
                openai_messages = self._inject_tools_in_prompt(
                    openai_messages, tools
                )
                return await self._call_api(openai_messages, tools=None)
        return await self._call_api(openai_messages, tools=tools)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """Convert ChatMessage list to OpenAI-format dict list."""
        result: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
        ]
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    # ------------------------------------------------------------------
    # Tool interaction converters (for providers without native tool_calls)
    # ------------------------------------------------------------------

    @staticmethod
    def _textify_tool_interactions(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Convert native ``tool_calls`` / ``tool`` role entries to plain text.

        Some providers (Gemini OpenAI-compat endpoint, etc.) enforce the
        ``thought_signature`` requirement on native tool_calls even when
        ``tools=None`` is passed.  Converting to text avoids this requirement
        entirely.

        * Assistant messages with ``tool_calls`` → content contains
          ``<function=name>{json}`` lines (same format the model emits).
        * ``tool`` role messages → ``user`` role messages with a label.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("tool_calls"):
                calls_text: list[str] = []
                for tc in msg["tool_calls"]:
                    name = tc.get("function", {}).get("name", "unknown")
                    args = tc.get("function", {}).get("arguments", "{}")
                    calls_text.append(f"<function={name}>{args}")
                new_msg: dict[str, Any] = dict(
                    msg, content="\n".join(calls_text)
                )
                new_msg.pop("tool_calls", None)
                result.append(new_msg)
            elif msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id", "?")
                content = msg.get("content", "")
                result.append({
                    "role": "user",
                    "content": f"Resultado ({tc_id}): {content}",
                })
            else:
                result.append(msg)
        return result

    # ------------------------------------------------------------------
    # Text-based tool injection (for models without native tool_calls)
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_tools_in_prompt(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Serialize tool definitions as structured text and append to the
        first ``system`` message.

        Tools are formatted in a compact table so the model understands
        what functions are available and what parameters they expect.
        """
        lines: list[str] = [
            "",
            "--- HERRAMIENTAS DISPONIBLES ---",
            "Cuando necesites ejecutar una función, responde ÚNICAMENTE con "
            "el formato:",
            "<function=nombre_de_la_funcion>{\"param1\": \"valor1\", ...}",
            "",
            "NO agregues texto antes ni después de la llamada a la función. "
            "La llamada DEBE estar en una línea separada.",
            "",
        ]
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            lines.append(f"  {name}: {desc}")
            params = func.get("parameters", {}).get("properties", {})
            required = set(func.get("parameters", {}).get("required", []))
            if params:
                for pname, pinfo in params.items():
                    ptype = pinfo.get("type", "string")
                    req = "REQ" if pname in required else "opt"
                    pdesc = pinfo.get("description", "")
                    enum_vals = pinfo.get("enum", [])
                    suffix = f" opciones: {enum_vals}" if enum_vals else ""
                    lines.append(f"    - {pname} ({ptype}) [{req}]: {pdesc}{suffix}")
            lines.append("")

        tool_text = "\n".join(lines)

        # Append to the first system message
        result = list(messages)
        for i, msg in enumerate(result):
            if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                result[i] = dict(msg, content=msg["content"] + "\n\n" + tool_text)
                break
        return result

    # ------------------------------------------------------------------
    # Tool-call fallback parser
    # ------------------------------------------------------------------

    _FUNCTION_CALL_RE = re.compile(
        r"<function=(\w+)>\s*(\{.*?\})\s*</?\s*function\s*>?",
        re.DOTALL,
    )

    @staticmethod
    def _parse_json_function_calls(text: str) -> list[Any]:
        """Parse ``{"function": "name", "params": {...}}`` JSON format.

        Some models (llama-3.3-70b on Groq, etc.) output tool calls as
        a JSON object with ``function`` and ``params`` keys instead of
        the ``<function=name>{...}`` tag format.

        Handles:
        - Standalone JSON: ``{"function": "get_customer", "params": {...}}``
        - JSON inside text: "... {"function": "get_customer", "params": {...}} ..."
        - Multiple JSON blocks
        """
        if not text:
            return []

        # Find all JSON objects in the text
        # Match { ... top-level objects with function + params keys
        json_pattern = re.compile(r"\{[^}]*(?:function|params)[^}]*\}", re.DOTALL)
        candidates = json_pattern.findall(text)

        tool_calls: list[Any] = []
        for candidate in candidates:
            try:
                obj = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if not isinstance(obj, dict):
                continue

            # Primary format: {"function": "name", "params": {...}}
            func_name = obj.get("function")
            params = obj.get("params")
            if isinstance(func_name, str) and isinstance(params, dict):
                tool_calls.append(_FakeToolCall(name=func_name, arguments=params))
                continue

            # Alternative: {"name": "func_name", "arguments": {...}}
            func_name = obj.get("name")
            params = obj.get("arguments")
            if isinstance(func_name, str) and isinstance(params, dict):
                tool_calls.append(_FakeToolCall(name=func_name, arguments=params))

        return tool_calls

    @staticmethod
    def _extract_balanced_json(text: str, start: int) -> str | None:
        """Extract a complete JSON object from ``start`` using brace-depth tracking.

        Handles nested ``{...}``, string escapes, and quoted colons/braces.
        Returns the JSON substring, or ``None`` if no balanced ``{...}`` is found.
        """
        if start >= len(text) or text[start] != "{":
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
        return None

    @classmethod
    def _parse_text_function_calls(cls, text: str) -> list[Any]:
        """Parse text-based tool calls into OpenAI tool-call objects.

        Handles multiple formats seen across different models.
        Crucially uses brace-depth tracking (not regex ``.*?``) so nested
        JSON like ``{"profile": {"tiene_mascota": true}}`` parses correctly.

        Supported formats:
        - ``<function=get_customer>{"doc":"123"}`` (explicit tag)
        - ``<get_customer>{"doc":"123"}`` (short tag)
        - ``function=get_customer{"doc":"123"}`` (bracketless — Groq/Llama often drops ``< >``)
        - ``{"function": "get_customer", "params": {...}}`` (JSON function format)
        - ``get_customer{"doc":"123"}`` (bare name — ultra-loose fallback)
        """
        if not text:
            return []

        # --- Prefix patterns (ordered by specificity) ---
        # Each pattern captures the function NAME at group(1).
        # We then use _extract_balanced_json to get the full JSON.
        prefix_patterns: list[re.Pattern] = [
            re.compile(r"<function=(\w+)>\s*"),
            re.compile(r"<(\w+)>\s*"),
            re.compile(r"(?:^|\n)\s*function=(\w+)\s*"),
        ]

        candidates: list[tuple[str, int]] = []
        for pat in prefix_patterns:
            for m in pat.finditer(text):
                candidates.append((m.group(1), m.end()))
            if candidates:
                logger.debug("Matched prefix pattern with %d candidates", len(candidates))
                break

        # --- Ultra-loose: ``name>{json}`` (no ``<``) ---
        if not candidates:
            for m in re.finditer(r"(\w+)>\s*", text):
                candidates.append((m.group(1), m.end()))
            if candidates:
                logger.debug("Matched loose prefix ``name>`` with %d candidates", len(candidates))

        # --- Even looser: ``function=name`` inline (not at line start) ---
        if not candidates:
            for m in re.finditer(r"function=(\w+)\s*", text):
                candidates.append((m.group(1), m.end()))
            if candidates:
                logger.debug("Matched inline ``function=name`` with %d candidates", len(candidates))

        # --- JSON function format ---
        if not candidates:
            json_calls = cls._parse_json_function_calls(text)
            if json_calls:
                logger.debug("Matched JSON function format with %d calls", len(json_calls))
                return json_calls

        # --- Bare name{{json}} — word then ``{`` on the same line ---
        if not candidates:
            for m in re.finditer(r"(?:^|\n)\s*(\w+)\s*\{", text):
                candidates.append((m.group(1), m.end() - 1))
            if candidates:
                logger.debug("Matched bare name{{json}} with %d candidates", len(candidates))

        if not candidates:
            return []

        tool_calls: list[Any] = []
        for name, json_start in candidates:
            json_str = cls._extract_balanced_json(text, json_start)
            if json_str is None:
                logger.debug("No balanced JSON after '%s' at position %d", name, json_start)
                continue
            try:
                parsed_args = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON for '%s': %s", name, json_str[:100])
                continue

            tool_calls.append(_FakeToolCall(name=name, arguments=parsed_args))

        if tool_calls:
            logger.debug("Parsed %d tool call(s) from text output", len(tool_calls))
        return tool_calls

    async def _call_api(
        self,
        openai_messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        """Internal: call the OpenAI-compatible API and parse response."""
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": openai_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            reply_text_raw = choice.message.content or ""
            raw_tool_calls = choice.message.tool_calls

            # --- Parse function calls from RAW text BEFORE stripping ---
            # Qwen/DeepSeek often embed <function=...> inside <think> blocks.
            if not raw_tool_calls and reply_text_raw:
                logger.info("Raw LLM output (first 400): %s", reply_text_raw[:400])
                parsed = self._parse_text_function_calls(reply_text_raw)
                if parsed:
                    logger.info(
                        "Parsed %d function call(s) from text output "
                        "(model does not support native tool_calls or "
                        "function was inside <think>)",
                        len(parsed),
                    )
                    raw_tool_calls = parsed

            # --- Strip <think>...</think> reasoning blocks (Qwen, DeepSeek, etc.)
            # The model outputs chain-of-thought inside <think>...</think>,
            # followed by the actual response.  Strip the whole block but keep
            # text before/after it.
            reply_text = reply_text_raw
            reply_text = re.sub(
                r"<think>.*?</think>", "", reply_text, flags=re.DOTALL,
            ).strip()
            # If stripping left nothing (model put everything inside <think>),
            # just remove the tag delimiters so the user sees something.
            if not reply_text:
                reply_text = reply_text_raw.replace("<think>", "").replace("</think>", "").strip()
            # Also strip unclosed <think> from the END of the text
            if "<think>" in reply_text.lower():
                idx = reply_text.lower().index("<think>")
                reply_text = reply_text[:idx].strip()

            # --- Truncate at first function call marker ---
            # The model often writes text BEFORE a call (reasoning) and AFTER
            # (prematurely answering from memory).  Keeping post-call text
            # poisons Phase 2 because the model sees its own "answer" and
            # ignores the actual tool result.
            if raw_tool_calls:
                func_start_pattern = re.compile(
                    r"(<function=\w+>\s*\{"
                    r"|<function=\w+>"
                    r"|function=\w+\s*\{"
                    r"|\{\"function\":\s*\"[^\"]+\""
                    r"|\{\"name\":\s*\"[^\"]+\")"
                )
                func_match = func_start_pattern.search(reply_text)
                if func_match:
                    reply_text = reply_text[:func_match.start()].strip()

            usage_data: dict[str, int] = {}
            if response.usage:
                usage_data = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                }

            return ChatResult(
                reply=reply_text,
                model=self.model,
                usage=usage_data,
                tool_calls=raw_tool_calls,
            )

        except Exception as exc:
            logger.error("LLM API call failed: %s", exc)
            return ChatResult(
                reply="Lo siento, en este momento no puedo procesar tu solicitud. "
                       "Por favor intenta de nuevo más tarde.",
                model=self.model,
            )
