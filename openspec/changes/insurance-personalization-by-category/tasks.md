# Tasks: Insurance Personalization by Category + Segment

> **Change:** `insurance-personalization-by-category`
> **Date:** 2026-07-23
> **Total tasks:** 10 (T001–T010)
> **Strict TDD**: RED test → GREEN implementation → REFACTOR for every task

---

## Dependencies

```
T001 (SegmentDataService)
 ├── T002 (main.py startup singleton)
 │    └── T004 (domain_tools with singleton access)
 ├── T003 (engine compound rules) ← no dep on T001 (pure functions)
 │    └── T004 (domain_tools tools + tests)
 │         └── T005 (chat.py hooks + tests)
 │              └── T007 (e2e integration test)
 ├── T006 (seed data) ← no dep on T003/T004
 └── T010 (CSV sample doc)
```

---

## T001 — SegmentDataService + tests

**ID:** T001
**Nombre:** Implementar SegmentDataService con carga CSV, lookup y stats agregadas
**Dependencias:** Ninguna
**Esfuerzo estimado:** L

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/services/segment_data.py` | **Crear** — `SegmentDataService` class |
| `backend/tests/test_segment_data.py` | **Crear** — tests unitarios del loader |
| `backend/.gitignore` | **Modificar** — añadir `Usos_Productos_Afiliados_SIN_ID2.csv` |

### Criterios de aceptación

- [ ] `SegmentDataService(csv_path)` se instancia sin errores. `is_loaded()` = False inicialmente
- [ ] `load()` lee CSV con `csv.DictReader`, construye `documento_index` y `aggregate_index`
- [ ] Normalización de categorías: SIGMA/SIGMA__A → A, PI/PI__B → B, ZETA/ZETA__C → C, MU → MU, otros → MU
- [ ] Segmento vacío/missing → almacenado como `None`
- [ ] `lookup_by_documento("existente")` devuelve `{categoria, segmento, consumos, prima_promedio, edad}`
- [ ] `lookup_by_documento("inexistente")` devuelve `None`
- [ ] `get_aggregate_stats()` devuelve `list[dict]` ordenado por `total_afiliados` desc
- [ ] `get_aggregate_stats(categoria="A", segmento="LAMBDA")` filtra correctamente
- [ ] Archivo no encontrado: log WARNING, `is_loaded()` = False, no exception
- [ ] Columnas faltantes: log WARNING con nombres, `is_loaded()` = False
- [ ] Fila malformada: log WARNING, salta la fila, continúa
- [ ] Logging de progreso cada 100K filas a INFO
- [ ] Todas las queries son read-only (thread-safe por GIL)
- [ ] Singleton pattern: `_instance` module-level + `get_instance()` + `_set_instance()`

### Testing (RED → GREEN)

- `test_load_success` — CSV válido de 3+ rows → is_loaded=True, lookup funciona
- `test_lookup_found` — documento existente → keys correctas en el dict
- `test_lookup_not_found` — documento inexistente → None
- `test_aggregate_all` — sin filtros → lista ordenada por total_afiliados desc
- `test_aggregate_by_categoria` — filtrado por categoría → solo esa categoría
- `test_aggregate_by_segmento` — filtrado por (cat, seg) → un entry
- `test_load_file_not_found` — archivo inexistente → warning, is_loaded=False
- `test_load_corrupt_csv` — CSV corrupto → warning, is_loaded=False
- `test_load_missing_columns` — columnas faltantes → warning, is_loaded=False
- `test_categoria_normalization` — SIGMA→A, PI→B, ZETA→C, MU→MU, UNKNOWN→MU
- `test_empty_segmento` — segmento vacío → None en el dict
- `test_malformed_row_skipped` — fila con count incorrecto → skip + continúa
- `test_concurrent_reads` — múltiples corrutinas leyendo simultáneo → sin race
- `test_get_instance_before_load` — get_instance() antes de _set_instance → None
- `test_singleton_lifecycle` — _set_instance → get_instance() devuelve misma instancia

### CSV de test fixture

Crear `backend/tests/fixtures/segment_data_test.csv` con 5-10 rows que cubran:
- Categorías A, B, C, MU — variantes SIGMA, PI, ZETA para probar normalización
- Segmentos LAMBDA, RHO, EPSILON, IOTA
  - Una fila con segmento vacío
  - Una fila con categoria UNKNOWN

---

## T002 — Integración main.py startup

**ID:** T002
**Nombre:** Inicializar SegmentDataService en el lifespan de FastAPI
**Dependencias:** T001
**Esfuerzo estimado:** S

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/main.py` | **Modificar** — añadir step 7 en lifespan(): SegmentDataService init |

