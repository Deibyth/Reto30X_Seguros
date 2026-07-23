# Spec: Dashboard — Correcciones y Mejoras

## Requerimientos

### R1 — Bugfix conversion_rate
**Problema:** PipelinePanel muestra "500%" porque backend devuelve ratio decimal (0.05) y frontend multiplica ×100.
**Fix:** Backend ya devuelve porcentaje (5.0) — quitar la multiplicación ×100 en frontend.

### R2 — Bugfix TrendsPanel days param
**Problema:** TrendsPanel no envía `?days=N` al backend, siempre usa default 30 días.
**Fix:** Pasar `days` al fetch en `analytics.ts` según el tab seleccionado.

### R3 — Bugfix CreditPanel título
**Problema:** El chart dice "Monto Promedio por Destino" pero renderiza `count`.
**Fix:** Cambiar a "Cantidad de Créditos por Destino" o renderizar monto promedio real.

### R4 — Datos demo en seed
Crear aplicaciones, créditos y sesiones de ejemplo en seed.py.

### R5 — Panel de Seguros
Endpoint `/analytics/insurance` + InsurancePanel frontend mostrando pólizas activas por tipo.

## What was built

### Bugfixes
- **conversion_rate**: Se eliminó la multiplicación ×100 en PipelinePanel. El backend ya devuelve porcentaje (ej. 5.0), se corrigió el frontend para mostrar el valor directo.
- **Trends days**: Se corrigió el envío del parámetro `days` en el fetch de TrendsPanel. Ahora envía `?days=90` (u otros valores según el tab seleccionado) en lugar de usar siempre el default de 30 días.
- **CreditPanel título**: Se cambió el título a "Cantidad de Créditos por Destino" para reflejar correctamente que el chart renderiza conteo, no promedio.

### Demo data
- Se agregó flag `--demo-data` en seed.py. Al ejecutarlo, se crean ~12-15 solicitudes de crédito, sesiones, conversaciones y pólizas de seguro vinculadas al usuario Juan Pérez.

### InsurancePanel + endpoint
- **Endpoint**: `GET /analytics/insurance` en `routers/analytics.py` que consulta `policies` y `claims` y retorna stats de pólizas activas por tipo de cobertura y estado.
- **InsurancePanel**: Nuevo componente en frontend que muestra stat cards (pólizas activas, reclamos pendientes) y gráficos (cobertura por tipo, estado de reclamos).
- Se agregó un tab "Seguros" en el DashboardLayout.

### Resultado
El dashboard ahora se puebla con datos reales al ejecutar el seed con `--demo-data`, los 3 bugs están corregidos, y el panel de seguros es completamente funcional mostrando datos de pólizas y reclamos.
