# Insurance Form Schema Specification

> **Capability:** New — `insurance-form-schema`
> **Change:** `insurance-conversational-flow`
> **Date:** 2026-07-22

## Purpose

Define the `InsuranceFormSchema` contract that structures insurance policy fields and the progressive collection protocol, following the same pattern as the credit FormSchema. The AI uses this schema to collect policy holder data, coverage selections, beneficiary info, and payment method before policy creation.

## Requirements

### Requirement: InsuranceFormSchema contract

The system SHALL define an `InsuranceFormSchema` as an internal JSON structure with four sections. Each field SHALL specify: `nombre`, `tipo` (string|number|date|email|select|boolean), `requerido` (bool), `validaciones` (min/max/pattern/enum), `prompt_question`, and `seccion`. The four sections SHALL be ordered:

| Section | Fields | Required |
|---------|--------|----------|
| Datos del Tomador | nombre, documento, email, telefono, fecha_nacimiento | ALL |
| Cobertura | tipo_cobertura, suma_asegurada, coberturas_adicionales | tipo_cobertura, suma_asegurada |
| Beneficiario | beneficiario_nombre, beneficiario_parentesco | beneficiario_nombre |
| Pago | forma_pago, cuenta_pago, acepta_terminos | forma_pago, acepta_terminos |

#### Scenario: Schema defines all insurance fields
- GIVEN the `InsuranceFormSchema` is loaded
- WHEN inspected
- THEN it contains at least the fields: nombre, documento, email, telefono, fecha_nacimiento, tipo_cobertura, suma_asegurada, beneficiario_nombre, forma_pago, acepta_terminos
- AND each field has `seccion`, `tipo`, `requerido`, `validaciones`, and `prompt_question`

### Requirement: Dynamic schema loading

The system SHALL load `InsuranceFormSchema` when `session.estado_actual` enters `"recopilando_datos_seguro"`. The schema SHALL be loaded from `app/services/insurance_schema.py` — separate from, but structurally identical to, the credit `FormSchema` in `credit_form.py`.

#### Scenario: Schema loaded on insurance state
- GIVEN a session at `estado_actual="cotizando"`
- WHEN the user expresses intent to buy
- THEN the system transitions to `"recopilando_datos_seguro"`
- AND `InsuranceFormSchema` is loaded as the active schema

#### Scenario: Credit schema unaffected
- GIVEN a session at `estado_actual="recopilando_datos"` (credit flow)
- WHEN the system loads the active schema
- THEN the credit `FormSchema` is loaded, NOT `InsuranceFormSchema`

### Requirement: Progressive field collection

The AI SHALL collect fields one at a time, in section order (Datos del Tomador → Cobertura → Beneficiario → Pago). Within each section, required fields SHALL be asked first, then optional fields. The AI SHALL NOT ask multiple fields in a single turn unless clarifying.

#### Scenario: Fields collected sequentially
- GIVEN a session at `estado_actual="recopilando_datos_seguro"`
- WHEN the AI asks for `nombre` and the user responds
- THEN `session.campos_diligenciados` SHALL contain `{"nombre": "Maria Gomez"}`
- AND the AI proceeds to the next field `documento`

#### Scenario: Coverage section follows tomador
- GIVEN all Datos del Tomador fields are collected
- WHEN the AI evaluates completeness
- THEN the AI SHALL begin asking fields from the Cobertura section

### Requirement: Product-specific field variants

Certain InsuranceFormSchema fields SHALL adapt based on the selected product. For example, `suma_asegurada` SHALL show different ranges for Vida vs Mascotas vs Hogar. `tipo_cobertura` SHALL offer product-specific options.

#### Scenario: Suma asegurada adapts to product
- GIVEN a user selected Seguro de Vida
- WHEN the AI asks `suma_asegurada`
- THEN the `prompt_question` suggests ranges: "montos desde $10.000.000 hasta $200.000.000"
- AND the `validaciones.max` reflects the product's max coverage

### Requirement: Optional field skip

If the user explicitly chooses not to provide an optional field, the system SHALL save it as `null` in `campos_diligenciados` and continue.

#### Scenario: User skips optional coberturas_adicionales
- GIVEN the AI asks for optional `coberturas_adicionales`
- WHEN the user says "no quiero coberturas extra"
- THEN `campos_diligenciados["coberturas_adicionales"]` SHALL be `null`
- AND the AI proceeds to the next field

### Requirement: Completeness detection

The AI SHALL track collection progress by comparing collected fields against the `InsuranceFormSchema`. When all REQUIRED fields across all four sections have a non-null value, the AI SHALL summarize and ask for confirmation.

#### Scenario: All required fields complete
- GIVEN `campos_diligenciados` has all required insurance fields populated
- WHEN the last required field is collected
- THEN the AI SHALL present a summary of all collected data
- AND call `create_policy()` on user confirmation

### Requirement: Términos y condiciones acceptance

The `acepta_terminos` boolean field MUST be confirmed by the user before `create_policy()` executes. If the user declines, the session SHALL remain in `"recopilando_datos_seguro"` and the policy SHALL NOT be created.

#### Scenario: Terms accepted
- GIVEN the AI asks "¿Aceptás los términos y condiciones del seguro?"
- WHEN the user responds affirmatively
- THEN `campos_diligenciados["acepta_terminos"]` SHALL be `true`
- AND the system proceeds to confirmation

#### Scenario: Terms declined
- GIVEN the AI presents terms for acceptance
- WHEN the user declines
- THEN `campos_diligenciados["acepta_terminos"]` SHALL NOT be set
- AND the session remains in `"recopilando_datos_seguro"`

## Dependencies

- `chat-sessions` — `session.campos_diligenciados`, `session.estado_actual`
- `insurance-conversational-flow` — state `recopilando_datos_seguro`
- `mcp-domain-tools` — `create_policy()` tool
