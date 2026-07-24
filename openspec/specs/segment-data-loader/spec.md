# Segment Data Loader Specification

> **Capability:** New — `segment-data-loader`
> **Change:** `insurance-personalization-by-category`
> **Date:** 2026-07-23

## Purpose

Load the 500K affiliate dataset (`Usos_Productos_Afiliados_SIN_ID2.csv`) into memory at service startup, providing fast lookup by `documento` for category + segment resolution, and aggregate consumption stats by `(categoria, segmento)` for recommendation engine use. The dataset is Colsubsidio-proprietary and gitignored; the service degrades gracefully when the file is absent.

## Terminology

| Term | Definition |
|------|------------|
| Documento | Affiliate identity document number (unique key in CSV) |
| Categoria | Affiliate income category: A (SIGMA), B (PI), C (ZETA), or MU ("sin categoría") |
| Segmento | Family group segment: LAMBDA (sin grupo familiar), RHO (monoparental), EPSILON (nuclear), IOTA (pareja), CHI/THETA/PI (unknown) |
| Product consumption | Count of purchases per product category (drogueria, seguros, etc.) for this affiliate |
| Aggregate stats | Summed/frequency data per (categoria, segmento) tuple — never raw PII |

## CSV Format

File: `backend/data/Usos_Productos_Afiliados_SIN_ID2.csv`

Required columns (case-insensitive header matching):

| Column | Type | Description |
|--------|------|-------------|
| `documento` | string | Unique affiliate ID. Leading zeros preserved. |
| `categoria` | string | One of: `A`, `B`, `C`, `MU`. Mapped from SIGMA/SIGMA__A→A, PI/PI__B→B, ZETA/ZETA__C→C, MU→MU. |
| `segmento_grupo_familiar` | string | One of: `LAMBDA`, `RHO`, `EPSILON`, `IOTA`, `CHI`, `THETA`, `PI`. |
| `producto_*` | integer | One column per product category (e.g., `producto_drogueria`, `producto_seguros`). Value = count of purchases. |
| `prima_promedio` | float | Average premium/amount spent (nullable). |
| `edad` | integer | Affiliate age (nullable). |
| `salario` | float | Affiliate salary (nullable). |

The file SHALL be gitignored (`.gitignore`) as it contains Colsubsidio-proprietary data. A sample header row SHALL be documented in a `.sample` file or in this spec only; actual data SHALL NOT be committed.

## Requirements

### Requirement: SegmentDataService singleton

The system SHALL provide a `SegmentDataService` class at `backend/app/services/segment_data.py`. It SHALL:

1. Be a plain class (not a FastAPI dependency) — instantiated once at application startup
2. Accept an optional `csv_path: str` parameter (default: `"backend/data/Usos_Productos_Afiliados_SIN_ID2.csv"`)
3. Provide a `load()` async method that reads the CSV file and builds in-memory lookup structures
4. Provide synchronous query methods for lookup and aggregate stats
5. Log a warning and become a no-op if the CSV file does not exist or cannot be parsed

```python
class SegmentDataService:
    def __init__(self, csv_path: str = "backend/data/Usos_Productos_Afiliados_SIN_ID2.csv"):
        ...

    async def load(self) -> None:
        """Parse CSV, build lookup dicts. Log warning if file missing."""
        ...

    def lookup_by_documento(self, documento: str) -> dict | None:
        """Return {categoria, segmento, consumos, prima_promedio, edad} or None."""
        ...

    def get_aggregate_stats(
        self, categoria: str | None = None, segmento: str | None = None
    ) -> list[dict]:
        """Return aggregate consumption stats filtered by categoria/segmento."""
        ...

    def is_loaded(self) -> bool:
        """Return True if data was loaded successfully."""
        ...
```

