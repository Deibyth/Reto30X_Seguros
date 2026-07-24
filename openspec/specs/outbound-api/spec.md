# Spec: Outbound API

> **Capability:** `outbound-api`
> **Change:** `proactive-outreach-whatsapp`
> **Date:** 2026-07-23

## Description

REST endpoints consumed by the WhatsApp bot for outbound messaging. Provides polling for pending notifications, delivery confirmation, response reporting, and failure logging.

## Requirements

### Functional

- F-API-01: The system SHALL expose `GET /api/outbound/pending` returning a list of pending notifications (`tipo="wpp"`, `estado="pendiente"`).
- F-API-02: The `GET /api/outbound/pending` endpoint SHALL support a `limit` query parameter (default: 20, max: 50).
- F-API-03: The `GET /api/outbound/pending` response SHALL contain `notification_id`, `phone`, `content`, and `customer_name` for each item.
- F-API-04: The `GET /api/outbound/pending` endpoint SHALL exclude notifications with `estado` other than `"pendiente"`.
- F-API-05: The system SHALL expose `POST /api/outbound/{id}/sent` to mark a notification as sent.
- F-API-06: The `POST /api/outbound/{id}/sent` endpoint SHALL update `estado` to `"enviado"` and set `sent_at`.
- F-API-07: The system SHALL expose `POST /api/outbound/{id}/responded` to mark that a customer responded.
- F-API-08: The `POST /api/outbound/{id}/responded` endpoint SHALL update `estado` to `"respondido"` and set `responded_at`.
- F-API-09: The system SHALL expose `POST /api/outbound/{id}/failed` to mark delivery failure.
- F-API-10: The `POST /api/outbound/{id}/failed` endpoint SHALL update `estado` to `"fallido"`, log the error in `error_log`, and increment `intento_actual`.
- F-API-11: All mutation endpoints SHALL return 404 if the notification ID does not exist.
- F-API-12: All mutation endpoints SHALL return 200 on success with the updated notification.

### Non-Functional

- NF-API-01: The `GET /api/outbound/pending` endpoint SHALL respond within 500 ms for up to 50 pending notifications.
- NF-API-02: All endpoints SHALL be internal-only (no external auth required, rate-limited by convention).

## Scenarios

### Scenario 1: Poll pending notifications
**Given** 5 notifications with `tipo="wpp"` and `estado="pendiente"`
**When** `GET /api/outbound/pending` is called
**Then** the response contains 5 items
**And** each item has `notification_id`, `phone`, `content`, and `customer_name`

### Scenario 2: Limit parameter
**Given** 30 pending notifications exist
**When** `GET /api/outbound/pending?limit=10` is called
**Then** at most 10 items are returned

### Scenario 3: Mark as sent
**Given** a notification with `id="abc-123"` and `estado="pendiente"`
**When** `POST /api/outbound/abc-123/sent` is called
**Then** `estado` is `"enviado"`
**And** `sent_at` is set

### Scenario 4: Mark as responded
**Given** a notification with `id="abc-123"`
**When** `POST /api/outbound/abc-123/responded` is called
**Then** `estado` is `"respondido"`
**And** `responded_at` is set

### Scenario 5: Mark as failed
**Given** a notification with `id="abc-123"`
**When** `POST /api/outbound/abc-123/failed` is called with `{"error": "timeout"}`
**Then** `estado` is `"fallido"`
**And** `error_log` contains the error
**And** `intento_actual` is incremented

### Scenario 6: Unknown notification
**Given** no notification with `id="nonexistent"`
**When** `POST /api/outbound/nonexistent/sent` is called
**Then** a 404 response is returned