### Criterios de aceptación

- [ ] En `lifespan()`, después de ToolBridge init y antes de ChatService init, se crea `SegmentDataService`
- [ ] `await segment_data.load()` se ejecuta en startup
- [ ] Si `load()` falla (FileNotFoundError, etc.), se captura la excepción, log WARNING, se usa instancia fresca con `is_loaded()` = False
- [ ] `app.state.segment_data` = instancia cargada
- [ ] `_set_instance(segment_data)` se llama para export a sync module-level
- [ ] Singletons accesible desde `from app.services.segment_data import get_instance`
- [ ] Startup sequence loggea: `"SegmentDataService initialized (loaded={is_loaded})"`
- [ ] **Backward compat**: Sin CSV presente, app arranca sin error, loggea WARNING

### Testing (se testea en T007 e2e)

No requiere tests separados — se verifica en T007 (e2e) que la app arranca con y sin CSV.

---

## T003 — Compound rules engine + match_products_by_segment + tests

**ID:** T003
**Nombre:** Implementar SEGMENT_RULES (R8-R13), match_products_by_segment(), merge lógico y segment boost
**Dependencias:** T001 (solo para conocer estructura datos; funciones puras sin import directa)
**Esfuerzo estimado:** L

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/services/recommendation_engine.py` | **Modificar** — +SEGMENT_RULES, +SEGMENT_BOOST, +SEGMENTO_LABELS, +match_products_by_segment(), +helpers de merge |
| `backend/tests/test_recommendation_engine.py` | **Modificar** — +TestCompoundRules, +TestSegmentBoost, +TestMergeConfidence, +TestBackwardCompat |

### Criterios de aceptación

- [ ] `match_products()` permanece **inalterada** (mismo código, misma firma, mismo comportamiento)
- [ ] `SEGMENT_RULES` constante: 6 tuples con (categoria, segmento, products, confidence, reason_template)
- [ ] R8: (A, LAMBDA) → vida + hogar, confidence "medium"
- [ ] R9: (A, RHO) → vida + accidentes, confidence "medium"
- [ ] R10: (A, EPSILON) → vida + hogar, confidence "medium"
- [ ] R11: (B, None/any) → accidentes + movilidad, confidence "medium"
- [ ] R12: (C, None/any) → vida+hogar "high", resto "medium"
- [ ] R13: (None/any, IOTA) → vida + hogar, confidence "medium"
- [ ] `match_products_by_segment({}, None, None)` → mismo resultado que `match_products({})`
- [ ] `match_products_by_segment({}, "MU", None)` → solo R1-R7 (sin compound)
- [ ] `match_products_by_segment({}, "A", "LAMBDA")` con profile vacío → vida + hogar medium
- [ ] Merge: producto coincide en conversational + compound → gana high confidence
- [ ] Merge: producto solo en compound → medium confidence
- [ ] Merge: R1-R7 sin categoria → medium confidence con "(perfil general)"
- [ ] `SEGMENT_BOOST`: LAMBDA → [vida, hogar]; RHO → [vida, accidentes]; EPSILON → [vida, hogar]; IOTA → [vida, hogar]
- [ ] Segment boost **reordena** resultados (nunca excluye): mismos productos, boosteados primero al mismo confidence level
- [ ] `SEGMENTO_LABELS`: mapeo código → label legible
- [ ] R12 special case: vida+hogar confidence "high", resto "medium"
- [ ] match_reason para compound incluye "categoría {categoria}" o "perfil {segmento_label}"
- [ ] match_reason para overlap incluye "alineado con tu categoría"
- [ ] `match_reason` para fallback sin categoria: "(perfil general)"
- [ ] Empty profile siempre → `[]`

### Testing (RED → GREEN)

Añadir clases al archivo `test_recommendation_engine.py` existente:

**TestCompoundRules:**
- `test_r8_a_lambda` — vida + hogar en resultados
- `test_r9_a_rho` — vida + accidentes en resultados
- `test_r10_a_epsilon` — vida + hogar en resultados
- `test_r11_b_any` — accidentes + movilidad en resultados (con B+None)
- `test_r12_c_all_products` — 6 productos en resultados
- `test_r12_c_life_home_high` — vida+hogar confidence "high", resto "medium"
- `test_r13_any_iota` — vida + hogar en resultados (con None+iota y con A+iota)
- `test_mu_fallback` — solo R1-R7, sin compound
- `test_none_categoria` — solo R1-R7
- `test_r11_b_and_rho` — R11 match + R13 no match (B+IOTA no existe → solo R11)

**TestSegmentBoost:**
- `test_boost_reorder_lambda` — boosted products first at same confidence
- `test_boost_never_excludes` — boosted o no, todos los matched están presentes
- `test_no_boost_for_unknown_segment` — CHI/THETA/PI → sin boost

**TestMergeConfidence:**
- `test_conversational_wins` — conversational high + compound medium → high
- `test_compound_only` — sin conversational → medium
- `test_overlap_reason_includes_aligned` — match_reason contiene "alineado"
- `test_compound_reason_contains_category` — "categoría A" en match_reason
- `test_fallback_categoria_medium` — R1-R7 sin categoria → medium + "(perfil general)"

**TestBackwardCompat (añadir a TestMatchProductsEdgeCases existente):**
- `test_match_products_unchanged` — match_products() devuelve mismo resultado que antes
- `test_match_products_empty_still_empty` — match_products({}) → []
- `test_by_segment_no_cat_equals_match` — match_products_by_segment(profile, None, None) == match_products(profile)
- `test_by_segment_empty_still_empty` — match_products_by_segment({}, None, None) → []
- `test_profile_without_categoria_key` — perfil sin "categoria_afiliacion" → R1-R7
- `test_all_existing_tests_pass` — todas las tests de TestMatchProducts, TestRules, TestProductsCatalog, TestQuoteProduct pasan sin cambio

---

## T004 — domain_tools: recommend_insurance con documento, load_segment_data, get_customer enriquecido + tests

**ID:** T004
**Nombre:** Extender MCP tools con soporte categoría/segmento
**Dependencias:** T001 (singleton get_instance), T002 (singleton disponible via main.py), T003 (match_products_by_segment)
**Esfuerzo estimado:** M

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/tools/domain_tools.py` | **Modificar** — `recommend_insurance` +documento param, +`load_segment_data` tool, `get_customer` enriched |
| `backend/tests/test_domain_tools.py` | **Modificar** — tests para tools nuevas y extendidas |

