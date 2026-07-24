# Spec: Outbound Prospect Selection

> **Capability:** `outbound-prospect-selection`
> **Change:** `proactive-outreach-whatsapp`
> **Date:** 2026-07-23

## Description

Service that queries Customer data and applies eligibility rules to identify prospects for outbound WhatsApp outreach. The service returns a ranked list of eligible customers with recommended product types (credito/seguro), prioritizing by Opportunity.score when available.

## Requirements

### Functional

- F-PROS-01: The system SHALL query the Customer table and apply all eligibility rules in a single pass.
- F-PROS-02: Customers with `tipo_contrato="indefinido"` SHALL be eligible only if `antiguedad_meses >= 2`.
- F-PROS-03: Customers with `tipo_contrato="fijo"` (fixed-term) SHALL be eligible only if `antiguedad_meses >= 6`.
- F-PROS-04: Customers with any other contract type SHALL be excluded.
- F-PROS-05: Customers SHALL be eligible only if `salario >= 1 SMMLV` (Colombia 2026: ~$1,423,500 COP).
- F-PROS-06: Customers SHALL be eligible only if `score_crediticio` is non-null and above a configurable minimum threshold (default: 0.0, i.e., no negative history).
- F-PROS-07: The system SHALL exclude customers whose existing commitments exceed their income (negative debt margin).
- F-PROS-08: The system SHALL exclude customers who already hold a Policy or Credit for the product being offered.
- F-PROS-09: The system SHALL exclude customers who received a Notification of the same `tipo` in the last N days (configurable, default: 30).
- F-PROS-10: The system SHALL prioritize eligible customers by `Opportunity.score` descending when available.
- F-PROS-11: The system SHALL return a list of `(customer, recommended_product_type)` tuples, where `recommended_product_type` is `"credito"` or `"seguro"`.
- F-PROS-12: The system SHALL return an empty list gracefully when no customers match all criteria.

### Non-Functional

- NF-PROS-01: The selection query SHALL complete within 5 seconds for up to 10,000 customers.
- NF-PROS-02: The service SHALL be stateless — all state lives in the database.

## Scenarios

### Scenario 1: Eligible customer with indefinido contract
**Given** a customer with `tipo_contrato="indefinido"` and `antiguedad_meses=3`
**And** `salario >= 1423500`
**And** `score_crediticio` is non-null and positive
**And** no existing Policy or Credit for the recommended product
**And** no recent Notification in the last 30 days
**When** `select_prospects()` is called
**Then** the customer appears in the eligible list

### Scenario 2: Fixed-term contract below threshold
**Given** a customer with `tipo_contrato="fijo"` and `antiguedad_meses=4`
**When** `select_prospects()` is called
**Then** the customer is excluded

### Scenario 3: Income below SMMLV
**Given** a customer with `salario=1000000` (below 1 SMMLV)
**When** `select_prospects()` is called
**Then** the customer is excluded

### Scenario 4: Already has the product
**Given** a customer who already holds a Policy for the insurance being offered
**When** `select_prospects()` is called
**Then** the customer is excluded from that product recommendation

### Scenario 5: Recently notified
**Given** a customer who received a Notification of the same `tipo` within the last 30 days
**When** `select_prospects()` is called
**Then** the customer is excluded

### Scenario 6: Empty results
**Given** no customers match all eligibility criteria
**When** `select_prospects()` is called
**Then** an empty list is returned

### Scenario 7: Priority by Opportunity score
**Given** multiple eligible customers with Opportunity records
**When** `select_prospects()` returns the list
**Then** customers are ordered by `Opportunity.score` descending

Now let me create all 5 spec files.

<｜DSML｜tool_calls>
<｜DSML｜invoke name="write">
<｜DSML｜parameter name="filePath" string="true">/run/media/deiby7h322/F64C3ADD4C3A97F7/PROJECTS/Reto30X_Credit/openspec/specs/outbound-prospect-selection/spec.md