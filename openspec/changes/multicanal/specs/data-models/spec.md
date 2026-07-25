# Delta for Data Models

## MODIFIED Requirements

### Requirement: Versioned Schema Evolution

The system MUST retain the existing business records while evolving SQLite through ordered, versioned, transactional, and replay-safe migrations. Startup MUST apply pending migrations before workers or channel ingress become active; `create_all()` MUST NOT be treated as sufficient schema evolution.

(Previously: Startup used `Base.metadata.create_all()` and schema migrations were deferred.)

#### Scenario: Upgrade populated database
- GIVEN a database at the previous supported schema version
- WHEN the application starts
- THEN each pending migration MUST apply once and existing records MUST remain readable

#### Scenario: Migration failure or replay
- GIVEN a migration fails or startup repeats after success
- WHEN migration processing runs
- THEN failure MUST prevent worker/ingress activation, while replay MUST not duplicate changes

### Requirement: Existing Model Compatibility

The twelve existing ORM entities, async session behavior, UUID conventions, and existing relationships MUST remain usable. Canonical multichannel records MUST link to existing Session and Customer records when known rather than overloading Conversation, Notification, Opportunity, or Customer.

(Previously: The twelve models were the complete data model and were created directly at startup.)

#### Scenario: Existing workflow
- GIVEN data created by an existing chat or outbound workflow
- WHEN the migrated application reads or writes it
- THEN its established identifiers and relationships MUST continue to work

#### Scenario: Channel-only person
- GIVEN a channel identity lacks required Customer business data
- WHEN it is persisted
- THEN it MUST use a Contact without fabricated Customer fields

## ADDED Requirements

### Requirement: Canonical Multichannel Records

The schema MUST represent channel connections, contacts, channel identities, chats identified by canonical `chat_id`, canonical text messages, delivery attempts, API-key metadata, CRM stage history, closer assignments, ownership versions, idempotency records, work claims, and audit events with enforceable references and lifecycle states.

#### Scenario: Complete accepted event
- GIVEN valid inbound text for an unknown identity
- WHEN ingress commits
- THEN its connection, identity, contact, chat, message, and work references MUST be consistent

#### Scenario: Invalid reference
- GIVEN a record refers to a missing or incompatible parent
- WHEN commit is attempted
- THEN the transaction MUST fail without partial rows

### Requirement: Uniqueness and Concurrency Constraints

The schema MUST enforce provider-event uniqueness per connection, channel-identity uniqueness per connection, scoped idempotency-key uniqueness, one logical processing item per message, monotonic ownership/configuration versions, and at most one active worker owner.

#### Scenario: Duplicate race
- GIVEN concurrent transactions insert the same protected identity
- WHEN both commit
- THEN one MUST win and the other MUST resolve without a duplicate logical outcome

#### Scenario: Stale version
- GIVEN a mutation carries an obsolete ownership or configuration version
- WHEN commit is attempted
- THEN it MUST fail without overwriting current state

### Requirement: Retention-Sensitive Persistence

Retention or deletion operations MUST preserve required audit, idempotency, delivery, and migration evidence while removing or irreversibly redacting expired contact/message content. Redacted records MUST remain non-deliverable and metrics MUST not reconstruct sensitive content.

#### Scenario: Retention expiry
- GIVEN sensitive content has exceeded configured retention
- WHEN retention processing commits
- THEN content MUST be removed or redacted while non-sensitive integrity evidence remains

#### Scenario: Replay after redaction
- GIVEN a redacted message or expired idempotency record is referenced
- WHEN replay or delivery is requested
- THEN the system MUST fail safely rather than reconstruct or resend removed content
