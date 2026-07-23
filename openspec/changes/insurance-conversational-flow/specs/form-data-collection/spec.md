# Delta for Form Data Collection

> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## ADDED Requirements

### Requirement: Schema type awareness

The system SHALL support a `schema_type` parameter in the schema loader to distinguish credit vs insurance schemas. The loader SHALL return the correct `FormSchema` or `InsuranceFormSchema` based on the session's current `estado_actual`. Credit states load `credit_form.py` schema; `"recopilando_datos_seguro"` loads `insurance_schema.py` schema.

#### Scenario: Schema loaded by session state
- GIVEN a session at `estado_actual="recopilando_datos"`
- WHEN the schema loader is invoked
- THEN the credit `FormSchema` from `credit_form.py` is returned

- GIVEN a session at `estado_actual="recopilando_datos_seguro"`
- WHEN the schema loader is invoked
- THEN the `InsuranceFormSchema` from `insurance_schema.py` is returned

### Requirement: Combined completeness check

The completeness checker SHALL consider the active schema type when evaluating which fields are required. It SHALL NOT mix credit and insurance fields — completeness is scoped to the currently active schema.

#### Scenario: Insurance completeness isolated from credit
- GIVEN a session with `campos_diligenciados` containing insurance fields only
- WHEN completeness is evaluated for `estado_actual="recopilando_datos_seguro"`
- THEN only `InsuranceFormSchema` required fields are checked
- AND credit-specific fields (salario, monto_solicitado, etc.) SHALL be ignored

## MODIFIED Requirements

### Requirement: Confirmation triggers `create_application` or `create_policy`

When the user confirms, the system SHALL call the appropriate creation tool based on `schema_type`: `create_application()` for credit or `create_policy()` for insurance. Both tools SHALL create their respective records in an atomic transaction. After success, `session.campos_diligenciados` SHALL be cleared and `session.estado_actual` SHALL become `"completado"` or `"completado_seguro"` respectively.
(Previously: Only `create_application()` existed for credit)

#### Scenario: Insurance confirmation calls create_policy
- GIVEN all InsuranceFormSchema required fields are collected and the user confirms
- WHEN the schema type is insurance
- THEN `create_policy()` is called with the form data
- AND `session.estado_actual` becomes `"completado_seguro"`

#### Scenario: Credit confirmation remains unchanged
- GIVEN all credit FormSchema required fields are collected and the user confirms
- WHEN the schema type is credit
- THEN `create_application()` is called as before
- AND `session.estado_actual` becomes `"completado"`
