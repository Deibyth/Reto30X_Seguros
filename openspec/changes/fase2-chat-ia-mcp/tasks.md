# Tasks: Fase 2 — Chat IA Real + MCP Domain Tools + Sesiones + Chat UI

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 400–550 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Backend → PR 2: Frontend |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend: services + tools + router | PR 1 | N/A (no test runner) | `uvicorn app.main:app` + curl POST /chat | Revert routers/chat.py; delete services/* |
| 2 | Frontend: ChatPanel + API types | PR 2 | N/A (no test runner) | `npm run dev` + send message | Revert ChatPanel.tsx, api.ts |

## Phase 1: Services (C06 + C08)

- [ ] 1.1 Create `backend/app/services/__init__.py` + `backend/app/services/tool_bridge.py` — ToolBridge class: `get_openai_tools()` (auto-derives from `mcp._tool_manager`), `execute_tool(name, args)` (resolves by name, raises ValueError if unknown)
- [ ] 1.2 Create `backend/app/services/chat.py` — ChatService(session_maker, ai_client, tool_bridge): `get_or_create_session()`, `load_history(limit=20)`, `persist_turn()`, `process_message()` with two-phase tool loop (AI→tool_calls→ToolBridge→Phase2), session state updates, 30s timeout guard

## Phase 2: Domain Tools (C07)

- [ ] 2.1 Create `backend/app/tools/domain_tools.py` — 5 `@mcp.tool()` fns each with own `async_session_maker` context: `get_products(tipo=None)`, `get_customer(documento_identidad)`, `check_eligibility(customer_id)` (salary≥1M, contract type, tenure≥6mo), `simulate_credit(monto, plazo)` (fixed 18% annual), `get_insurance(insurance_id)`. Return formatted strings as per design
- [ ] 2.2 Update `backend/app/tools/mcp_server.py` — import `domain_tools` module (register tools automatically via decorator), keep `hello_world` for backward compat

## Phase 3: Router Integration (C06 modified — C03)

- [ ] 3.1 Update `backend/app/routers/chat.py` — import and wire ChatService: create session if no `X-Session-Id`, load existing by ID (404 if missing), inject history into AI context, call `process_message()`, persist user+assistant turns, return `ChatResult` with `model` field

## Phase 4: Frontend (C09)

- [ ] 4.1 Rewrite `frontend/src/components/chat/ChatPanel.tsx` — scrollable message list (role-styled), input with placeholder, send button disabled while pending, `useMutation` for POST /chat, framer-motion staggered entry, typing indicator (animated dots), auto-scroll with suppression on history read, error banner with "Reintentar" button, responsive layout (full-width mobile / 800px max desktop), skeleton on first load
- [ ] 4.2 Update `frontend/src/lib/api.ts` — add `model: string` to `ChatResponse`, ensure `X-Session-Id` header management persists across messages

## Verification

Manual check per spec scenarios: POST /chat creates session, loads history, tool calls succeed, frontend renders messages with typing indicator and retry. No test runner — skip automated tests.
