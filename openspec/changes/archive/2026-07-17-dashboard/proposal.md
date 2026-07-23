# Proposal: Dashboard Analítico — Bugfixes, Demo Data & Insurance Panel

## Intent

Dashboard shows 0 data, has 3 bugs, lacks insurance analytics (core product). Fix, seed, fill.

## Scope

### In Scope
1. **3 bugs**: conversion_rate ×100, Trends days param, CreditPanel title
2. **Demo data** in seed.py: sessions, apps, credits, policies, conversations
3. **Insurance panel**: endpoint + InsurancePanel component
4. **Date filter**: backend params + frontend DateRangePicker
5. **UI polish**: consistent cards, proper empty/loading states

### Out of Scope
CSV export, WebSocket, frontend tests, period comparison

## Capabilities

### New
- `analytics-dashboard`: All panels with bugfixes, demo seeding, date filtering
- `insurance-analytics`: Insurance overview endpoint + component

### Modified
None

## Approach

| # | Change | Detail |
|---|--------|--------|
| 1 | conversion_rate | Remove `* 100` in PipelinePanel (backend returns %) |
| 2 | Trends days | `fetchTrends(days)` sends `?days=` query |
| 3 | CreditPanel title | Fix to "Distribución por Destino" (matches count data) |
| 4 | Seed data | 12–15 applications, sessions, policies, conversations linked to Juan Pérez |
| 5 | /insurance endpoint | `get_insurance_stats()` — policies, claims, coverage stats |
| 6 | InsurancePanel | StatCards + pie chart (coverage) + bar chart (status). New layout tab |
| 7 | Date filter | Backend accepts start/end date; shared DateRangePicker on frontend |

## Affected Areas

| File | Impact | What |
|------|--------|------|
| `backend/app/services/analytics.py` | Modified | Fix rate, add insurance, date params |
| `backend/app/routers/analytics.py` | Modified | Add /insurance endpoint, date params |
| `backend/app/seed.py` | Modified | Demo sessions, apps, credits, policies |
| `frontend/src/lib/analytics.ts` | Modified | fetchTrends(days), fetchInsurance() |
| `frontend/src/components/dashboard/*Panel.tsx` | Modified | fix bugs + UI polish |
| `frontend/src/components/dashboard/InsurancePanel.tsx` | New | Insurance component |
| `frontend/src/components/dashboard/DateRangePicker.tsx` | New | Shared date filter |
| `frontend/src/components/dashboard/DashboardLayout.tsx` | Modified | Add insurance tab |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Seed conflicts with existing data | Low | `--clear` flag available |
| Date filter inconsistency | Low | Single shared DateRangePicker |
| Slow queries on large data | Low | SQLite — index later if needed |

## Rollback Plan

Revert 8 backend + 8 frontend files. If seed corrupts, `python -m app.seed --clear`.

## Dependencies

None (in-repo, insurance needs demo policies from seed — same change).

## Success Criteria

- [ ] Dashboard shows non-zero data after seeding
- [ ] conversion_rate displays correct % (no 500%)
- [ ] TrendsPanel 90d returns 90 days, not 30
- [ ] CreditPanel title matches chart content
- [ ] Insurance panel renders with policy/claims stats
- [ ] DateRangePicker filters apply to all panels
