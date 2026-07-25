# Delta for Docker Infrastructure

## MODIFIED Requirements

### Requirement: Multiservice Composition

Docker Compose MUST retain backend and frontend services and add one Node 20 Baileys sidecar with explicit health, authenticated backend connectivity, restart behavior, and a single active WhatsApp-session owner. Backend readiness for WhatsApp processing MUST depend on sidecar health without making existing `/chat` depend on it.

(Previously: Compose defined only backend and frontend services.)

#### Scenario: Full multichannel startup
- GIVEN valid deployment configuration
- WHEN the stack starts
- THEN backend, frontend, and one healthy Baileys sidecar MUST run with authenticated internal connectivity

#### Scenario: Sidecar unavailable
- GIVEN Baileys is unhealthy or reconnecting
- WHEN the stack serves traffic
- THEN WhatsApp work MUST remain durable/paused while existing `/chat` and unrelated operations remain available

### Requirement: Persistent Protected State

The existing SQLite volume MUST remain persistent, and Baileys auth state MUST use separate persistent protected storage inaccessible to the frontend and not published as a host endpoint. Ordinary shutdown MUST preserve both; destructive cleanup MAY remove them only through an explicit operator action.

(Previously: Only the SQLite volume was persistent and `clean` removed all volumes.)

#### Scenario: Restart persistence
- GIVEN database and Baileys credentials have committed
- WHEN containers restart without explicit destructive cleanup
- THEN both states MUST remain available without plaintext exposure

#### Scenario: Explicit destructive cleanup
- GIVEN an operator invokes documented destructive cleanup
- WHEN volumes are removed
- THEN the action MUST clearly include loss of channel session state and require re-pairing

## ADDED Requirements

### Requirement: Secret-Safe Container Configuration

Encryption master-key material, integration credentials, Telegram tokens, webhook secrets, QR content, and Baileys auth blobs MUST NOT be embedded in images, committed defaults, command arguments, public ports, or frontend environment variables. Example configuration MUST use placeholders and document required protection.

#### Scenario: Image inspection
- GIVEN built images and rendered non-secret Compose configuration
- WHEN inspected
- THEN no operational secret or auth-state content MUST be present

#### Scenario: Missing required secret
- GIVEN a required secret reference is absent
- WHEN the dependent service starts
- THEN that capability MUST fail closed with a non-secret diagnostic

### Requirement: Rollback Isolation

Operators MUST be able to disable multichannel workers/connections and stop the Baileys sidecar while retaining SQLite, protected auth state, audit records, and the existing backend/frontend `/chat` deployment.

#### Scenario: Multichannel rollback
- GIVEN multichannel causes an operational incident
- WHEN its workers and sidecar are disabled
- THEN no new channel sends MUST occur and existing `/chat` MUST remain deployable

#### Scenario: Re-enable after rollback
- GIVEN retained state is valid and configuration is re-enabled
- WHEN one worker and the sidecar become healthy
- THEN previously acknowledged eligible work MAY resume under normal ownership and idempotency checks