### Criterios de aceptación

#### 4.1 recommend_insurance(profile, documento=None)

- [ ] Firma: `def recommend_insurance(profile: dict, documento: str | None = None) -> str:` (sync)
- [ ] Sin documento → comportamiento actual exacto (`match_products(profile)`)
- [ ] Con documento + encontrado en segment_data → `match_products_by_segment(profile, cat, seg)`
- [ ] Con documento + NO encontrado → log warning + `match_products(profile)`
- [ ] Sin documento + profile con `categoria_afiliacion` → `match_products_by_segment(profile, cat, None)`
- [ ] Sin documento + profile con `salario` (sin categoria) → llama `_calcular_categoria()` internamente, luego `match_products_by_segment()`
- [ ] Output incluye nota: `"*Recomendación personalizada para categoría {categoria}*"` cuando aplica
- [ ] Output sin categoria = formato actual exacto

#### 4.2 load_segment_data(documento=None)

- [ ] Firma: `def load_segment_data(documento: str | None = None) -> str:` (sync)
- [ ] `is_loaded()` = False → retorna `"Datos de segmentación no disponibles. El archivo CSV no fue cargado."`
- [ ] Con documento + encontrado → stats de ese segmento: "El segmento {label} (categoría {cat}) suele comprar: ..."
- [ ] Con documento + NO encontrado → `"No se encontraron datos para el documento '{doc}'."`
- [ ] Sin documento → tabla de todos los segmentos ordenados por total_afiliados desc
- [ ] Top 3 productos más comprados por segmento incluidos en output

