# Delta for Chat Sessions

> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## ADDED Requirements

### Requirement: Insurance intent tracking

The system SHALL support insurance-specific intent values in `session.ultima_intencion`. Valid ADDITIONAL values SHALL include: `solicitar_seguro`, `info_producto_seguro`, `cotizar_seguro`, `ninguna` (existing). Existing credit intents (`solicitar_credito`, `consultar_producto`, `simular_cuota`) SHALL remain unchanged.

#### Scenario: Insurance intent detected
- GIVEN a session
- WHEN a user message about "quiero un seguro de vida" is processed
- THEN `ultima_intencion` is set to `solicitar_seguro`

#### Scenario: Insurance intent does not affect credit intents
- GIVEN a session with `ultima_intencion="solicitar_credito"`
- WHEN a user message about insurance is processed
- THEN the AI detects `solicitar_seguro`
- AND the session remains in its current state (does not auto-transition to insurance)

## MODIFIED Requirements

### Requirement: State machine tracking — insurance state support

The system SHALL update `session.estado_actual` to reflect the conversation phase. Valid states SHALL include: `inicio`, `recopilando_datos`, `evaluando`, `ofreciendo_producto`, `completado` (credit states), AND `perfilando`, `recomendando`, `cotizando`, `recopilando_datos_seguro`, `completado_seguro` (insurance states).
(Previously: Only credit states existed — inicio, recopilando_datos, evaluando, ofreciendo_producto, completado)

The ChatService SHALL determine state transitions based on the AI's detected intent and the current state domain (credit vs insurance).

#### Scenario: State transitions to insurance states on insurance intent
- GIVEN a session at `estado_actual="inicio"`
- WHEN the AI detects the user wants insurance (intent: `solicitar_seguro`)
- THEN the system updates `estado_actual` to `perfilando`
- AND insurance-specific states become available for subsequent transitions

#### Scenario: Credit state machine unchanged
- GIVEN a session at `estado_actual="recopilando_datos"`
- WHEN the user continues with credit data
- THEN `estado_actual` transitions follow the existing credit flow (→ evaluando → ofreciendo_producto → completado)
- AND insurance states are never entered

### Requirement: History window — unchanged

The system SHALL continue loading the most recent N conversation messages for AI context. N SHALL remain at 20. Insurance messages (profiling questions, recommendation discussions, quoting back-and-forth) SHALL be included in history like any other conversation turn.

#### Scenario: Insurance turns included in history
- GIVEN a session with 15 credit turns + 10 insurance turns
- WHEN a new insurance message is processed
- THEN the latest 20 messages are passed as AI context

### Requirement: Intent tracking — updated valid values

The system SHALL update `session.ultima_intencion` on each message turn. Values SHALL include: `solicitar_credito`, `consultar_producto`, `simular_cuota`, `solicitar_seguro`, `info_producto_seguro`, `cotizar_seguro`, `ninguna`.
(Previously: Values were `solicitar_credito`, `consultar_producto`, `simular_cuota`, `info_seguro`, `ninguna`)

#### Scenario: Insurance intent values tracked per turn
- GIVEN a session
- WHEN a user message about "cuánto cuesta el seguro de hogar" is processed
- THEN `ultima_intencion` is set to `cotizar_seguro`
