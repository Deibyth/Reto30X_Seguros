# Operator Access Security Specification

## Purpose

Protect the single-company operations surface, integration APIs, credentials, and audit evidence.

## Requirements

### Requirement: Operator Authentication and Authorization

Every Multichannel, Settings, CRM, inbox, dashboard, and human-reply operation MUST require an authenticated operator and MUST enforce the permission required by the operation. The deployment MUST remain single-company and MUST NOT expose tenant selection or tenant-scoped resources.

#### Scenario: Authorized operator
- GIVEN an authenticated operator with the required permission
- WHEN the operator requests a protected operation
- THEN the system MUST perform the operation for the single company

#### Scenario: Missing or insufficient authorization
- GIVEN an anonymous operator or one without the required permission
- WHEN a protected operation is requested
- THEN the system MUST reject it without disclosing protected data or changing state

### Requirement: Scoped Integration API Keys

Integration API keys MUST be accepted only from a designated request header, stored only as non-reversible hashes with a display-safe prefix, compared safely, and restricted to explicit scopes including `messages:reply`, `crm:read`, and `crm:write`.

#### Scenario: Correct scope
- GIVEN a valid key carrying the endpoint's required scope
- WHEN the key is supplied in the designated header
- THEN the request MUST be authorized and its use audited

#### Scenario: Unsafe key placement or scope
- GIVEN a key in a query/body or a header key lacking the required scope
- WHEN the request is evaluated
- THEN the system MUST reject it and MUST NOT execute the operation

### Requirement: Key Issuance, Rotation, and Revocation

Plaintext API keys MUST be disclosed exactly once at issuance. Rotation MUST permit an explicit overlap period, and revocation or overlap expiry MUST prevent subsequent use without invalidating previously committed work.

#### Scenario: Key issuance
- GIVEN an authorized operator creates a key
- WHEN issuance succeeds
- THEN plaintext MUST be returned once and later reads MUST expose only masked metadata

#### Scenario: Rotation and revocation
- GIVEN an old key is rotated or revoked
- WHEN it is used after its allowed validity ends
- THEN authorization MUST fail while the replacement key remains independently usable

### Requirement: Encrypted Channel Secrets

Channel credentials, webhook signing secrets, and Baileys authentication state MUST be encrypted at rest under a deployment-provided master-key reference and MUST NOT appear in logs, audit payloads, metrics, errors, or ordinary API responses.

#### Scenario: Secret persistence
- GIVEN a valid secret submitted by an authorized operator
- WHEN configuration commits
- THEN only encrypted secret material and non-sensitive metadata MUST be persisted

#### Scenario: Missing decryption capability
- GIVEN encrypted configuration cannot be decrypted
- WHEN a channel operation requires it
- THEN the operation MUST fail closed and expose a non-secret diagnostic state

### Requirement: Safe Settings Secret Behavior

Settings reads MUST return presence, health, version, and masked metadata only. An omitted or masked secret on update MUST preserve the current secret; explicit replacement MUST be validated before atomic activation, and deletion MUST require an explicit action.

#### Scenario: Read or non-secret update
- GIVEN a configured channel secret
- WHEN Settings is read or updated without a replacement secret
- THEN plaintext MUST not be returned and the stored secret MUST remain unchanged

#### Scenario: Invalid replacement
- GIVEN an operator submits an invalid replacement secret
- WHEN validation fails
- THEN the prior configuration MUST remain active and unmodified

### Requirement: Security Audit Trail

Authentication outcomes, key lifecycle changes, Settings changes, CRM mutations, ownership changes, manual replays, and human sends MUST produce append-only audit events with actor, action, target, outcome, and timestamp, while excluding secrets and sensitive message bodies.

#### Scenario: Audited mutation
- GIVEN an authorized actor performs a sensitive mutation
- WHEN the mutation succeeds or is denied
- THEN an audit event MUST record the outcome without secret or message-body disclosure

#### Scenario: Audit write failure
- GIVEN a security-sensitive mutation cannot be durably audited
- WHEN commit is attempted
- THEN the mutation MUST fail rather than create unaudited state
