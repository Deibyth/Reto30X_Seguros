# Channel Adapters Specification

## Purpose

Connect Telegram and WhatsApp/Baileys through replaceable, provider-isolated text contracts.

## Requirements

### Requirement: Provider-Neutral Adapter Contract

Each adapter MUST authenticate ingress, normalize provider events into the canonical text contract, send canonical outbound text, classify outcomes as success, retryable, or permanent, and report connection health. Provider payloads and identifiers MUST NOT leak into public domain APIs.

#### Scenario: Replaceable transport
- GIVEN a valid adapter event
- WHEN it is normalized
- THEN the core MUST receive the same canonical fields regardless of provider

#### Scenario: Provider failure
- GIVEN a send fails at the provider
- WHEN the adapter reports it
- THEN it MUST return a classified outcome without mutating domain ownership or routing

### Requirement: Telegram Ingress

Telegram ingress MUST validate the configured secret-token header before acceptance and MUST deduplicate using Telegram's update identity within the connection.

#### Scenario: Valid Telegram update
- GIVEN a valid secret token and text update
- WHEN Telegram ingress receives it
- THEN it MUST normalize and durably accept it under the Telegram connection

#### Scenario: Invalid Telegram secret
- GIVEN the secret token is absent or incorrect
- WHEN an update arrives
- THEN it MUST be rejected without persistence or processing

### Requirement: Telegram Outbound

The Telegram adapter MUST resolve the provider destination from canonical chat state, send text only, and map provider acknowledgements and errors to canonical delivery outcomes.

#### Scenario: Telegram send
- GIVEN a queued canonical text message
- WHEN Telegram accepts the send
- THEN the attempt MUST record success and the provider receipt internally

#### Scenario: Telegram error
- GIVEN Telegram throttles or permanently rejects a send
- WHEN the response is mapped
- THEN the attempt MUST be classified for the canonical retry policy

### Requirement: Baileys Sidecar Contract

The Baileys transport MUST run as a Node 20 sidecar, authenticate all backend-sidecar calls, expose normalized text ingress, outbound text send, connection/QR state, and health, and remain replaceable without changing canonical contracts.

#### Scenario: Baileys inbound
- GIVEN the sidecar is authenticated and receives a WhatsApp text event
- WHEN it calls backend ingress
- THEN the backend MUST receive a canonical adapter event and deduplicate it

#### Scenario: Unauthenticated sidecar
- GIVEN a missing, revoked, or incorrectly scoped sidecar credential
- WHEN the sidecar calls ingress or send
- THEN the call MUST be rejected without domain-state change

### Requirement: Baileys Session Lifecycle

Baileys credential updates MUST be durably protected before use, QR content MUST be transient and secret-safe, and reconnect/logout/corruption states MUST be visible without logging auth material. Only one sidecar MAY actively own a WhatsApp session.

#### Scenario: Credential update
- GIVEN Baileys emits updated credentials
- WHEN the sidecar persists them
- THEN the protected state MUST commit before continued session use

#### Scenario: Disconnect or duplicate owner
- GIVEN a logout, corrupt state, or another active owner
- WHEN connection is evaluated
- THEN sends MUST pause and health MUST report a safe actionable state