#### Scenario: CSV loads successfully
- GIVEN a valid CSV file exists at the configured path with 500K rows
- WHEN `load()` is called
- THEN `is_loaded()` SHALL return `True`
- AND `lookup_by_documento("123456")` SHALL return a dict for that document
- AND `get_aggregate_stats()` SHALL return aggregated stats across all segments

#### Scenario: CSV file not found
- GIVEN no CSV file exists at the configured path
- WHEN `load()` is called
- THEN a warning SHALL be logged: `"Segment data CSV not found at {path} — running without segment personalization"`
- AND `is_loaded()` SHALL return `False`
- AND `lookup_by_documento(...)` SHALL return `None`
- AND `get_aggregate_stats(...)` SHALL return `[]`
- AND no exception SHALL be raised

#### Scenario: CSV has inconsistent data (missing columns)
- GIVEN a CSV file with some required columns missing
- WHEN `load()` is called
- THEN a warning SHALL be logged with details of missing columns
- AND `is_loaded()` SHALL return `False`
- AND the service SHALL degrade gracefully (same as file-not-found behavior)

#### Scenario: Singleton lifecycle
- GIVEN a `SegmentDataService` instance created at startup
- WHEN `load()` completes
- THEN the same instance SHALL be reused across all requests (singleton)
- AND `load()` SHALL NOT be called again during the service lifetime

### Requirement: In-memory lookup structures

After `load()` completes, the service SHALL build two lookup structures:

1. **Documento index**: `dict[str, dict]` — maps `documento` → `{categoria, segmento, consumos: dict[str, int], prima_promedio: float | None, edad: int | None}`
2. **Aggregate index**: `dict[tuple[str, str], dict]` — maps `(categoria, segmento)` → `{total_afiliados, producto_counts: dict[str, int], prima_promedio: float}`

The aggregate index SHALL be computed as:
- Group all rows by `(categoria, segmento)`
- Count total affiliates per group
- Sum product counts per group (so we know "drogueria was bought 45K times by A+LAMBDA")
- Average `prima_promedio` per group

#### Scenario: Documento lookup returns expected shape
- GIVEN `load()` completed successfully
- WHEN `lookup_by_documento("100000001")` is called and the document exists
- THEN the return dict SHALL have keys: `categoria`, `segmento`, `consumos`, `prima_promedio`, `edad`
- AND `categoria` SHALL be one of `"A"`, `"B"`, `"C"`
- AND `segmento` SHALL be one of `"LAMBDA"`, `"RHO"`, `"EPSILON"`, `"IOTA"`, `"CHI"`, `"THETA"`, `"PI"`
- AND `consumos` SHALL be a dict of `{product_category: count}` (e.g., `{"drogueria": 12, "seguros": 3}`)

#### Scenario: Documento not found
- GIVEN `load()` completed successfully
- WHEN `lookup_by_documento("nonexistent")` is called
- THEN the result SHALL be `None`

#### Scenario: Aggregate stats by specific segment
- GIVEN `load()` completed successfully
- WHEN `get_aggregate_stats(categoria="A", segmento="LAMBDA")` is called
- THEN the result SHALL be a list with at most one entry for the (A, LAMBDA) group
- AND the entry SHALL include `total_afiliados`, `producto_counts`, `prima_promedio`
- AND the entry SHALL NOT include `documento` or any PII

#### Scenario: Aggregate stats all segments
- GIVEN `load()` completed successfully
- WHEN `get_aggregate_stats()` is called with no filters
- THEN the result SHALL be a list of dicts — one per (categoria, segmento) combination present in the data
- AND the result SHALL be sorted by `total_afiliados` descending

### Requirement: Integration with FastAPI lifecycle

The `SegmentDataService` SHALL be created and loaded once at application startup, attached to `app.state` or as a module-level singleton.

In `backend/app/main.py` (or equivalent startup):

```python
from app.services.segment_data import SegmentDataService

segment_data = SegmentDataService()

@app.on_event("startup")
async def startup():
    await segment_data.load()
    app.state.segment_data = segment_data
```

