# Spec: FastMCP Server

> **Capability:** C04 — `fastmcp-server`
> **Change:** `fundacion-plataforma`
> **Date:** 2026-07-16

## Description

Embedded FastMCP server inside the FastAPI process, providing MCP tools consumable by AI models. For Fase 1, the server exposes a single `hello_world` tool that accepts a name and returns a greeting — proving the MCP integration works end-to-end.

## Requirements

### Functional

- F-MCP-01: The system SHALL create a `FastMCP` instance named `"Proteccion360"` inside the application process.
- F-MCP-02: The system SHALL register a `hello_world` tool decorated with `@mcp.tool()`.
- F-MCP-03: The `hello_world` tool SHALL accept an optional `name: str` parameter (default `"Mundo"`).
- F-MCP-04: The `hello_world` tool SHALL return `f"Hola, {name}! Bienvenido a Protección Inteligente 360°"`.
- F-MCP-05: The MCP server SHALL be accessible via the MCP protocol (stdio mode for MVP; SSE-ready).
- F-MCP-06: The MCP server instance SHALL be importable from `app.tools.mcp_server`.
- F-MCP-07: The system SHALL log MCP server initialization at startup.

### Non-Functional

- NF-MCP-01: FastMCP SHALL be pinned to `fastmcp>=0.3.0,<1.0.0` (pre-1.0 API may change).
- NF-MCP-02: The MCP server SHALL NOT block FastAPI startup or shutdown.
- NF-MCP-03: The MCP server SHALL be designed for future extraction into a sidecar container.
- NF-MCP-04: Tool functions SHALL be stateless (no DB or external service calls in Fase 1).

## FastMCP Tool

```python
# app/tools/mcp_server.py
from fastmcp import FastMCP

mcp = FastMCP("Proteccion360")

@mcp.tool()
def hello_world(name: str = "Mundo") -> str:
    """Saluda a un usuario."""
    return f"Hola, {name}! Bienvenido a Protección Inteligente 360°"
```

## Integration Pattern

The MCP server is initialized in its own module and imported by the app factory. For MVP, the server runs in stdio mode (the default). The FastAPI app does not mount the MCP server as a route — it exists as a separately addressable MCP endpoint.

Future evolution:
- Fase 2+: Run as SSE server on a separate port for sidecar extraction
- Fase 3+: Domain-specific tools (credit simulation, policy lookup, etc.)

## File Structure

```
backend/app/tools/
├── __init__.py
└── mcp_server.py            # FastMCP("Proteccion360") + hello_world tool
```

## Dependencies

**Inter-capability:**
- `health-check` (C01) — app factory logs MCP init during startup lifecycle
- `data-models` (C02) — (future) MCP tools will query models
- `docker-infrastructure` (C05) — (future) sidecar container if extracted

**External:**
- `fastmcp>=0.3.0,<1.0.0`

## Scenarios

### Scenario 1: hello_world default greeting
**Given** the FastMCP server is initialized
**When** `hello_world()` is called with no arguments
**Then** the return value is `"Hola, Mundo! Bienvenido a Protección Inteligente 360°"`

### Scenario 2: hello_world custom name
**Given** the FastMCP server is initialized
**When** `hello_world(name="Deiby")` is called
**Then** the return value is `"Hola, Deiby! Bienvenido a Protección Inteligente 360°"`

### Scenario 3: MCP server importable
**Given** the backend package structure
**When** `from app.tools.mcp_server import mcp` is executed
**Then** the import succeeds
**And** `mcp.name` equals `"Proteccion360"`
