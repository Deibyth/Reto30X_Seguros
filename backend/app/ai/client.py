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
    "Español neutro siempre: sin regionalismos, sin voseo, sin modismos locales. "
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
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> None:
        if not api_key:
            logger.warning("No LLM_API_KEY configured — AI calls will fail")

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Auto-detect: ALL Groq free-tier models output <function=name>{json}
        # as text instead of native structured tool_calls. Always use
        # tools-in-prompt mode (text injection + fallback parser) for Groq.
        # Non-Groq providers (OpenAI, Ollama, SiliconFlow with capable models)
        # can use native tool_calls.
        is_groq = "groq" in (base_url or "").lower()
        self.tools_in_prompt = is_groq
        if self.tools_in_prompt:
            logger.info(
                "Tools-in-prompt mode for %s (Groq — no native tool_calls)",
                model,
            )
        else:
            logger.info("Native tool_calls mode for %s", model)

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
        if self.tools_in_prompt and tools:
            openai_messages = self._inject_tools_in_prompt(openai_messages, tools)
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
            "Cuando necesites ejecutar una función, respondé ÚNICAMENTE con "
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

    @classmethod
    def _parse_text_function_calls(cls, text: str) -> list[Any]:
        """Parse text-based tool calls into OpenAI tool-call objects.

        Handles multiple formats seen across different models:
        - ``<function=get_customer>{"doc":"123"}`` (explicit tag format)
        - ``<get_customer>{"doc":"123"}`` (short tag)
        - ``{"function": "get_customer", "params": {...}}`` (JSON function format)
        """
        if not text:
            return []

        # Try multiple patterns in order of specificity
        patterns = [
            re.compile(r"<function=(\w+)>\s*(\{.*?\})", re.DOTALL),
            re.compile(r"<(\w+)>\s*(\{.*?\})", re.DOTALL),
            # Loose match: name>{json} (when <function= is partially stripped)
            re.compile(r"<function=(\w+)>\s*(\{.*?\})", re.DOTALL),
        ]

        all_matches: list[tuple[str, str]] = []
        for pat in patterns:
            all_matches = pat.findall(text)
            if all_matches:
                logger.debug("Matched pattern %s with %d calls", pat.pattern, len(all_matches))
                break

        # --- Ultra-loose: find any name>{\"... pattern ---
        if not all_matches:
            loose = re.findall(r"(\w+)>\s*(\{.*?\})", text, re.DOTALL)
            if loose:
                logger.debug("Matched loose pattern with %d calls", len(loose))
                all_matches = loose

        # --- JSON function format: {"function": "name", "params": {...}} ---
        # Some models (llama-3.3-70b, etc.) emit this instead of <function=...>
        if not all_matches:
            json_calls = cls._parse_json_function_calls(text)
            if json_calls:
                logger.debug("Matched JSON function format with %d calls", len(json_calls))
                return json_calls

        if not all_matches:
            return []

        tool_calls: list[Any] = []
        for name, args_json in all_matches:
            try:
                parsed_args = json.loads(args_json)
            except json.JSONDecodeError:
                logger.warning("Failed to parse function args: %s", args_json[:100])
                continue

            tool_calls.append(_FakeToolCall(name=name, arguments=parsed_args))

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
            reply_text = choice.message.content or ""
            raw_tool_calls = choice.message.tool_calls

            # --- Fallback: parse <function=name>{json} text ---
            if not raw_tool_calls and reply_text:
                logger.debug("Raw LLM output (first 300): %s", reply_text[:300])
                parsed = self._parse_text_function_calls(reply_text)
                if parsed:
                    logger.info(
                        "Parsed %d function call(s) from text output "
                        "(model does not support native tool_calls)",
                        len(parsed),
                    )
                    raw_tool_calls = parsed
                    # Strip the function call tags from the reply text
                    reply_text = self._FUNCTION_CALL_RE.sub("", reply_text).strip()
                    # Also strip simpler pattern
                    reply_text = re.sub(
                        r"<function=\w+>\s*\{.*?\}", "", reply_text, flags=re.DOTALL,
                    ).strip()
                    # Strip JSON function format: {"function": "name", "params": {...}}
                    reply_text = re.sub(
                        r'\{"function":\s*"[^"]+"\s*,\s*"params":\s*\{[^}]*\}\}',
                        "", reply_text, flags=re.DOTALL,
                    ).strip()

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
                       "Por favor intentá de nuevo más tarde.",
                model=self.model,
            )
