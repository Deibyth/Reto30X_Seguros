"""Bridge between FastMCP tool definitions and OpenAI tool-calling format.

Reads tool registrations from the FastMCP instance and exposes them
as OpenAI-compatible tool schemas. Also provides tool execution by name.

Tools are grouped by domain (``credit``, ``insurance``) for selective
injection. Tools without an explicit domain tag are treated as shared
and visible in all domains.
"""

import logging
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Mapping of tool name → domain tag. Tools not listed are treated as
# shared (visible in all domains).
TOOL_DOMAINS: dict[str, str] = {
    "get_customer": "credit",
    "get_products": "credit",
    "simulate_credit": "credit",
    "create_application": "credit",
    "send_sms": "credit",
    # save_form_field is intentionally NOT domain-tagged (shared) so the AI
    # can call it in both credit and insurance data-collection states.
    "calculate_amortization": "credit",
    "check_eligibility": "credit",
    "recommend_insurance": "insurance",
    "quote_insurance": "insurance",
    "create_policy": "insurance",
    "set_category": "insurance",
}


class ToolBridge:
    """Converts FastMCP registered tools to OpenAI tool schema and executes calls.

    Hides internal parameters (like ``session_id``) from the model schema
    but injects them automatically at execution time.

    Usage:
        bridge = ToolBridge(mcp_instance)
        bridge.current_session_id = "uuid-..."
        tools = await bridge.get_openai_tools()
        result = await bridge.execute_tool("get_products", {"tipo": "credito"})
    """

    # Parameters to hide from the model (injected by the backend).
    # Per-tool mapping: only inject session_id into tools that need it.
    HIDDEN_PARAMS: dict[str, set[str]] = {
        "save_form_field": {"session_id"},
        "set_category": {"session_id"},
        "create_policy": {"session_id"},
    }

    def __init__(self, mcp_instance: FastMCP) -> None:
        self._mcp = mcp_instance
        self._tool_cache: dict[str, Any] = {}
        # Will be set by ChatService before each message processing
        self.current_session_id: str | None = None

    async def _ensure_cache(self) -> None:
        """Populate tool cache from FastMCP registry (lazy, once)."""
        if self._tool_cache:
            return
        tools = await self._mcp.list_tools()
        for tool in tools:
            self._tool_cache[tool.name] = tool
        logger.debug("ToolBridge: cached %d tools", len(self._tool_cache))

    async def get_openai_tools(
        self, domain: str | None = None
    ) -> list[dict[str, Any]]:
        """Return OpenAI-format tool definitions for registered MCP tools.

        Parameters
        ----------
        domain : str | None
            If ``"credit"``, return only credit-tagged tools.
            If ``"insurance"``, return only insurance-tagged tools.
            If ``None``, return all tools.

        Strips per-tool ``HIDDEN_PARAMS`` from each schema so the model
        never sees internal parameters — the bridge injects them at execution.
        """
        await self._ensure_cache()
        result: list[dict[str, Any]] = []
        for name, tool in self._tool_cache.items():
            # Apply domain filter
            tool_domain = TOOL_DOMAINS.get(name)
            if domain is not None and tool_domain is not None and tool_domain != domain:
                continue

            params = dict(tool.parameters) if tool.parameters else {
                "type": "object", "properties": {},
            }

            # Strip per-tool hidden params from properties and required list
            hidden = self.HIDDEN_PARAMS.get(name, set())
            props = dict(params.get("properties", {}))
            required = list(params.get("required", []))
            for h in hidden:
                props.pop(h, None)
                try:
                    required.remove(h)
                except ValueError:
                    pass

            params["properties"] = props
            params["required"] = required

            result.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description or "",
                    "parameters": params,
                },
            })
        return result

    def _normalize_profile_args(self, name: str, full_args: dict[str, Any]) -> None:
        """Mutate ``full_args`` in place: wrap root-level profile fields
        under ``profile`` if the tool expects one but the model sent fields
        directly at root level.

        Some models (e.g. Qwen on Groq) emit flattened fields like
        ``{"tiene_mascota": true}`` instead of the canonical
        ``{"profile": {"tiene_mascota": true}}``.

        Detection logic: if the tool declares a ``profile: object`` parameter
        and ``full_args`` lacks a ``profile`` key, any keys that are NOT
        recognised root-level parameters of the tool are presumed to be
        profile fields and get bundled under ``profile``.
        """
        tool = self._tool_cache.get(name)
        if tool is None or tool.parameters is None:
            return
        props = tool.parameters.get("properties", {})
        profile_schema = props.get("profile")
        if profile_schema is None or profile_schema.get("type") != "object":
            return
        # profile key already present → nothing to normalise
        if "profile" in full_args:
            return
        # Determine which root-level params are NOT ``profile``
        root_params: set[str] = set(props.keys()) - {"profile"}
        # Any argument key that is NOT a recognised root param is likely a
        # profile field.
        arg_keys = set(full_args.keys())
        profile_candidates = arg_keys - root_params
        if not profile_candidates:
            return
        profile_dict: dict[str, Any] = {}
        for key in list(full_args.keys()):
            if key not in root_params:
                profile_dict[key] = full_args.pop(key)
        full_args["profile"] = profile_dict

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with the given arguments.

        Injects per-tool hidden params (e.g. ``session_id`` for
        ``save_form_field``) automatically before calling.
        """
        await self._ensure_cache()
        tool = self._tool_cache.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: '{name}'")

        # Normalise profile arguments (models sometimes flatten profile fields)
        full_args = dict(arguments)
        self._normalize_profile_args(name, full_args)

        # Inject per-tool hidden params
        hidden = self.HIDDEN_PARAMS.get(name, set())
        if "session_id" in hidden and self.current_session_id:
            full_args.setdefault("session_id", self.current_session_id)

        try:
            result = await self._mcp.call_tool(name, full_args)
            texts: list[str] = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
                else:
                    texts.append(str(content))
            return "\n".join(texts)
        except Exception as exc:
            logger.error("Tool '%s' execution failed: %s", name, exc)
            return f"Error al ejecutar '{name}': {exc!s}"
