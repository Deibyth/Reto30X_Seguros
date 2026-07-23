# AI Tool Loop Specification

> **Capability:** C08 — `ai-tool-loop`
> **Change:** `fase2-chat-ia-mcp`
> **Date:** 2026-07-16

## Purpose

Bridge between FastMCP tool definitions and OpenAI's tool-calling format, execute the two-phase AI call loop (initial call → tool execution → follow-up call), and handle errors gracefully.

## Requirements

### Requirement: Tool bridge

The system SHALL have a `ToolBridge` class in `app/services/tool_bridge.py` that reads tool definitions from the FastMCP registry and converts them to OpenAI-compatible tool schema arrays. Each MCP tool SHALL map to an OpenAI `{type: "function", function: {name, description, parameters}}` entry.

#### Scenario: Bridge converts MCP tools
- GIVEN the FastMCP server has 5 domain tools registered
- WHEN `ToolBridge.to_openai_schema()` is called
- THEN it returns a list of 5 OpenAI tool schema objects
- AND each schema has `name`, `description`, and `parameters` matching the MCP tool definition

### Requirement: Tool execution by name

`ToolBridge` SHALL expose an `execute_tool(name: str, args: dict) -> Any` method that resolves the tool name to the actual FastMCP tool function, calls it with the provided arguments, and returns the result. If the tool name is unknown, SHALL raise `ValueError`.

#### Scenario: Tool executed by name
- GIVEN a registered tool `get_products`
- WHEN `bridge.execute_tool("get_products", {"tipo": "credito"})` is called
- THEN the tool function is invoked with `tipo="credito"`
- AND the result is returned

#### Scenario: Unknown tool raises
- GIVEN no tool named `nonexistent_tool` is registered
- WHEN `bridge.execute_tool("nonexistent_tool", {})` is called
- THEN a `ValueError` is raised

### Requirement: Two-phase execution loop

The system SHALL implement a two-phase AI call in `ChatService`:

1. **Phase 1**: Call `AIClient.chat_with_tools()` with history and tool schemas
2. If the response contains `tool_calls`, execute each via `ToolBridge.execute_tool()`
3. Append tool results as a new message with `role="tool"`
4. **Phase 2**: Call `AIClient.chat()` with the augmented history (including tool results)
5. Return the final assistant reply

#### Scenario: Tool called and result injected
- GIVEN a user asks "qué productos tienen?"
- WHEN Phase 1 returns a `tool_calls` request for `get_products`
- THEN the tool is executed and its result is appended to the message list
- AND Phase 2 produces a natural-language response describing the products

#### Scenario: No tools needed
- GIVEN a simple greeting like "hola"
- WHEN Phase 1 returns no `tool_calls`
- THEN Phase 2 is skipped
- AND the Phase 1 reply is returned directly

### Requirement: Error handling in tool loop

If a tool execution fails (exception or timeout), the system SHALL append an error message as the tool result and continue to Phase 2. The AI SHALL inform the user that the operation failed and suggest alternatives.

#### Scenario: Tool failure handled gracefully
- GIVEN `get_customer` raises a database error
- WHEN the tool is executed in Phase 1
- THEN the tool result is `{"error": "..."}` 
- AND Phase 2 produces a reply apologizing and suggesting retry

### Requirement: Timeout guard

Each AI call (Phase 1 and Phase 2) SHALL have a 30-second timeout. If the AI call exceeds 30 seconds, the system SHALL return a fallback message: "Lo siento, la solicitud tardó demasiado. Por favor intentá de nuevo."

#### Scenario: AI call times out
- GIVEN the SiliconFlow API takes more than 30 seconds
- WHEN a chat message is processed
- THEN the system returns a timeout fallback message
- AND no conversation rows are persisted for that turn
