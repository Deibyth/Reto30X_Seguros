# Agent Routing and Handoff Specification

## Purpose

Select one default automation route while making human ownership an absolute sending boundary.

## Requirements

### Requirement: Global Default Agent Configuration

The system MUST expose exactly one active global/default automation mode: `internal_agent` or `external_webhook`. External mode MUST reference one configured webhook URL. Per-chat external routes MUST NOT be exposed in the MVP.

#### Scenario: Select internal agent
- GIVEN no chat is human-owned
- WHEN the global mode is `internal_agent`
- THEN newly accepted inbound work MUST route only to the internal agent

#### Scenario: Select external webhook
- GIVEN a validated webhook configuration and no human owner
- WHEN the global mode is `external_webhook`
- THEN newly accepted inbound work MUST route only to that webhook

### Requirement: Deterministic Configuration Boundary

Accepted inbound work MUST retain the configuration version effective at acceptance so a later global mode change cannot reroute it nondeterministically.

#### Scenario: Configuration changes after acceptance
- GIVEN inbound work was accepted under configuration version A
- WHEN the global setting changes to version B before processing
- THEN that work MUST use version A and later work MUST use version B

### Requirement: Strict Human Ownership

A human-owned chat MUST suppress both internal-agent and external-webhook enqueueing and sending. Only its assigned authenticated operator MAY create a human reply until ownership is explicitly released or transferred.

#### Scenario: Inbound while human-owned
- GIVEN a chat is assigned to a human
- WHEN a new inbound message commits
- THEN neither automation route MUST be enqueued or invoked

#### Scenario: Unauthorized human reply
- GIVEN a chat is owned by another operator
- WHEN an unassigned operator attempts to reply
- THEN the reply MUST be rejected without enqueueing

### Requirement: Atomic Takeover and In-Flight Suppression

Ownership changes MUST increment an ownership version and atomically suppress queued automation. Every automation MUST revalidate ownership and version immediately before enqueue and immediately before send; results produced after takeover MUST be discarded.

#### Scenario: Takeover races with generation
- GIVEN automation is generating a reply
- WHEN human takeover commits before outbound enqueue
- THEN the generated reply MUST be discarded and MUST NOT be enqueued

#### Scenario: Takeover races with queued send
- GIVEN an automated reply is queued but no provider send has begun
- WHEN human takeover commits
- THEN the queued reply MUST be cancelled and MUST NOT be sent

#### Scenario: Send already crossed boundary
- GIVEN a provider accepted an automated send before takeover committed
- WHEN takeover completes
- THEN the attempt MUST be recorded as pre-boundary and no further automation MUST occur

### Requirement: Release and Transfer

Ownership release MUST require an explicit operator action and apply automation only to messages accepted after release. Transfer MUST be atomic and MUST preserve continuous human ownership.

#### Scenario: Release ownership
- GIVEN a chat is human-owned
- WHEN its owner explicitly releases it
- THEN subsequent inbound work MAY use the then-current global route, but suppressed work MUST stay suppressed

#### Scenario: Transfer ownership
- GIVEN operator A owns a chat
- WHEN ownership is transferred to operator B
- THEN A MUST lose send authority when B gains it, with no automated interval
