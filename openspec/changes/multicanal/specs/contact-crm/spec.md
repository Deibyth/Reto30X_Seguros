# Contact CRM Specification

## Purpose

Manage lightweight channel contacts and a three-stage, human-assigned CRM without fabricating customer data.

## Requirements

### Requirement: Canonical Contacts and Channel Identities

Unknown channel users MUST create or resolve a lightweight canonical contact. A channel identity MUST be unique by channel connection and provider user identity, and MAY include normalized address metadata. Contacts MUST NOT require business-customer fields.

#### Scenario: First contact
- GIVEN an unknown authenticated provider identity
- WHEN its first text event commits
- THEN one contact and one unique channel identity MUST be created

#### Scenario: Repeated identity
- GIVEN the channel identity already exists
- WHEN another event arrives
- THEN the existing contact MUST be reused without duplicate identity creation

### Requirement: Customer Linking

A contact MAY link to at most one existing Customer through an explicit authorized action. Linking MUST NOT invent required Customer fields or automatically merge contacts solely by display name or address; unlinking MUST preserve chat history.

#### Scenario: Explicit link
- GIVEN an operator selects an existing Customer
- WHEN the contact link commits
- THEN the contact MUST reference that Customer without rewriting either identity

#### Scenario: Invalid or removed link
- GIVEN a missing Customer or concurrent conflicting link
- WHEN mutation is attempted
- THEN it MUST fail without partial linkage; a valid unlink MUST retain messages and CRM history

### Requirement: CRM Stages

Every chat MUST have exactly one stage from `lead`, `payment_pending`, or `sale_closed`, defaulting to `lead`. Stage changes MUST be authorized, idempotent, auditable, and preserve timestamped history; no additional MVP stage is implied.

#### Scenario: Valid transition
- GIVEN an authorized actor and current stage
- WHEN a supported stage mutation with `Idempotency-Key` commits
- THEN the new stage and one history event MUST be recorded

#### Scenario: Invalid or duplicate transition
- GIVEN an unsupported stage or a replayed idempotency key
- WHEN mutation is requested
- THEN invalid input MUST be rejected and a matching replay MUST not add history

### Requirement: Closer Assignment

Closer MUST be a human operator assignment independent of stage. Assignment, transfer, and removal MUST be authorized, idempotent, audited, and MUST NOT itself change `sale_closed` or chat ownership.

#### Scenario: Assign closer
- GIVEN an eligible operator and an authorized CRM writer
- WHEN closer assignment commits
- THEN the chat MUST reference the closer while retaining its stage and ownership

#### Scenario: Concurrent assignment
- GIVEN the assignment changed since the caller's observed version
- WHEN a stale mutation is submitted
- THEN it MUST be rejected without overwriting the newer assignment

### Requirement: Contact and CRM APIs

Authenticated operator/API clients MUST be able to read paginated, filterable contacts and chats according to scope, and authorized writers MUST mutate contact details, Customer links, stages, and closer assignments. Responses MUST use canonical IDs and MUST NOT expose provider identifiers unnecessarily.

#### Scenario: Paginated read
- GIVEN an authorized `crm:read` caller
- WHEN contacts or chats are requested with filters and a page bound
- THEN a deterministic bounded page and continuation metadata MUST be returned

#### Scenario: Unauthorized mutation
- GIVEN a caller lacks `crm:write` or the required operator permission
- WHEN a CRM mutation is attempted
- THEN it MUST be rejected without state or audit-history mutation beyond the denial event
