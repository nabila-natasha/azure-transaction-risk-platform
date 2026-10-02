# ADR-003: Use Bronze and Silver Data Layers

## Status

Accepted

## Context

The platform receives transaction data through more than one ingestion path.

Batch and simulated streaming data need to converge into a common processing architecture while preserving the original ingested data and providing a controlled data-quality boundary before downstream analytics and machine learning.

## Decision

Use a layered data architecture with Bronze and Silver zones.

### Bronze

Bronze contains the ingested transaction data with minimal transformation. It acts as the landing layer for both batch and streaming ingestion.

### Silver

Silver contains validated and cleaned transaction records that satisfy the project's data-quality rules.

Invalid records are separated into a quarantine area rather than being silently discarded.

## Alternatives Considered

### Single-Layer Data Lake

A single layer would simplify the physical layout but would make it harder to distinguish raw ingestion from validated analytical data.

### Full Multi-Layer Medallion Architecture

A Bronze/Silver/Gold architecture could be used, but the current project's primary requirement is to demonstrate reliable ingestion, validation, feature preparation, and ML processing.

Adding additional layers without a concrete downstream requirement would increase complexity.

## Rationale

The Bronze/Silver design provides a clear quality boundary:

```text
Batch / Streaming
       |
       v
    Bronze
       |
       v
 Data Quality Gate
    /        \
 Valid       Invalid
   |            |
   v            v
Silver      Quarantine
```

This allows both ingestion paths to use the same validation contract.

## Consequences

### Positive

* Preserves ingested data before transformation
* Creates an explicit data-quality boundary
* Allows batch and streaming paths to converge
* Makes invalid records observable through quarantine
* Provides a clean input layer for ML preparation

### Negative

* Requires additional storage
* Requires validation and movement logic
* Bronze data may require lifecycle management in a larger production environment

## Project Evidence

The project implements Bronze ingestion followed by validation and Silver processing. Invalid records are routed to quarantine and are not included in the validated Silver dataset.
