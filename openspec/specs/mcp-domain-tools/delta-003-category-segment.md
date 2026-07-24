# MCP Domain Tools — Delta Spec: Category × Segment Integration

> **Capability:** `mcp-domain-tools`
> **Change:** `insurance-personalization-by-category`
> **Parent Spec:** `openspec/specs/mcp-domain-tools/spec.md`
> **Date:** 2026-07-23

## Purpose

Extend existing MCP tools with category + segment data from the 500K affiliate dataset. Add a new `load_segment_data` tool for Anna to query aggregate consumption patterns. Enrich `get_customer` output with segment info from the loaded dataset (not DB). Add optional `documento` parameter to `recommend_insurance` for automated category + segment resolution.

## Requirements

### Requirement: `recommend_insurance` optional `documento` parameter

The `recommend_insurance` tool SHALL accept an optional `documento: str | None = None` parameter.

When `documento` is provided:
1. Call `segment_data.lookup_by_documento(documento)` to resolve `categoria` and `segmento`
2. If documento not found in dataset → log warning, continue with profile-only (no category/segment)
3. Call `match_products_by_segment(profile, categoria, segmento)` instead of `match_products(profile)`
4. Include a note in the output: "*Recomendación personalizada para categoría {categoria}*"

When `documento` is not provided:
- Behaves exactly as before: `match_products(profile)` → existing output format

Updated signature:

```python
@mcp.tool()
def recommend_insurance(
    profile: dict,
    documento: str | None = None,
) -> str:
    ...
```

#### Scenario: Documento resolves to categoria A, LAMBDA
- GIVEN `segment_data` loaded with "1234567890" mapping to `categoria="A"`, `segmento="LAMBDA"`
- WHEN `recommend_insurance({"viaja_frecuentemente": True}, "1234567890")` is called
- THEN the result SHALL include "Asistencia Médica Viajes" (R3 conversational match, `confidence: "high"`)
- AND "Seguro de Vida" and "Seguro Hogar" (R8 compound, `confidence: "medium"`)
- AND the output SHALL contain the text "categoría A" somewhere in the response

#### Scenario: Documento not found in dataset
- GIVEN `segment_data.lookup_by_documento("nonexistent")` returns `None`
- WHEN `recommend_insurance(profile, "nonexistent")` is called
- THEN the result SHALL be identical to `recommend_insurance(profile)` without documento
- AND a warning SHALL be logged: `"Documento 'nonexistent' not found in segment data — falling back to conversational rules"`

#### Scenario: Documento not provided (backward compat)
- GIVEN `recommend_insurance` is called without `documento`
- WHEN the function executes
- THEN it SHALL call `match_products(profile)` (original function)
- AND the output format SHALL be identical to the existing behavior
- AND no category/segment notes SHALL appear in the output

#### Scenario: Anonymous user flow via profile
- GIVEN `profile = {"viaja_frecuentemente": True, "categoria_afiliacion": "B"}`
- WHEN `recommend_insurance(profile)` is called without documento
- THEN the function SHALL detect `categoria_afiliacion` in profile
- AND call `match_products_by_segment(profile, "B", None)`
- AND the output SHALL contain "categoría B" note

### Requirement: New `load_segment_data` tool

The system SHALL provide an MCP tool `load_segment_data(documento: str | None = None) -> str` that returns aggregate consumption stats for Anna's conversational context.

```python
@mcp.tool()
async def load_segment_data(documento: str | None = None) -> str:
    """Return aggregate product consumption patterns per segment.
    
    If ``documento`` is provided, returns stats for that member's segment.
    If omitted, returns a summary of all segments.
    """
    ...
```

Output format:
- **Con documento**: "El segmento {segmento_label} (categoría {categoria}) suele comprar: {top_products}. Prima promedio: ${prima_promedio}."
- **Sin documento**: Table of all segments with total affiliates, top 3 products per segment, and average premium.