#### 4.3 get_customer(documento_identidad) enrich

- [ ] Output existente preservado íntegro
- [ ] Si `segment_data.is_loaded()` AND `lookup_by_documento()` retorna segmento → append `**Segmento familiar:** {label}`
- [ ] Sin segment_data o sin match → output actual exacto (ni una línea extra)

### Testing (RED → GREEN)

Añadir tests al archivo `test_domain_tools.py` existente:

- `test_recommend_insurance_with_documento` — mock lookup devuelve (A, LAMBDA) → categoría A en output
- `test_recommend_insurance_documento_not_found` — mock lookup None → mismo output que sin doc
- `test_recommend_insurance_no_documento` — sin doc → usa match_products (formato actual)
- `test_recommend_insurance_profile_with_categoria` — sin doc pero profile con categoria → usa match_products_by_segment
- `test_recommend_insurance_salario_inference` — profile con salario 2M → infiere A → categoría A en output
- `test_recommend_insurance_empty_profile` — {} + doc → No encontramos productos
- `test_load_segment_data_by_documento` — doc encontrado → texto contiene "categoría" + label segmento
- `test_load_segment_data_all` — sin doc → múltiples segmentos listados
- `test_load_segment_data_not_found` — doc no encontrado → mensaje específico
- `test_load_segment_data_unavailable` — is_loaded=False → "no disponibles"
- `test_get_customer_with_segmento` — segment_data devuelve (A, LAMBDA) → "**Segmento familiar:** Sin grupo familiar"
- `test_get_customer_without_segmento` — segment_data None → sin línea extra
- `test_get_customer_no_csv` — is_loaded=False → sin línea extra, mismo output

---

## T005 — ChatService: profile pre-seed + anonymous salary flow + tests

**ID:** T005
**Nombre:** Hook de pre-seed de profile en chat.py e instrucciones de perfilación sin documento
**Dependencias:** T004 (domain_tools con segment_data)
**Esfuerzo estimado:** M

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/services/chat.py` | **Modificar** — `_update_session_state()` pre-seed hook, `_build_profiling_instructions()` salary section |
| `backend/app/services/segment_data.py` | **Modificar** — exportar `get_instance()` (si no se hizo en T001) |
| `backend/tests/test_chat.py` | **Modificar** — tests para pre-seed y flujo anónimo |

### Criterios de aceptación

#### 5.1 Profile pre-seed en _update_session_state()

- [ ] Cuando Phase 1 incluye tool call `get_customer`, se extrae `documento_identidad` de los args
- [ ] Se llama `get_instance().lookup_by_documento(documento)` — si retorna data, se mergea a `insurance_profile`
- [ ] Pre-seed: `profile["categoria_afiliacion"]` = lookup["categoria"]
- [ ] Pre-seed: `profile["segmento_grupo_familiar"]` = lookup["segmento"]
- [ ] Si lookup retorna None → no se modifica profile
- [ ] Si `insurance_profile` es None → se crea nuevo dict
- [ ] Si ya existían keys en insurance_profile → se preservan, solo se añaden categoria+segmento
- [ ] Error al parsear args (JSONDecodeError, KeyError) → silent catch, no break flow

#### 5.2 Instrucciones de perfilación sin documento

- [ ] En `_build_profiling_instructions()`, para el caso "sin contexto específico" (else branch), se añade sección:
  > **PERFILACIÓN SIN DOCUMENTO:**
  > Si el usuario NO ha proporcionado su número de documento, preguntá por su rango salarial aproximado para determinar su categoría de afiliación.
- [ ] Instrucciones incluyen ejemplos de preguntas naturales sobre salario
- [ ] Anna guarda el salario con `save_form_field(campo="salario", valor=...)`
- [ ] `recommend_insurance()` detecta `salario` en profile y llama `_calcular_categoria()` internamente

### Testing (RED → GREEN)

Añadir/Modificar tests en `test_chat.py`:

- `test_profile_preseed_on_get_customer` — mock Phase 1 con tool_call get_customer → insurance_profile.categoria_afiliacion seteada
- `test_profile_preseed_doc_not_found` — mock lookup None → insurance_profile no modificado
- `test_profile_preseed_preserves_existing` — insurance_profile ya tenía keys → se preservan + nuevas
- `test_profile_preseed_no_get_customer` — tool_call de otra tool → no se toca profile
- `test_anonymous_salary_in_profiling` — `_build_profiling_instructions()` con None → contiene "PERFILACIÓN SIN DOCUMENTO" / "salario"
- `test_profiling_instructions_with_context` — con product_context → no contiene salary section (solo en else branch)

---

## T006 — Seed data actualizado

**ID:** T006
**Nombre:** Actualizar seed.py con datos de categoría y segmento realistas
**Dependencias:** T001 (formato de datos conocido)
**Esfuerzo estimado:** S

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/seed.py` | **Modificar** — añadir categoria_afiliacion variada + datos de segmento consistentes |
| `backend/data/colsubsidio_segments.csv` | **Modificar** — reemplazar agregados con columnas de consumo por categoría×segmento |

