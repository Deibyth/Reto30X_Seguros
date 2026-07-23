# Proposal: Fase 2 — Chat IA Real + MCP Domain Tools + Sesiones + Chat UI

## Intent

Replace the echo-stub chat with real AI conversations where the assistant queries products, customers, eligibility, and simulates credits via MCP tools — all persisted in sessions. Unlocks the platform's core value.

## Scope

### In Scope
1. Session management in `POST /chat` — create/load sessions, persist conversation history
2. MCP Domain Tools — `get_products`, `get_customer`, `check_eligibility`, `simulate_credit`, `get_insurance`
3. AI tool-calling loop — tool bridge + execution loop + result injection
4. Real Chat UI — message list, input, typing indicator, auto-scroll

### Out of Scope
Auth, NLP intent classification, PostgreSQL, CI/CD, admin dashboard, file upload

## Capabilities

### New
- `chat-sessions`: Session lifecycle, history loading, conversation persistence
- `mcp-domain-tools`: 5 ORM-backed MCP tools
- `ai-tool-loop`: Tool bridge + execution loop
- `chat-ui`: Chat panel with React Query + framer-motion

### Modified
- `chat-api-stub`: Echo → AI response; `session_id` now required
- `fastmcp-server`: `hello_world` → 5 domain tools; add async ORM; remove stateless constraint

## Approach

1. **Session layer**: `ChatService` class in `app/services/chat.py`. `POST /chat` calls `get_or_create_session()` then `process_message()` — loads history, calls AI, persists, returns.
2. **MCP domain tools**: Use global `async_session_maker` inside tool functions. Tools in `app/tools/domain_tools.py`, imported into `mcp_server.py`.
3. **Tool bridge**: `app/services/tool_bridge.py` reads FastMCP registrations → OpenAI tool schema array. `execute_call()` resolves tool calls by name.
4. **Tool loop**: AI → parse `tool_calls` → execute → append results → second AI call → persist both turns.
5. **Chat UI**: `ChatPanel.tsx` uses `useMutation` for `POST /chat`. `framer-motion` staggered entry. Typing indicator while pending.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/routers/chat.py` | Modified | Real handler with session & AI |
| `backend/app/services/chat.py` | New | ChatService class |
| `backend/app/services/tool_bridge.py` | New | FastMCP → OpenAI converter |
| `backend/app/tools/mcp_server.py` | Modified | Register domain tools |
| `backend/app/tools/domain_tools.py` | New | 5 ORM-backed MCP tools |
| `frontend/src/components/ChatPanel.tsx` | Modified | Placeholder → real UI |
| `frontend/src/lib/api.ts` | Modified | Updated response types |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SiliconFlow latency stalls chat UX | Med | Typing indicator + 30s timeout |
| Tool schema <-> OpenAI schema drift | Low | `tool_bridge.py` auto-derives from registry |

## Rollback

Revert `POST /chat` to echo, revert `ChatPanel.tsx` to placeholder, keep MCP server on `hello_world`. Delete new files; restore modified files to `fundacion-plataforma` baseline.

## Dependencies

`fastmcp`, `openai`, `framer-motion`, `@tanstack/react-query` (all present). SiliconFlow key in `.env`.

## Success Criteria

- [ ] `POST /chat` creates/loads sessions and persists full history
- [ ] AI calls MCP tools and returns tool-informed answers
- [ ] Frontend renders message list with typing indicator and auto-scroll
- [ ] All 5 MCP domain tools return correct ORM data