Other services access it via `app.state.segment_data` or a shared import.

#### Scenario: Available via app state
- GIVEN the application has started
- WHEN any service reads `app.state.segment_data`
- THEN it SHALL be the `SegmentDataService` instance
- AND `is_loaded()` SHALL reflect whether the CSV was successfully loaded

#### Scenario: Graceful shutdown
- GIVEN the application is shutting down
- WHEN no explicit cleanup is needed (in-memory only)
- THEN the service SHALL require no explicit teardown

### Requirement: Thread safety

The in-memory dicts SHALL be built once during `load()` and never mutated afterward. All query methods SHALL be read-only. This ensures thread safety without locks:
- Documento index: built once, never modified → safe for concurrent reads
- Aggregate index: built once, never modified → safe for concurrent reads

#### Scenario: Concurrent reads safe
- GIVEN `load()` completed
- WHEN multiple coroutines call `lookup_by_documento()` simultaneously
- THEN all calls SHALL succeed without race conditions

### Requirement: CSV mapping normalization

On load, the service SHALL normalize the `categoria` column:

| Source value | Normalized |
|-------------|------------|
| `SIGMA`, `SIGMA__A` | `A` |
| `PI`, `PI__B` | `B` |
| `ZETA`, `ZETA__C` | `C` |
| `MU` | `MU` ("sin categoría") |
| Any other | `MU` (treated as "sin categoría") |

The `segmento_grupo_familiar` column SHALL be normalized to uppercase and used as-is. Empty or missing segmento SHALL be treated as `None`.

#### Scenario: SIGMA mapped to A
- GIVEN a CSV row with `categoria = "SIGMA__A"`
- WHEN `load()` processes the row
- THEN the documento index stores `categoria = "A"`

#### Scenario: Unknown categoria mapped to MU
- GIVEN a CSV row with `categoria = "UNKNOWN"`
- WHEN `load()` processes the row
- THEN the documento index stores `categoria = "MU"`

### Requirement: Memory and performance

Loading 500K rows SHALL:
- Complete within 3 seconds on typical hardware (single-threaded)
- Use no more than 500MB of RAM (estimate: ~1KB per row for dict overhead)
- Use `csv.DictReader` from stdlib (no pandas dependency)
- Log progress every 100K rows at INFO level

#### Scenario: Large CSV within limits
- GIVEN a 500K-row CSV file
- WHEN `load()` is called
- THEN it SHALL complete within 3 seconds
- AND the process RSS SHALL remain under 500MB above baseline

## Dependencies

- Python `csv` stdlib module (no new dependencies)
- `backend/data/Usos_Productos_Afiliados_SIN_ID2.csv` — gitignored, Colsubsidio-proprietary
- `data-models` — no model changes; segmento is CSV-only
- `insurance-recommendation` — consumes aggregate stats for compound rules
- `mcp-domain-tools` — `get_customer` enriched, `load_segment_data` tool exposed
- `chat-sessions` — profile pre-seed from documento lookup

## Rollback

Remove `backend/app/services/segment_data.py`, revert `recommend_insurance` signature, remove `load_segment_data` MCP tool. The recommendation engine falls through to R1-R7 only.

## Files Affected

| File | Change |
|------|--------|
| `backend/app/services/segment_data.py` | New — SegmentDataService class |
| `backend/app/main.py` | +SegmentDataService import, startup event, app.state assignment |
| `backend/app/services/recommendation_engine.py` | Import segment_data, compound rules |
| `backend/app/tools/domain_tools.py` | +load_segment_data tool, get_customer enriched |
| `backend/app/services/chat.py` | Profile pre-seed from documento → segment_data lookup |
| `backend/tests/test_segment_data.py` | New — loader, queries, empty dataset tests |
| `backend/.gitignore` | +`Usos_Productos_Afiliados_SIN_ID2.csv` |
