# Day 5 — Batch and Streaming Ingestion

## Objective

Demonstrate the two operational ingestion paths for the transaction-risk platform:

1. Historical batch ingestion through Azure Data Factory.
2. Chronological streaming replay through Azure Event Hubs.

Both paths converge in the ADLS Gen2 Bronze layer.

## Batch Ingestion

Historical transaction data was ingested through Azure Data Factory.

```text
Historical CSV
     |
     v
Azure Data Factory
     |
     v
ADLS Gen2
bronze/transactions/batch/
```

### Result

* Pipeline: `PL_Batch_Transactions`
* Copy activity: `Copy_Transactions_Batch_to_Bronze`
* Source: `source/transactions/transactions_batch.csv`
* Destination: `bronze/transactions/batch/transactions_batch.csv`
* Source rows: 1,712,856
* Data read: 457,796,677 bytes
* Data written: 457,796,677 bytes
* Files read: 1
* Files written: 1
* Errors: 0

The Azure Data Factory copy activity completed successfully.

## Streaming Ingestion

The later chronological transaction window was replayed through Azure Event Hubs.

```text
Streaming CSV
     |
     v
Python Event Hubs Producer
     |
     v
Azure Event Hubs
transaction-events
     |
     v
Python Consumer
     |
     v
ADLS Gen2
bronze/transactions/streaming/
```

### Result

* Event Hubs namespace: `eh-transaction-bello`
* Event Hub: `transaction-events`
* Partitions: 4
* Consumer group: `$Default`
* Bronze streaming files: 954
* Bronze streaming events received: 98,688

The consumer wrote JSONL files under partition-specific Bronze paths.

Example:

```text
bronze/transactions/streaming/
├── partition=0/
├── partition=1/
├── partition=2/
└── partition=3/
```

The streaming payload preserves:

* `event_id`
* `event_time`
* `ingestion_time`
* `source`
* transaction payload

`event_time` represents the original transaction timestamp, while `ingestion_time` represents when the event was produced for ingestion.

## Chronological Replay Design

The original source was divided operationally by transaction timestamp rather than using the source uploader's `fraudTrain.csv` and `fraudTest.csv` names as the streaming boundary.

The Project 4 split is:

| Ingestion path     | Transaction period                        | Source rows |
| ------------------ | ----------------------------------------- | ----------: |
| Batch / historical | 2019-01-01 00:00:18 → 2020-11-30 23:59:45 |   1,712,856 |
| Streaming replay   | 2020-12-01 00:00:55 → 2020-12-31 23:59:34 |     139,538 |

The streaming path is an accelerated replay of historical data. It is therefore a simulation of streaming ingestion rather than a genuine real-time transaction source.

## Event Hubs Throttling Incident

During the accelerated replay, the Event Hubs namespace returned a service-side throttling error:

```text
server-busy
50002
entity is being throttled
```

The producer was initially sending batches too aggressively for the available throughput of the Standard namespace configured with one throughput unit.

The issue was therefore treated as a throughput-management problem rather than a malformed-event or consumer-code failure.

The producer was stopped and resumed during the experiment. A temporary resume file was used to continue from a later transaction timestamp.

This created the possibility of replaying some events that had already been delivered during an earlier attempt.

## Current Day 5 Boundary

Day 5 intentionally demonstrates ingestion rather than production hardening.

The current Bronze streaming result contains 98,688 received events from the 139,538-row streaming source window. The remaining source events are not required to prove the Day 5 ingestion architecture.

The producer/consumer implementation and Bronze data will be further hardened on Day 6.

## Day 6 Follow-up

Day 6 adds the production-oriented Bronze-to-Silver quality gate:

* schema validation
* required-field validation
* business-rule validation
* deterministic `event_id` validation
* duplicate detection
* idempotent processing
* quarantine handling
* DQ metrics
* audit output

The `event_id` generated during Day 5 provides the key used for duplicate detection.

The intended processing rule is:

> The same transaction `event_id` must not produce multiple analytical records in Silver.

Therefore, duplicates created by replay or retry are handled during Day 6 processing rather than being silently treated as separate transactions.

## Evidence

Azure evidence includes:

* Successful ADF batch copy activity.
* ADLS Bronze batch file.
* Event Hubs streaming configuration.
* ADLS partitioned streaming JSONL files.
* Streaming event count validation.
* Producer throttling and retry behavior observed during accelerated replay.
