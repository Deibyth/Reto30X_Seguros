# MCP Domain Tools Specification

> **Capability:** C07 — `mcp-domain-tools`
> **Change:** `fase2-chat-ia-mcp`
> **Date:** 2026-07-16

## Purpose

Five ORM-backed MCP tools enabling the AI to query products, customers, check eligibility, simulate credits, and fetch insurance details.

## Requirements

### Requirement: Tool signature contract

Each domain tool SHALL be decorated with `@mcp.tool()`, accept typed parameters, return JSON-serializable data, and use an async SQLAlchemy session sourced from the global `async_session_maker`.

| Tool | Signature | Return |
|------|-----------|--------|
| `get_products` | `(tipo: str \| None = None) -> list[dict]` | All products (filtered by `tipo` if provided: `"credito"` / `"seguro"`). Returns `Product` + `Insurance` data. |
| `get_customer` | `(documento_identidad: str) -> dict \| None` | Customer matching the identity document, or `None` if not found. |
| `check_eligibility` | `(customer_id: str) -> dict` | Eligibility assessment: `elegible: bool`, `razones: list[str]`, `monto_maximo: float \| None`. |
| `simulate_credit` | `(monto: float, plazo: int) -> dict` | Monthly payment using flat-rate formula, total interest, total repayment. |
| `get_insurance` | `(insurance_id: str) -> dict \| None` | Insurance detail including coverage and base premium, or `None`. |

#### Scenario: get_products returns all
- GIVEN products and insurances exist in the database
- WHEN `get_products()` is called with no arguments
- THEN it returns a list containing both credit products and insurances

#### Scenario: get_products filtered by tipo
- GIVEN mixed products exist
- WHEN `get_products(tipo="credito")` is called
- THEN only credit-type products are returned

#### Scenario: get_customer found
- GIVEN a customer with `documento_identidad="1234567890"` exists
- WHEN `get_customer("1234567890")` is called
- THEN the customer dict is returned with all fields

#### Scenario: get_customer not found
- GIVEN no customer exists with that document
- WHEN `get_customer("nonexistent")` is called
- THEN `None` is returned

#### Scenario: check_eligibility eligible
- GIVEN a customer with sufficient salary and credit score
- WHEN `check_eligibility("customer-id")` is called
- THEN `elegible` is `true` and `monto_maximo` reflects the calculated max amount

#### Scenario: check_eligibility ineligible
- GIVEN a customer with low credit score
- WHEN `check_eligibility("customer-id")` is called
- THEN `elegible` is `false` and `razones` contains the reason(s)

#### Scenario: simulate_credit valid inputs
- GIVEN positive monto and plazo
- WHEN `simulate_credit(5000000, 24)` is called
- THEN it returns `cuota_mensual`, `interes_total`, `total_pagar`
- AND the calculation uses a fixed annual interest rate (configurable)

#### Scenario: simulate_credit invalid inputs
- GIVEN negative or zero monto/plazo
- WHEN `simulate_credit(-1000, 0)` is called
- THEN the tool returns an error dict with `error` field describing the issue

#### Scenario: get_insurance found
- GIVEN an insurance with the given ID exists
- WHEN `get_insurance("insurance-id")` is called
- THEN the full insurance dict is returned with nombre, cobertura, prima_base

#### Scenario: get_insurance not found
- GIVEN no insurance matches the ID
- WHEN `get_insurance("nonexistent")` is called
- THEN `None` is returned

### Requirement: Session lifecycle per tool

Each tool SHALL create its own `AsyncSession` via `async_session_maker` using a context manager (`async with`). The session SHALL be closed automatically after the query completes.

#### Scenario: Session acquired and released
- GIVEN a tool is called
- WHEN it queries the database
- THEN an async session is acquired and released after the query
- AND no connection leaks occur
