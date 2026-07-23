# Delta for AI Tool Loop

> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## ADDED Requirements

### Requirement: Multi-domain tool registration

The FastMCP server SHALL register insurance tools (`recommend_insurance`, `quote_insurance`, `create_policy`) alongside existing credit tools. ToolBridge SHALL auto-discover all registered tools regardless of domain — no separate registration step needed.

| Tool | Domain | Group |
|------|--------|-------|
| `recommend_insurance` | Insurance | `insurance` |
| `quote_insurance` | Insurance | `insurance` |
| `create_policy` | Insurance | `insurance` |

Existing credit tools SHALL remain registered unchanged.

#### Scenario: Insurance tools discovered by ToolBridge
- GIVEN the FastMCP server has 3 insurance + 5 credit tools registered
- WHEN `ToolBridge.to_openai_schema()` is called
- THEN it SHALL return 8 tool schemas total
- AND each insurance tool has `name`, `description`, and `parameters` matching its MCP definition

#### Scenario: Insurance tool executed by name
- GIVEN insurance tools are registered
- WHEN `bridge.execute_tool("recommend_insurance", {"profile": {...}})` is called
- THEN the `recommend_insurance` function is invoked with the profile dict
- AND the result is returned to the AI

### Requirement: Context-aware tool injection

The system MAY inject only the relevant tool subset into the AI call context based on `session.estado_actual`. Credit tools MAY be filtered out during insurance states and vice versa. This SHALL be an optimization only — ToolBridge still resolves all tools.

#### Scenario: Insurance tools active in insurance states
- GIVEN a session at `estado_actual="perfilando"`
- WHEN the AI call context is built
- THEN `recommend_insurance`, `quote_insurance`, and `create_policy` SHALL be available
- AND credit-only tools (e.g., `simulate_credit`) MAY be excluded

## MODIFIED Requirements

### Requirement: Tool execution by name

The system SHALL have a `ToolBridge` class that reads tool definitions from the FastMCP registry and converts them to OpenAI-compatible tool schema arrays. Each MCP tool SHALL map to an OpenAI `{type: "function", function: {name, description, parameters}}` entry. ToolBridge SHALL expose an `execute_tool(name: str, args: dict) -> Any` method that resolves the tool name and calls it. Tools MAY be grouped by domain (credit, insurance) for selective injection.
(Previously: ToolBridge read from FastMCP registry and executed tools; no domain grouping concept)

#### Scenario: Bridge converts all domain tools
- GIVEN the FastMCP server has 8 domain tools (5 credit, 3 insurance)
- WHEN `ToolBridge.to_openai_schema()` is called
- THEN it returns all 8 OpenAI tool schema objects
- AND each schema has `name`, `description`, and `parameters`

#### Scenario: Unknown tool raises
- GIVEN no tool named `nonexistent_tool` is registered
- WHEN `bridge.execute_tool("nonexistent_tool", {})` is called
- THEN a `ValueError` is raised
