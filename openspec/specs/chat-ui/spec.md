# Chat UI Specification

> **Capability:** C09 — `chat-ui`
> **Change:** `fase2-chat-ia-mcp`
> **Date:** 2026-07-16

## Purpose

Replace the placeholder ChatPanel with a functional chat interface featuring message list, input, send button, typing indicator, and smooth animations.

## Requirements

### Requirement: ChatPanel component

The system SHALL render a `ChatPanel` component with:
- A scrollable message list displaying user and assistant messages
- An input field with placeholder "Escribí tu mensaje..."
- A send button (disabled while pending)
- Messages styled distinctly by role (user right-aligned, assistant left-aligned)

#### Scenario: Messages rendered by role
- GIVEN a conversation with 2+ messages
- WHEN ChatPanel renders
- THEN each user message appears right-aligned with user styling
- AND each assistant message appears left-aligned with assistant styling

### Requirement: API integration via TanStack Query

The system SHALL use `useMutation` from `@tanstack/react-query` to call `POST /chat`. On success, the response message SHALL be appended to the message list. The mutation SHALL track loading and error states.

#### Scenario: Message sent via mutation
- GIVEN the user types and sends a message
- WHEN the form is submitted
- THEN `useMutation` calls `POST /api/chat`
- AND the user message appears immediately in the list
- AND on success the assistant reply is appended

### Requirement: Typing indicator

While the mutation is pending (`isPending === true`), the system SHALL display a typing indicator (animated dots) below the last user message. The indicator SHALL be replaced by the assistant reply when the mutation resolves.

#### Scenario: Typing dots shown while waiting
- GIVEN a message has been sent
- WHEN the API call is in flight
- THEN a three-dot typing indicator is shown in the assistant slot

### Requirement: Staggered message entry

The system SHALL use `framer-motion` for staggered message entry. Each new message SHALL animate in with a slide-up + fade effect. Consecutive messages from the same role SHALL enter with a shorter delay than role switches.

#### Scenario: New message animates in
- GIVEN a new message is added to the list
- WHEN the list renders
- THEN the message animates in with a slide-up transition
- AND the animation delay varies by position and role

### Requirement: Auto-scroll to bottom

The system SHALL automatically scroll the message list to the bottom when new messages arrive. If the user has scrolled up to read history, auto-scroll SHALL be suppressed until they scroll back to the bottom.

#### Scenario: Auto-scroll on new message
- GIVEN the user is at the bottom of the chat
- WHEN a new message arrives
- THEN the list scrolls to show the latest message

#### Scenario: No auto-scroll when reading history
- GIVEN the user has scrolled up to read older messages
- WHEN a new message arrives
- THEN the viewport does NOT jump to the bottom

### Requirement: Error handling with retry

If the mutation fails, the system SHALL show an error toast or inline error message with a "Reintentar" (Retry) button. Dismissing the error SHALL clear the error state.

#### Scenario: Error shown with retry
- GIVEN the API returns an error
- WHEN the mutation fails
- THEN an error message appears below the input field
- AND a "Reintentar" button re-sends the last message

### Requirement: Responsive layout

The chat panel SHALL be full-width on mobile viewports and constrained to 800px max-width centered on desktop (Tailwind `md:max-w-[800px] md:mx-auto`). The message list SHALL fill available vertical space within its container.

#### Scenario: Mobile full-width
- GIVEN a viewport < 768px wide
- WHEN ChatPanel renders
- THEN the container spans 100% of the viewport width

#### Scenario: Desktop constrained
- GIVEN a viewport >= 768px wide
- WHEN ChatPanel renders
- THEN the container max-width is 800px and centered

### Requirement: Loading skeleton

On first load (before any messages are sent), the system SHALL display a skeleton placeholder with animated pulse indicating the chat interface is ready but empty.

#### Scenario: Skeleton on initial render
- GIVEN the ChatPanel mounts for the first time
- WHEN no messages exist yet
- THEN a skeleton placeholder is shown with a greeting message placeholder
