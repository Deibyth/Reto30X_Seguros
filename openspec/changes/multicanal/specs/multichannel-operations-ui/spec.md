# Multichannel Operations UI Specification

## Purpose

Give operators safe, testable Multichannel, Settings, inbox, CRM, reply, and dashboard workflows.

## Requirements

### Requirement: Protected Navigation

Authenticated operators MUST see top-level Multichannel and Settings navigation only when authorized. Multichannel operations MUST remain distinct from analytics, and existing Chat and Dashboard navigation MUST continue to work.

#### Scenario: Authorized navigation
- GIVEN an authenticated authorized operator
- WHEN the application loads
- THEN permitted Multichannel and Settings destinations MUST be available

#### Scenario: Unauthorized route
- GIVEN the operator lacks access or loses authentication
- WHEN a protected view is opened
- THEN protected content MUST not render and re-authentication or denial MUST be shown

### Requirement: Safe Settings Experience

Settings MUST show connection enabled/health state, masked credential presence, global agent mode, webhook status, and configuration version. It MUST distinguish preserving, replacing, and explicitly deleting a secret and MUST never redisplay plaintext.

#### Scenario: Preserve secret
- GIVEN a masked configured credential
- WHEN an operator changes a non-secret setting and saves
- THEN the credential MUST remain unchanged and success MUST be confirmed

#### Scenario: Failed validation
- GIVEN invalid channel or webhook configuration
- WHEN save is attempted
- THEN field-safe errors MUST appear and the prior active configuration MUST remain represented

### Requirement: Inbox Behavior

The inbox MUST present paginated/filterable chats with channel, contact, stage, closer, owner, last-message time, unread/backlog state, and delivery-failure indicators. Selecting a chat MUST show ordered canonical text history and delivery state.

#### Scenario: Select chat
- GIVEN an authorized operator views the inbox
- WHEN a canonical `chat_id` is selected
- THEN ordered text history and current CRM/ownership state MUST be shown

#### Scenario: Refresh under new activity
- GIVEN messages arrive while a page is open
- WHEN data refreshes
- THEN messages MUST remain ordered and no duplicate row or history item MUST appear

### Requirement: Human Reply Experience

Only the assigned human owner MUST be able to submit a reply. The UI MUST submit canonical `chat_id` with a unique idempotency key, prevent accidental duplicate submission, and display queued, sent, retrying, failed, or cancelled state.

#### Scenario: Human send
- GIVEN the current operator owns the chat
- WHEN text is submitted once
- THEN one canonical outbound message MUST appear immediately as durably queued

#### Scenario: Ownership changed
- GIVEN ownership changes before or during submission
- WHEN the reply response is resolved
- THEN the UI MUST show rejection/cancellation and MUST NOT imply a send occurred

### Requirement: CRM Operations

Authorized operators MUST edit lightweight contact fields, explicitly link/unlink a Customer, change the three supported stages, and assign/transfer/remove a closer with visible conflict handling.

#### Scenario: CRM mutation
- GIVEN current data and valid authorization
- WHEN an edit commits
- THEN the view MUST show the committed value and refreshed audit-relevant state

#### Scenario: Concurrent conflict
- GIVEN another operator changed the same version
- WHEN a stale edit is submitted
- THEN the UI MUST preserve the newer server state and require deliberate retry

### Requirement: Operational Dashboard Metrics

The dashboard MUST incrementally expose at least message volume by channel, processing backlog/dead letters, delivery outcomes, and chat counts by CRM stage. Metrics MUST use canonical records, display their time window, and MUST not expose sensitive message content.

#### Scenario: Metrics render
- GIVEN canonical activity exists in a selected time window
- WHEN the dashboard loads
- THEN the supported aggregates and window MUST be displayed consistently

#### Scenario: Partial metric failure
- GIVEN one metric source is unavailable
- WHEN the dashboard loads
- THEN available metrics MUST remain visible and the unavailable metric MUST show a non-sensitive error state
