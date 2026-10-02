# ADR-001: Use Azure Data Factory for Batch Ingestion

## Status

Accepted

## Context

The platform needs to ingest a large historical transaction dataset into Azure Data Lake Storage Gen2 for downstream data processing and machine learning.

The historical dataset is batch-oriented rather than continuously generated. The ingestion process therefore requires orchestration of a controlled batch movement of data into the data lake.

The ingestion mechanism should also remain separate from downstream transformation and data-quality processing.

## Decision

Use Azure Data Factory (ADF) for historical batch ingestion.

ADF is responsible for orchestrating the movement of the historical transaction data into the Bronze layer of Azure Data Lake Storage Gen2.

## Alternatives Considered

### Python or Azure CLI Ingestion

A Python- or CLI-based process could upload the files directly, but this would place more orchestration responsibility on custom code.

### Event Hubs

Event Hubs is better suited to event-oriented ingestion and replay scenarios rather than the primary mechanism for loading a large historical dataset.

### Manual Upload

Manual upload does not provide a repeatable or production-oriented ingestion workflow.

## Rationale

Azure Data Factory provides a managed orchestration layer for batch ingestion while keeping ingestion concerns separate from downstream transformation.

This also allows the project to demonstrate a realistic Azure data-engineering pattern in which an orchestration service controls movement of data into the data lake.

## Consequences

### Positive

* Managed batch orchestration
* Clear separation between ingestion and transformation
* Suitable for historical data loading
* Provides a foundation for scheduling and monitoring
* Reduces the amount of custom orchestration code

### Negative

* Adds an Azure service to the architecture
* Requires configuration of ADF pipelines and connections
* Introduces Azure-specific orchestration concepts

## Project Evidence

The Azure Data Factory resources are managed through Terraform and are used as part of the batch ingestion path into Azure Data Lake Storage Gen2.