### Criterios de aceptación

- [ ] Seed customers tienen distribución realista de categorías (~72% A, ~16% B, ~10% C, ~1% MU)
- [ ] Salarios consistentes con categoría asignada (A ≤ 2 SMMLV, B ≤ 4 SMMLV, C > 4 SMMLV)
- [ ] Segmentos de grupo familiar asignados con distribución cercana a la real (LAMBDA ~57%, RHO ~24%, etc.)
- [ ] CSV de segmentos tiene columnas: documento, categoria, segmento_grupo_familiar, producto_*, prima_promedio, edad
- [ ] CSV tiene al menos 50 filas de datos sintéticos para desarrollo+testing
- [ ] Los seed customers pueden ser encontrados por `get_customer()` y luego enriquecidos por `SegmentDataService`

### Testing

Verificación manual: correr seed, luego verificar que get_customer + lookup_by_documento funcionan con datos seeded.

---

## T007 — Test de integración end-to-end

**ID:** T007
**Nombre:** Test de integración que verifica el flujo completo
**Dependencias:** T001, T002, T003, T004, T005, T006
**Esfuerzo estimado:** M

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/tests/test_integration_segment.py` | **Crear** — test de integración |

### Criterios de aceptación

- [ ] Test que arranca la app con CSV de test → verifica startup exitoso
- [ ] Test que arranca la app sin CSV → verifica warning + graceful degradation
- [ ] `match_products_by_segment()` con (A, LAMBDA) → vida + hogar ambos medium
- [ ] `match_products_by_segment()` con (B, RHO) → accidentes + movilidad
- [ ] `match_products_by_segment()` con (C, EPSILON) → 6 productos, vida+hogar high
- [ ] `match_products_by_segment()` con (MU, LAMBDA) → R1-R7 solamente
- [ ] `recommend_insurance()` con documento válido → include categoría en output
- [ ] `recommend_insurance()` sin documento → formato actual intacto
- [ ] `load_segment_data()` con documento → devuelve stats
- [ ] `load_segment_data()` sin datos → "no disponibles"
- [ ] `get_customer()` con documento en CSV → incluye "**Segmento familiar:**"
- [ ] `get_customer()` con documento fuera de CSV → sin segmento line
- [ ] **Todas las tests existentes de recommendation_engine.py pasan** (regression)
- [ ] **Todas las tests existentes de domain_tools.py pasan** (regression)

---

## T008 — Estilo y formato del output de herramientas

**ID:** T008
**Nombre:** Asegurar formato consistente en outputs de herramientas MCP (post-implementación)
**Dependencias:** T004
**Esfuerzo estimado:** S

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/tools/domain_tools.py` | **Modificar** — revisar formato output de recommend_insurance y load_segment_data |

### Criterios de aceptación

- [ ] `recommend_insurance` con doc: nota de categoría al final, productos listados igual que sin doc
- [ ] `load_segment_data` con doc: formato: "El segmento {label} (categoría {cat}) suele comprar: {top3}. Prima promedio: ${prima}."
- [ ] `load_segment_data` sin doc: tabla markdown-style con header: Segmento | Categoría | Afiliados | Top 3 Productos | Prima Prom.
- [ ] `get_customer` con segmento: "**Segmento familiar:** {label}" al final del output existente
- [ ] Outputs son legibles para Anna (AI), no raw JSON

