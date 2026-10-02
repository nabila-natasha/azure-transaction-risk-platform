# ADR-002: Use Azure Event Hubs for Streaming Ingestion

## Status

Accepted

## Context

The platform needs to demonstrate both batch and event-driven ingestion.

The transaction dataset is historical and does not represent a real production transaction stream. Therefore, a replay mechanism is required to simulate near-real-time transaction events without claiming that the source is a live banking system.

The streaming path should support event delivery, partitioning, replay, and consumer-based processing.

## Decision

Use Azure Event Hubs as the event-ingestion layer for the simulated near-real-time transaction stream.

Historical transaction records are replayed as events into Event Hubs. Consumers process these events and write them into the Bronze layer of Azure Data Lake Storage Gen2.

## Alternatives Considered

### Direct File Ingestion

Files could be written directly to the data lake, but this would not demonstrate an event-driven ingestion architecture.

### Azure Service Bus

Service Bus provides messaging capabilities but is not the primary choice for high-throughput event-stream ingestion in this project.

### Kafka

Kafka is a common event-streaming platform, but using Azure Event Hubs provides a managed Azure-native service that fits the project's architecture.

## Rationale

Event Hubs provides a managed event-ingestion service with partitioned throughput and consumer-based processing.

It allows the project to demonstrate an event-driven ingestion path while remaining clear that the source data is simulated historical data rather than live banking transactions.

## Consequences

### Positive

* Managed event ingestion
* Partitioned event processing
* Supports replay-based streaming demonstrations
* Azure-native integration
* Separates event ingestion from downstream data processing

### Negative

* Adds another ingestion component
* Requires consumer logic and event-handling code
* Simulated streaming does not represent the operational characteristics of a true live banking system

## Project Evidence

The project uses an Event Hubs namespace and event hub for transaction replay. The replayed events converge into the same Bronze data layer used by the batch ingestion path.
