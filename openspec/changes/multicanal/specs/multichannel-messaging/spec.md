# Multichannel Messaging Specification

## Purpose

Provide provider-neutral, text-only conversations with durable asynchronous processing and delivery.

## Requirements

### Requirement: Canonical Chat and Message Addressing

The system MUST assign an opaque canonical `chat_id` to each chat and canonical IDs to messages. Public clients MUST use canonical IDs; provider identifiers MUST remain adapter-internal. Messages MUST record chat, direction, text type, text, lifecycle status, correlation, and accepted timestamp.

#### Scenario: Canonical normalization
- GIVEN a supported provider text event
- WHEN it is accepted
- THEN one canonical message MUST be associated with one canonical `chat_id`

#### Scenario: Unsupported content
- GIVEN a media or non-text event
- WHEN ingress receives it
- THEN it MUST be rejected or recorded as unsupported without invoking any responder

### Requirement: Durable Ingress Acknowledgement

Ingress MUST commit the normalized identity, chat, message, and work item before returning `202 Accepted`. It MUST NOT invoke an agent, webhook, or provider send before that commit.

#### Scenario: Successful acceptance
- GIVEN a valid authenticated event
- WHEN all ingress records commit
- THEN the endpoint MUST return `202` and processing MAY begin asynchronously

#### Scenario: Commit failure
- GIVEN persistence fails before commit
- WHEN ingress handles the event
- THEN it MUST NOT return `202` or invoke downstream processing

### Requirement: Ingress Deduplication

The system MUST deduplicate each provider event within its channel connection using the provider event identity. Concurrent duplicates MUST resolve to one canonical message and one logical processing outcome.

#### Scenario: Sequential duplicate
- GIVEN an event has already committed
- WHEN the same provider event is received again
- THEN the system MUST acknowledge it without creating or enqueueing a duplicate

#### Scenario: Concurrent duplicate
- GIVEN two transactions accept the same provider event concurrently
- WHEN uniqueness is resolved
- THEN exactly one canonical message and work item MUST remain

### Requirement: Per-Chat Ordering

Accepted inbound work and outbound sends MUST preserve deterministic order within each chat. A blocked earlier item MUST prevent later items from overtaking it, while unrelated chats MAY progress.

#### Scenario: Ordered processing
- GIVEN two accepted messages in one chat
- WHEN the worker processes them
- THEN the earlier accepted message MUST reach its routing boundary first

#### Scenario: Earlier item retry
- GIVEN the first item is retryable and a later item is ready
- WHEN work is claimed
- THEN the later item MUST NOT overtake the first item

### Requirement: Idempotent Outbound Messages

Each enqueueing boundary MUST enforce an idempotency key in its authenticated caller scope. Reuse with the same semantic request MUST return the original result; reuse with different content or target MUST be rejected as a conflict.

#### Scenario: Matching replay
- GIVEN an outbound request previously committed under an idempotency key
- WHEN the identical request is repeated
- THEN the original canonical message MUST be returned without another send

#### Scenario: Conflicting replay
- GIVEN an idempotency key already identifies different content or chat
- WHEN it is reused
- THEN the request MUST fail without changing the original message

### Requirement: Retry, Dead Letter, and Manual Replay

Retryable failures MUST use bounded delayed retries with backoff; permanent failures MUST become terminal; exhausted work MUST enter a visible dead-letter state. Authorized manual replay MUST create an audited new processing cycle without duplicating a successful send.

#### Scenario: Retryable failure
- GIVEN a transient timeout, throttling response, or adapter unavailability
- WHEN an attempt fails below its limit
- THEN a later attempt MUST be scheduled and the failure recorded

#### Scenario: Permanent or exhausted failure
- GIVEN a permanent failure or exhausted retry budget
- WHEN the attempt completes
- THEN the item MUST become dead-lettered and MUST NOT retry automatically

#### Scenario: Safe replay
- GIVEN dead-lettered work has no successful delivery
- WHEN an authorized operator replays it
- THEN a new audited attempt cycle MUST begin without creating a second canonical message

### Requirement: Claims and Stale Recovery

Work claims MUST be atomic, leased, and recoverable after a bounded stale interval. A worker MUST verify claim ownership before committing an outcome; stale workers MUST NOT overwrite a recovered outcome.

#### Scenario: Stale claim recovery
- GIVEN a claimed item exceeds its lease without completion
- WHEN recovery runs
- THEN the item MUST become claimable again without loss

#### Scenario: Late stale worker
- GIVEN another claim completed recovered work
- WHEN the original worker reports late
- THEN its result MUST be rejected and MUST NOT cause another send

### Requirement: Single Active Worker Constraint

The SQLite MVP MUST permit only one active multichannel worker owner. Startup or health MUST fail closed for processing when another live owner exists; multiple-worker coordination is not an MVP behavior.

#### Scenario: Sole worker
- GIVEN no live worker owner exists
- WHEN one worker acquires ownership
- THEN it MAY claim durable work

#### Scenario: Competing worker
- GIVEN a live worker already owns processing
- WHEN another worker starts
- THEN the second MUST NOT claim or deliver work