### Testing

Unit tests ya cubiertos en T004. Esta tarea es de pulido post-implementación.

---

## T009 — Logging y errores

**ID:** T009
**Nombre:** Asegurar logging completo y manejo de errores en todos los componentes
**Dependencias:** T001, T003, T004, T005
**Esfuerzo estimado:** S

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/app/services/segment_data.py` | **Modificar** — verificar logging coverage |
| `backend/app/services/recommendation_engine.py` | **Modificar** — verificar logging coverage |
| `backend/app/tools/domain_tools.py` | **Modificar** — verificar logging coverage |
| `backend/app/services/chat.py` | **Modificar** — verificar logging coverage |

### Criterios de aceptación

- [ ] `segment_data.load()` loggea WARNING si archivo no encontrado
- [ ] `segment_data.load()` loggea WARNING si columnas faltantes
- [ ] `segment_data.load()` loggea WARNING por fila malformada (skip, continue)
- [ ] `segment_data.load()` loggea INFO cada 100K filas
- [ ] `segment_data.load()` loggea INFO al completar con conteo
- [ ] `recommend_insurance()` loggea WARNING si documento no encontrado en dataset
- [ ] `recommend_insurance()` loggea INFO cuando usa match_products_by_segment vs match_products
- [ ] `_update_session_state()` loggea DEBUG cuando pre-seedea profile
- [ ] `chat._build_profiling_instructions()` no requiere logging adicional
- [ ] Sin PII en logs (nunca loggear documento completo ni salario exacto)

---

## T010 — Documentación del formato CSV

**ID:** T010
**Nombre:** Crear archivo sample del CSV con headers documentados
**Dependencias:** T001
**Esfuerzo estimado:** S

### Archivos

| Archivo | Acción |
|---------|--------|
| `backend/data/Usos_Productos_Afiliados_SIN_ID2.sample.csv` | **Crear** — archivo header-only con columnas documentadas |
| `backend/data/colsubsidio_segments.csv` | **Modificar** — si ya existe, actualizar headers para coincidir |

### Criterios de aceptación

- [ ] Archivo `.sample.csv` existe con solo la fila de headers
- [ ] Headers coinciden con los esperados por `SegmentDataService.load()`: documento, categoria, segmento_grupo_familiar, producto_*, prima_promedio, edad
- [ ] Comentario al inicio explica el formato: origen, columnas requeridas, normalización
- [ ] `colsubsidio_segments.csv` actualizado para desarrollo (al menos 50 filas sintéticas con datos coherentes)
- [ ] `.gitignore` ya ignora `Usos_Productos_Afiliados_SIN_ID2.csv` (no el `.sample.csv`)

---

## Resumen de esfuerzo

| Tarea | Esfuerzo | Archivos nuevos | Archivos modificados |
|-------|----------|-----------------|----------------------|
| T001 | L | 2 | 1 |
| T002 | S | 0 | 1 |
| T003 | L | 0 | 2 |
| T004 | M | 0 | 2 |
| T005 | M | 0 | 3 |
| T006 | S | 0 | 2 |
| T007 | M | 1 | 0 |
| T008 | S | 0 | 1 |
| T009 | S | 0 | 4 |
| T010 | S | 1 | 1 |
| **Total** | **3S + 3M + 2L = ~18-22h** | **4** | **17** |

## Guidance para el aplicador

1. Respetar estrictamente el orden: T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010
2. Cada tarea debe seguir RED → GREEN → REFACTOR. Escribir test primero, ver que falle, implementar, ver que pase.
3. No modificar `match_products()` — solo leer. `match_products_by_segment()` es nueva función.
4. Para T003, NO importar SegmentDataService en el engine. `match_products_by_segment()` recibe categoria y segmento como parámetros. Es pura.
5. Para T004, el singleton de segment_data se importa vía `from app.services.segment_data import get_instance` dentro de cada función (no al tope del módulo) para evitar race condition con startup.
6. Las tests de T001 usan un CSV fixture en `tests/fixtures/`. No dependen del archivo real.
7. Las tests de T007 usan `conftest.py` fixtures existentes (`test_client`, `domain_db_maker`).
8. No olvidar actualizar `backend/.gitignore` en T001.
