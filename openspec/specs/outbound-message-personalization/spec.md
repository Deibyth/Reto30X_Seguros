# Spec: Outbound Message Personalization

> **Capability:** `outbound-message-personalization`
> **Change:** `proactive-outreach-whatsapp`
> **Date:** 2026-07-23

## Description

AI-powered generation of personalized outbound WhatsApp messages using the existing ChatService (Groq/llama). Takes a customer profile and recommended product, generates a natural warm message, and persists it as `Notification.contenido`.

## Requirements

### Functional

- F-MSG-01: The system SHALL accept a customer profile containing `nombre_completo`, salary range, segment, and recommended product type.
- F-MSG-02: The system SHALL call the existing ChatService (Groq/llama) to generate a natural-language message.
- F-MSG-03: The generated message SHALL be friendly, warm, and build trust — mentioning the specific product by name.
- F-MSG-04: The generated message SHALL NOT ask the customer for data the backend already possesses (e.g., name, ID, salary).
- F-MSG-05: The generated message SHALL be at most 500 characters (WhatsApp-friendly).
- F-MSG-06: The generated message SHALL include an opt-out hint (e.g., "responde STOP para no recibir más mensajes").
- F-MSG-07: The system SHALL persist the generated message as `Notification.contenido`.
- F-MSG-08: If the LLM call times out or fails, the system SHALL fall back to a static template containing the customer's name and product name.

### Non-Functional

- NF-MSG-01: The LLM call SHALL have a configurable timeout (default: 15 seconds).
- NF-MSG-02: The fallback template SHALL be locale-aware (default: Spanish/Colombia).

## Scenarios

### Scenario 1: Successful message generation
**Given** a customer profile with name, salary range, segment, and recommended product
**When** `generate_message(profile)` is called
**Then** the ChatService is invoked with a prompt containing the profile data
**And** the returned message is under 500 characters
**And** the message does not ask for data the backend already has
**And** the message includes an opt-out hint

### Scenario 2: LLM timeout
**Given** the ChatService call exceeds the configured timeout
**When** `generate_message(profile)` is called
**Then** the fallback template is used
**And** the fallback includes the customer's name and product name

### Scenario 3: Message persisted
**Given** a generated message from the LLM or fallback
**When** the outbound pipeline creates a Notification record
**Then** `Notification.contenido` contains the generated message