#### Scenario: Segment data by documento
- GIVEN `segment_data` loaded, documento "1234567890" → `(A, LAMBDA)`
- WHEN `load_segment_data("1234567890")` is called
- THEN the result SHALL contain the segment label for LAMBDA ("sin grupo familiar")
- AND SHALL list the top 3 most-bought product categories for (A, LAMBDA)
- AND SHALL include the average premium for this segment

#### Scenario: Segment data for all segments
- GIVEN `segment_data` loaded
- WHEN `load_segment_data()` is called with no arguments
- THEN the result SHALL contain one row per (categoria, segmento) combination
- AND each row SHALL list total affiliates, top 3 products, and average premium
- AND rows SHALL be sorted by total_affiliates descending

#### Scenario: Segment data unavailable
- GIVEN `segment_data.is_loaded() == False`
- WHEN `load_segment_data()` is called
- THEN the result SHALL be: "Datos de segmentación no disponibles. El archivo CSV no fue cargado."

### Requirement: `get_customer` enriched with segment data

The `get_customer` tool SHALL append segment information from the loaded dataset (not DB) when `segment_data` is loaded and the customer's document is found.

The existing output format SHALL be preserved with an additional line appended:

```
**Segmento familiar:** {segmento_label}
```

Where `segmento_label` maps:
- `LAMBDA` → "Sin grupo familiar"
- `RHO` → "Monoparental"
- `EPSILON` → "Nuclear"
- `IOTA` → "Pareja"
- `CHI`, `THETA`, `PI` → "No especificado"
- `None` → "No disponible"

#### Scenario: Customer found with segment data
- GIVEN a customer with `documento_identidad="1234567890"` exists in DB
- AND `segment_data.lookup_by_documento("1234567890")` returns `{categoria: "A", segmento: "LAMBDA"}`
- WHEN `get_customer("1234567890")` is called
- THEN the existing output fields SHALL all be present (name, doc, email, salary, category, contract, tenure, score)
- AND a new line SHALL be appended: `**Segmento familiar:** Sin grupo familiar`

#### Scenario: Customer found, document not in dataset
- GIVEN a customer exists in DB but is not in the CSV dataset
- WHEN `get_customer("1234567890")` is called
- THEN the output SHALL be the same as before (no segment line)
- AND no error SHALL be raised

#### Scenario: Segment data not loaded
- GIVEN `segment_data.is_loaded() == False`
- WHEN `get_customer("1234567890")` is called
- THEN the output SHALL be the same as before (no segment line)
- AND no warning to the user about missing segment data

### Requirement: Tools integrate with segment_data singleton

Both `load_segment_data()` and the enhanced `recommend_insurance()` SHALL import and use the same `SegmentDataService` singleton instance that was loaded at startup. The import pattern SHALL be:

```python
from app.main import segment_data  # or via app.state / module-level import
```

If `segment_data` is not yet initialized or `is_loaded()` returns `False`, the tools SHALL gracefully fall back to existing behavior with no errors.

#### Scenario: Startup sequence ensures availability
- GIVEN the application started and `SegmentDataService.load()` succeeded
- WHEN any MCP tool accesses the singleton
- THEN `segment_data.is_loaded()` SHALL be `True`

## Dependencies

- `backend/app/services/segment_data.py` — SegmentDataService singleton
- `backend/app/services/recommendation_engine.py` — `match_products_by_segment()` function
- `data-models` — no model changes (segmento is CSV-only)
- `fastmcp-server` — tool registration via `@mcp.tool()` decorator
- `chat-sessions` — profile pre-seed before `recommend_insurance` is called

## Files Affected

| File | Change |
|------|--------|
| `backend/app/tools/domain_tools.py` | `recommend_insurance` +documento param; new `load_segment_data` tool; `get_customer` enriched |
| `backend/app/services/chat.py` | Profile pre-seed from documento → segment_data lookup |
| `backend/app/main.py` | +SegmentDataService import, startup event, app.state assignment |
| `backend/tests/test_domain_tools.py` | +tests for new tools and enriched tools |
| `backend/tests/test_recommendation.py` | +recommend_insurance with documento tests |
