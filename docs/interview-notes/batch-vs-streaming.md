# Batch vs Streaming — Interview Notes

## Why use both?

The platform demonstrates two ingestion patterns because transaction systems commonly contain both historical/bulk data and continuously arriving operational events.

### Batch

Historical transactions are copied using Azure Data Factory.

```text
CSV → ADF → ADLS Bronze
```

ADF is appropriate because the historical source is file-based and can be processed as a scheduled or on-demand bulk ingestion workload.

### Streaming

The later transaction window is replayed through Azure Event Hubs.

```text
Producer → Event Hubs → Consumer → ADLS Bronze
```

Event Hubs acts as the streaming transport and buffer. It is not the analytical storage layer.

## Why was the streaming period later than the batch period?

The project uses a chronological split.

The batch workload represents historical data up to November 2020. The December 2020 window is replayed through Event Hubs.

This prevents the batch and streaming paths from processing the same chronological period intentionally.

## Why accelerated replay?

The dataset is historical rather than genuinely real-time.

An accelerated replay allows the platform to demonstrate the mechanics of event-driven ingestion without claiming that the source itself is a live transaction system.

## event_time vs ingestion_time

`event_time` represents when the transaction occurred according to the source.

`ingestion_time` represents when the transaction entered the platform ingestion flow.

Keeping both timestamps is important because they answer different questions.

For example:

```text
event_time      = when the transaction happened
ingestion_time  = when the platform received it
```

The difference between them can later be used to investigate ingestion latency and late-arriving events.

## What happened with Event Hubs throttling?

The first accelerated producer configuration sent events faster than the available Event Hubs throughput could sustain.

Azure returned a server-side throttling response.

The producer was subsequently designed to:

1. use bounded event batches,
2. pace successful sends,
3. retry transient failures,
4. use exponential backoff when a send fails.

This is preferable to simply assuming that a producer can send indefinitely at maximum speed.

## Why not simply increase Event Hubs capacity?

Increasing capacity is one possible operational response, but this portfolio project intentionally uses a small Standard namespace to control cost.

The producer therefore demonstrates application-level backpressure behavior as well.

In a larger production system, capacity planning, autoscaling strategy, partition utilization, producer concurrency, and throughput requirements would also be considered.

## Why can duplicates occur?

The producer creates a deterministic `event_id` for each transaction.

If a producer is interrupted after successfully sending an event but before the sender knows the complete outcome, or if a replay starts from an approximate checkpoint, the same event can potentially be sent again.

This is why reliable ingestion cannot depend only on "send once" behavior.

Day 6 therefore introduces idempotent Bronze-to-Silver processing using `event_id`.

## Day 5 vs Day 6

Day 5 proves:

```text
Batch ingestion works
Streaming ingestion works
Both reach Bronze
```

Day 6 makes the ingestion pipeline safer:

```text
Bronze
  ↓
Schema validation
  ↓
Business validation
  ↓
Duplicate detection
  ↓
Quarantine
  ↓
Silver + Audit
```

This separation keeps the project progression clear: first prove the data movement, then harden the data-processing layer.
