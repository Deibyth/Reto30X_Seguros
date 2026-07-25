# Delta for Outbound API

## MODIFIED Requirements

### Requirement: Protected Legacy Outbound Operations

Existing pending-notification polling and sent/responded/failed mutations MUST retain their established routes and response semantics for authorized legacy clients, but MUST require an authenticated, appropriately scoped integration credential. Anonymous access MUST be rejected.

(Previously: Outbound endpoints were internal-only by convention and required no authentication.)

#### Scenario: Authorized legacy poll
- GIVEN a valid legacy integration key with the required scope
- WHEN pending notifications are polled with the existing limit rules
- THEN the existing filtered response contract MUST be returned

#### Scenario: Anonymous legacy mutation
- GIVEN no valid integration credential
- WHEN a legacy status endpoint is called
- THEN the request MUST be rejected and notification state MUST remain unchanged

### Requirement: Incremental Legacy Bridge

Legacy Notification operations MAY be bridged into canonical delivery, but a bridge MUST map each notification at most once and MUST preserve existing IDs/status visibility. Disabling multichannel workers MUST leave the authenticated legacy contract available during rollback.

(Previously: Legacy polling and status mutation operated only on Notification records.)

#### Scenario: Bridge once
- GIVEN an eligible legacy notification has no canonical mapping
- WHEN bridge processing repeats
- THEN at most one canonical outbound message MUST be linked to it

#### Scenario: Rollback
- GIVEN multichannel connections and workers are disabled
- WHEN an authorized legacy client uses the existing API
- THEN the legacy operation MUST remain available without requiring provider identifiers

## ADDED Requirements

### Requirement: Delayed External Reply API

The system MUST expose an authenticated asynchronous reply operation that accepts only canonical `chat_id` and text in its request body and requires `Idempotency-Key` plus a scoped API key in headers. Provider IDs MUST NOT be accepted. The backend MUST resolve the channel destination and return `202` only after the canonical outbound message commits.

#### Scenario: Accepted delayed reply
- GIVEN a valid `messages:reply` key, canonical `chat_id`, text, and new idempotency key
- WHEN the reply is submitted
- THEN one canonical outbound message MUST commit and `202` MUST identify its canonical status resource

#### Scenario: Provider identifier or unknown chat
- GIVEN a request supplies a provider ID or a nonexistent/inaccessible `chat_id`
- WHEN validation runs
- THEN it MUST be rejected without enqueueing or revealing provider mapping

#### Scenario: Reply idempotency
- GIVEN an identical delayed reply already committed under the same caller and key
- WHEN it is repeated
- THEN the original result MUST be returned and no second send MUST occur

### Requirement: Human Ownership Enforcement at Reply API

External delayed replies MUST be rejected while a chat is human-owned and MUST revalidate ownership immediately before enqueue and send.

#### Scenario: Human-owned chat
- GIVEN a canonical chat is human-owned
- WHEN an external delayed reply is submitted
- THEN it MUST be rejected without creating an outbound message

#### Scenario: Ownership race
- GIVEN ownership changes after API validation but before enqueue or send
- WHEN the boundary is revalidated
- THEN the external reply MUST be cancelled or rejected and MUST NOT be sent

### Requirement: Signed External Webhook Delivery

External-mode inbound delivery MUST be asynchronous and include a stable delivery ID, timestamp, canonical chat/message data, and HMAC signature. Signature verification MUST be unambiguous and replay-bounded. Any `2xx` MUST acknowledge delivery only; response bodies MUST always be ignored and MUST never create replies.

#### Scenario: Webhook acknowledgement
- GIVEN a valid signed delivery receives any `2xx` body
- WHEN the attempt completes
- THEN delivery MUST be acknowledged and the body MUST have no behavioral effect

#### Scenario: Timeout or non-success
- GIVEN the webhook times out or returns a retryable status
- WHEN delivery fails
- THEN canonical retry policy MUST apply without blocking original ingress

### Requirement: Webhook SSRF Controls

Webhook configuration and every delivery MUST require HTTPS and an allowed public destination after DNS resolution. Private, loopback, link-local, metadata, disallowed-port, oversized, redirect-escaped, or DNS-rebound destinations MUST be rejected; requests MUST have bounded time and response size.

#### Scenario: Safe destination
- GIVEN a validated HTTPS destination resolves only to permitted public addresses
- WHEN delivery connects to that validated destination
- THEN the bounded signed request MAY be sent

#### Scenario: Redirect or resolution escape
- GIVEN configuration or delivery resolves/redirects to a prohibited address
- WHEN validation occurs
- THEN no request MUST reach that address and the failure MUST be safely recorded
