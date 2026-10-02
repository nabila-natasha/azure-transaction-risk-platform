# ADR-007: Use a Common Data Quality Gate for Batch and Streaming

## Status

Accepted

## Context

The platform receives transactions through two ingestion paths:

* Historical batch ingestion through Azure Data Factory
* Simulated near-real-time ingestion through Event Hubs

Both paths eventually represent the same type of transaction data.

Applying different validation rules to each path could result in inconsistent data-quality behavior.

## Decision

Use a common Bronze-to-Silver data-quality gate for both ingestion paths.

The validation layer checks the ingested transaction data before it becomes part of the trusted Silver dataset.

Records that satisfy the validation rules are written to Silver.

Invalid records are routed to quarantine for investigation rather than being silently dropped.

## Alternatives Considered

### Separate Validation for Each Ingestion Path

This would allow ingestion-specific logic but could create duplicated rules and inconsistent outcomes.

### Validate Only in the Silver Transformation

This would make the data-quality boundary less explicit and could make invalid records harder to isolate.

## Rationale

Both batch and streaming data converge in Bronze, so the shared Bronze-to-Silver boundary provides a natural location for common validation.

The design is:

```text
Batch --------\
               \
                > Bronze --> Data Quality --> Silver
               /                 |
Streaming ----/                  v
                             Quarantine
```

This keeps ingestion mechanisms separate while standardizing downstream data quality.

## Consequences

### Positive

* Consistent validation rules
* Reusable processing logic
* Common quality contract for both ingestion paths
* Invalid records remain observable
* Easier downstream assumptions about Silver data

### Negative

* The common validation layer becomes a shared dependency
* Streaming and batch-specific edge cases may still require additional logic

## Project Evidence

The project implements Bronze-to-Silver validation and separates invalid records into quarantine. Both batch and simulated streaming transactions converge into this processing path.
