# Design: Dashboard — Correcciones y Mejoras

## Decisiones

1. **Bugfixes**: Solo frontend. Modificar PipelinePanel.tsx, TrendsPanel.tsx, CreditPanel.tsx, analytics.ts
2. **Demo data**: ~30 solicitudes en seed.py con estados variados. Seed opcional vía flag `--demo-data` para no ensuciar prod.
3. **Insurance endpoint**: Endpoint GET `/analytics/insurance` en routers/analytics.py que consulta policies y claims.
4. **InsurancePanel**: Nuevo componente en dashboard/ con stats de pólizas activas.

## Archivos a modificar

| Archivo | Acción |
|---------|--------|
| `frontend/src/components/dashboard/PipelinePanel.tsx` | Modificar |
| `frontend/src/components/dashboard/TrendsPanel.tsx` | Modificar |
| `frontend/src/components/dashboard/CreditPanel.tsx` | Modificar |
| `frontend/src/services/analytics.ts` | Modificar |
| `backend/app/seed.py` | Modificar |
| `backend/app/routers/analytics.py` | Modificar |
| `backend/app/services/analytics.py` | Modificar |
| `frontend/src/components/dashboard/InsurancePanel.tsx` | Nuevo |
| `frontend/src/components/dashboard/DashboardLayout.tsx` | Modificar |
