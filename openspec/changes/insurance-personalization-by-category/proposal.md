# Proposal: Insurance Personalization by Category + Segment

## Intent

Insurance recommendations are identical for every member regardless of income level or family composition. With 500K affiliates across 4 categories (72.8% SIGMA/A, 16.4% PI/B, 9.8% ZETA/C) and 6 family segments, recommendations miss the mark: offering premium coberturas to low-income members or basic protection to high-income ones. Personalize by CATEGORIA + SEGMENTO_GRUPO_FAMILIAR using the existing 500K dataset.

## Scope

### In Scope
- Load 500K affiliate dataset into memory at service startup (consumption patterns per segment)
- Enrich `insurance_profile` with `categoria_afiliacion` + `segmento_grupo_familiar` from BD or inferred from salary
- New recommendation rules combining conversational profile × categoria × segmento
- New `load_segment_data` MCP tool for Anna to query segment stats
- Anonymous users: Anna asks salary range to infer categoria via `_calcular_categoria()`
- Mappings: SIGMA→A, PI→B, ZETA→C, MU→"sin categoría"; family segments: LAMBDA=sin grupo familiar, RHO=monoparental, EPSILON=nuclear, IOTA=pareja; CHI/THETA/PI como unknown

### Out of Scope
- ML-based recommendation (deterministic rules only)
- Adding `segmento_grupo_familiar` column to Customer model (CSV-only)
- Adding `D` category to Customer model constraint (MU handled as "sin categoría")
- Real-time dataset refresh (loaded once at startup; restart to reload)
- Multi-product cross-sell optimization (rules are additive, not weighted)

## Capabilities

### New Capabilities
- `segment-data-loader`: Service that loads the 500K CSV/XLSX dataset at startup into an in-memory lookup table. Provides per-segment product consumption stats (most-bought products by categoria × segmento, typical prima ranges). File is gitignored (Colsubsidio-proprietary data).

### Modified Capabilities
- `insurance-recommendation`: Profile enriched with `categoria_afiliacion` + `segmento_grupo_familiar`. New rules table with per-category product weighting and per-segment modifiers. MU category defaults to generic rules. Existing conversational rules remain as fallback.
- `mcp-domain-tools`: `get_customer` returns `segmento_grupo_familiar` from loaded dataset (not DB). New `load_segment_data(documento?)` tool returns per-segment consumption patterns for Anna's context. `recommend_insurance` now also accepts `documento` to auto-resolve categoria + segmento.
- `chat-sessions`: When customer is found by documento, `insurance_profile` is pre-seeded with categoria + segmento before profiling begins.
- `insurance-conversational-flow`: Profiling instructions updated — Anna asks salary range when no documento provided. Profile building enriched with segment-aware suggestions.
- `data-models`: No model changes (categoria exists; segmento is CSV-only). Dataset format documented in comments.

## Approach

1. **Data loader**: New `SegmentDataService` singleton loads the 500K CSV at FastAPI startup. Builds dicts: `{documento: {categoria, segmento, consumo_productos}}` and aggregate stats `{(categoria, segmento): [product_counts]}`.
2. **Profile enrichment** in `chat.py`: After `get_customer()` resolves documento, merge `categoria_afiliacion` + `segmento_grupo_familiar` into `insurance_profile`. If no documento, Anna asks salary range → `_calcular_categoria()`.
3. **New rules** in `recommendation_engine.py`: Compound rule format: `(category, segment, conversational_predicate) → product_id`. Pre-check category for MU = generic fallback. Conversational rules (R1-R7) weakened to medium confidence when no categoria available.
4. **MCP tools**: `recommend_insurance` gains optional `documento` param. `load_segment_data` exposes aggregate consumption for Anna's conversational context.
5. **Backward compat**: Empty profile still returns `[]`. Missing categoria/segmento falls back to existing R1-R7 rules.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/services/recommendation_engine.py` | Modified | New rules table with category × segment × conversational predicates |
| `backend/app/services/segment_data.py` | New | SegmentDataService — loader + lookup from 500K CSV |
| `backend/app/services/chat.py` | Modified | Profile pre-seed from documento lookup; salary-range profiling |
| `backend/app/tools/domain_tools.py` | Modified | `recommend_insurance` optional `documento` param; new `load_segment_data` tool; `get_customer` enriched |
| `backend/app/seed.py` | Modified | Seed customers with realistic categoria + matching segment data |
| `backend/data/colsubsidio_segments.csv` | Modified | Add categoria × segmento consumption columns (replaces old aggregate) |
| `backend/tests/test_recommendation.py` | New | Categoria-aware rules, segment-aware rules, edge cases |
| `backend/tests/test_segment_data.py` | New | Loader, queries, empty dataset edge case |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| 500K CSV not yet available in repo | Med | Design loader to fail gracefully; service runs without it using conversational-only fallback |
| MU (1%) produces noisy recs | Low | MU = generic fallback, no special handling |
| Categoria × segmento rules produce empty results | Low | Fall through to conversational R1-R7 rules as safety net |
| CSV loading at startup slows boot | Low | Load async, ~1s for 500K rows; cache aggressively |

## Rollback Plan

Remove `segment_data.py`, revert `recommendation_engine.py` rules to R1-R7 only, remove optional `documento` param from `recommend_insurance`. All existing conversational rules remain unchanged — just lose the personalization layer.

## Dependencies

- 500K affiliate dataset CSV/XLSX (Colsubsidio-provided; format documented but file gitignored)
- Existing `_calcular_categoria(salario)` function (used for anonymous users)
- Existing `get_customer()` MCP tool (documento → categoria)
- Existing `insurance_profile` JSON field on Session model

## Success Criteria

- [ ] Profile with `categoria=A, segmento_familiar=LAMBDA` recommends Vida + Hogar before Viajes
- [ ] Profile with `categoria=B, segmento_familiar=RHO` recommends Accidentes + Movilidad
- [ ] Profile with `categoria=C` recommends premium tiers (cobertura completa)
- [ ] Profile without categoria falls back to existing R1-R7 rules
- [ ] Anonymous user asked salary range → `_calcular_categoria()` → personalized recs
- [ ] Consumer dataset loads at startup without crashing; missing file = log warning + no-op
- [ ] All existing insurance tests pass unchanged
