# Delta for fastmcp-server

> **Change:** `fase2-chat-ia-mcp`
> **Source:** `openspec/specs/fastmcp-server/spec.md` (C04)

## ADDED Requirements

### Requirement: Domain tool registration

The system SHALL import and register 5 domain tools from `app.tools.domain_tools` onto the `FastMCP("Proteccion360")` instance: `get_products`, `get_customer`, `check_eligibility`, `simulate_credit`, `get_insurance`.

(Previously: N/A — only hello_world existed)

#### Scenario: Five tools registered
- GIVEN the FastMCP server is initialized
- WHEN the tool list is inspected
- THEN exactly 5 domain tools are registered
- AND `hello_world` is NOT registered

### Requirement: ORM access in tools

Each domain tool function SHALL have access to an async SQLAlchemy session via a global `async_session_maker` imported from `app.database`. Tools SHALL create their own session context and close it after returning.

(Previously: no DB access)

#### Scenario: Tool queries database
- GIVEN the async_session_maker is configured
- WHEN a domain tool executes
- THEN it acquires an async session, queries the database, and returns ORM data
- AND the session is properly closed

## MODIFIED Requirements

### Requirement: F-MCP-02 — Tool registration

The system SHALL register tools decorated with `@mcp.tool()` from `app.tools.domain_tools`. The `hello_world` tool SHALL be removed from `app.tools.mcp_server`.
(Previously: registered hello_world only)

#### Scenario: Domain tools imported
- GIVEN `app.tools.domain_tools` exists
- WHEN `app.tools.mcp_server` is loaded
- THEN the domain tools are registered on the `mcp` instance

### Requirement: NF-MCP-04 — Tool design constraint

Tool functions SHALL be designed for ORM access using the async session pattern. Tools MAY query the database and SHALL NOT be stateless.
(Previously: tools SHALL be stateless, no DB or external service calls)

#### Scenario: Tool queries product data
- GIVEN a tool function with ORM access
- WHEN `get_products()` is called
- THEN it returns data from the `products` and `insurances` tables

## REMOVED Requirements

### Requirement: F-MCP-03 — hello_world name parameter

(Reason: hello_world tool removed; domain tools have their own parameters)
(Migration: N/A — no production consumers depend on hello_world)

### Requirement: F-MCP-04 — hello_world return value

(Reason: hello_world tool removed)
(Migration: N/A)
