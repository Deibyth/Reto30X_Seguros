# Archive Report: dashboard

> **Estado:** Completado
> **Fecha de archivo:** 2026-07-17
> **Modo:** openspec
> **Archivado en:** `openspec/changes/archive/2026-07-17-dashboard/`

---

## 1. Cambio

**dashboard** — Dashboard Analítico: Bugfixes, Demo Data & Insurance Panel

## 2. Estado

**Completado** — Sin advertencias. Todos los requisitos implementados, todas las tareas marcadas como completadas.

## 3. Resumen

Se corrigieron 3 bugs del dashboard, se agregó seeding con datos demo vía `--demo-data`, y se implementó el endpoint `/analytics/insurance` + InsurancePanel frontend:

### Bugfixes
- **conversion_rate**: Se eliminó multiplicación ×100 en PipelinePanel (backend ya devuelve %)
- **Trends days**: Se agrega `?days=N` al fetch según tab seleccionado (90d ya funciona correctamente)
- **CreditPanel título**: Cambiado a "Cantidad de Créditos por Destino" para reflejar correctamente los datos de conteo

### Demo data
- Flag `--demo-data` en seed.py que crea ~12-15 solicitudes, sesiones, créditos, conversaciones y pólizas vinculadas a Juan Pérez

### InsurancePanel + endpoint
- `GET /analytics/insurance` con stats de pólizas y reclamos
- InsurancePanel con stat cards + gráficos de cobertura y estado
- Tab "Seguros" en DashboardLayout

### Resultado
Dashboard poblado con datos reales, bugs corregidos, seguros funcional.

## 4. Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `frontend/src/components/dashboard/InsurancePanel.tsx` | Componente de seguros con stat cards y gráficos |
| `frontend/src/components/dashboard/DateRangePicker.tsx` | DateRangePicker compartido para filtros de fecha |

## 5. Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/app/services/analytics.py` | Fix rate, agregado insurance stats, date params |
| `backend/app/routers/analytics.py` | Nuevo endpoint /analytics/insurance, date params |
| `backend/app/seed.py` | Demo data con flag --demo-data |
| `frontend/src/lib/analytics.ts` | fetchTrends(days), fetchInsurance() |
| `frontend/src/components/dashboard/PipelinePanel.tsx` | Bugfix conversion_rate |
| `frontend/src/components/dashboard/TrendsPanel.tsx` | Bugfix days param |
| `frontend/src/components/dashboard/CreditPanel.tsx` | Bugfix título |
| `frontend/src/components/dashboard/DashboardLayout.tsx` | Agregado tab de seguros |

## 6. Artefactos archivados

| Artefacto | Path archivado |
|-----------|----------------|
| Proposal | `openspec/changes/archive/2026-07-17-dashboard/proposal.md` |
| Spec | `openspec/changes/archive/2026-07-17-dashboard/spec.md` |
| Design | `openspec/changes/archive/2026-07-17-dashboard/design.md` |
| Tasks | `openspec/changes/archive/2026-07-17-dashboard/tasks.md` |
| Archive Report | `openspec/changes/archive/2026-07-17-dashboard/archive-report.md` |

## 7. Próximos pasos recomendados

| Prioridad | Acción |
|-----------|--------|
| Media | Agregar pruebas unitarias para los servicios de analytics |
| Media | Período de comparación (period-over-period) en el dashboard |
| Baja | Exportación CSV de datos del dashboard |
| Baja | Conexión WebSocket para actualizaciones en tiempo real |
