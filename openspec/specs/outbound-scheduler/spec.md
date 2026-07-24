# Spec: Outbound Scheduler

> **Capability:** `outbound-scheduler`
> **Change:** `proactive-outreach-whatsapp`
> **Date:** 2026-07-23

## Description

APScheduler-based background job that orchestrates the entire outbound pipeline: select prospects, generate personalized messages, and create Notification records. Runs on a configurable interval and handles rate limiting, idempotency, and re-attempt logic.

## Requirements

### Functional

- F-SCHED-01: The scheduler SHALL use APScheduler with an interval trigger, configurable between 15 and 30 minutes (default: 15).
- F-SCHED-02: The job SHALL execute the full pipeline: prospect selection → message generation → Notification creation.
- F-SCHED-03: The job SHALL process at most 50 prospects per run (configurable batch size).
- F-SCHED-04: The job SHALL respect a maximum of 1 outbound message per customer per day.
- F-SCHED-05: The job SHALL skip customers who already have a pending Notification (`estado="pendiente"`).
- F-SCHED-06: The job SHALL identify customers with no response after 5 days and create a re-attempt Notification (`estado="reintento"`), at most 1 re-attempt per customer.
- F-SCHED-07: The scheduler SHALL start when the application lifespan enters and SHALL stop on shutdown.
- F-SCHED-08: If message generation fails for one customer, the job SHALL continue processing the remaining batch.

### Non-Functional

- NF-SCHED-01: The scheduler interval SHALL be configurable via an environment variable (default: 15 minutes).
- NF-SCHED-02: The batch size SHALL be configurable via an environment variable (default: 50).

## Scenarios

### Scenario 1: Full pipeline run
**Given** eligible prospects exist in the database
**When** the scheduler job executes
**Then** prospects are selected
**And** personalized messages are generated
**And** Notification records are created with `estado="pendiente"`

### Scenario 2: Batch size respected
**Given** 100 eligible prospects exist
**When** the scheduler job executes
**Then** at most 50 Notification records are created

### Scenario 3: Idempotency — skip pending
**Given** a customer already has a Notification with `estado="pendiente"`
**When** the scheduler job executes
**Then** that customer is skipped

### Scenario 4: Re-attempt after 5 days
**Given** a customer with a sent Notification and no response after 5 days
**When** the scheduler job executes
**Then** a new Notification is created with `estado="reintento"`
**And** `intento_actual` is incremented

### Scenario 5: Graceful error handling
**Given** message generation fails for one customer in a batch
**When** the scheduler job executes
**Then** the remaining customers are still processed

### Scenario 6: Scheduler lifecycle
**Given** the application starts
**When** the lifespan context enters
**Then** the APScheduler is started with the configured interval
**And** on shutdown, the scheduler is stopped
