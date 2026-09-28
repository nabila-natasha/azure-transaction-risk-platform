# Day 6 — Bronze to Silver Data Reliability

## Objective

Day 6 implements the Bronze → Silver reliability layer for the Azure Transaction Risk Analytics Platform.

The objective is to transform raw Bronze transaction data into validated Silver data while providing:

* schema and data-quality validation
* deterministic event identification
* duplicate detection
* idempotent processing with respect to `event_id`
* quarantine handling
* audit metrics
* separate processing paths for batch and streaming data
* convergence of batch and streaming data into the same Silver layer

The processing layer is implemented in:

```text
ingestion/processing/bronze_to_silver.py
```

---

## Architecture

```text
                    BRONZE
                       |
          +------------+------------+
          |                         |
     Batch Bronze             Streaming Bronze
          |                         |
   transactions_batch.csv       JSONL events
          |                         |
          +------------+------------+
                       |
              Bronze → Silver
                       |
          +------------+------------+
          |            |            |
       Valid       Duplicate     Invalid
          |            |            |
          ↓            ↓            ↓
       SILVER      QUARANTINE   QUARANTINE
                       |
                       ↓
                 DQ METRICS
```

Batch and streaming ingestion use different mechanisms, but both converge at the Bronze layer and are processed by the same reliability layer.

---

## Bronze Inputs

### Batch

The historical transaction dataset is stored at:

```text
bronze/transactions/batch/transactions_batch.csv
```

The batch source contains:

```text
1,712,856 rows
```

The chronological batch period ends on:

```text
2020-11-30 23:59:45
```

### Streaming

Event Hubs replayed the December transaction period into:

```text
bronze/transactions/streaming/
```

The streaming Bronze layer contains:

```text
1,682 JSONL files
244,276 events
```

The original chronological streaming source contains:

```text
139,538 unique transactions
```

The difference is caused by the producer recovery and replay activity performed during Day 5. These replays provide a practical demonstration of duplicate handling and idempotent processing.

---

## Event ID

A deterministic `event_id` is used as the idempotency key.

For batch records, the ID is generated using:

```text
SHA256(
    trans_date_trans_time
    |
    cc_num
    |
    amt
    |
    merchant
)
```

The streaming producer generates the same deterministic identifier before publishing the event to Event Hubs.

For streaming records, the Bronze → Silver processor preserves the existing `event_id` rather than generating a new identifier.

This allows the same transaction replayed through Event Hubs to be identified as the same logical event.

---

## Validation Rules

The processor performs the following validation checks.

### Event ID

An event must contain a non-empty `event_id`.

Invalid records receive:

```text
missing_event_id
```

### Transaction amount

The transaction amount must be numeric and non-negative.

Possible quarantine reasons:

```text
missing_amount
negative_amount
```

### Latitude

Customer latitude must be within:

```text
-90 to 90
```

Invalid records receive:

```text
invalid_latitude
```

### Longitude

Customer longitude must be within:

```text
-180 to 180
```

Invalid records receive:

```text
invalid_longitude
```

### Merchant latitude

Merchant latitude must be within:

```text
-90 to 90
```

Invalid records receive:

```text
invalid_merchant_latitude
```

### Merchant longitude

Merchant longitude must be within:

```text
-180 to 180
```

Invalid records receive:

```text
invalid_merchant_longitude
```

### Fraud flag

The fraud indicator must be either:

```text
0 or 1
```

Invalid records receive:

```text
invalid_fraud_flag
```

### Duplicate event ID

An event is quarantined when its `event_id` has already been accepted.

Duplicates are detected both:

* across processing chunks
* within the current processing chunk

The quarantine reason is:

```text
duplicate_event_id
```

---

## Idempotency

The processing design is idempotent with respect to `event_id`.

The same logical transaction may appear multiple times in Bronze because the streaming producer can replay events after a partial transmission or recovery.

Instead of creating multiple analytical records, the processor:

```text
first occurrence
      ↓
   accepted
      ↓
   Silver

replayed occurrence
      ↓
duplicate event_id
      ↓
 quarantine
```

This prevents replayed events from becoming duplicate analytical transactions.

The Day 5 streaming recovery scenario produced a substantial number of repeated events, allowing the idempotency behavior to be demonstrated using an actual platform replay rather than only synthetic test rows.

---

## Output Structure

### Silver

```text
silver/transactions/
├── batch/
│   ├── part_00000.parquet
│   ├── ...
│   └── part_00034.parquet
│
└── streaming/
    ├── part_00000.parquet
    ├── part_00001.parquet
    ├── part_00002.parquet
    ├── part_00003.parquet
    └── part_00004.parquet
```

The batch layer contains:

```text
35 Parquet files
1,712,856 valid records
```

The optimized streaming processor reduced the streaming Silver output to:

```text
5 Parquet files
139,538 valid records
```

The reduction in file count avoids the inefficient one-Bronze-file-to-one-Silver-file pattern used during the initial implementation.

---

## Quarantine

Invalid and duplicate records are separated from analytical Silver data.

The intended structure is:

```text
quarantine/transactions/
├── batch/
└── streaming/
```

The streaming quarantine output from the successful processing run contained:

```text
104,738 duplicate events
```

The quarantine Parquet artifacts were subsequently cleaned during Day 6 verification. The underlying Bronze data remains available for regeneration, and the authoritative DQ counts are retained in the audit metrics and processing log.

---

## Audit / DQ Metrics

DQ metrics are written to:

```text
audit/dq_metrics/run_date=YYYY-MM-DD/dq_metrics.parquet
```

The successful streaming processing run produced:

```text
244,276 rows received
139,538 rows valid
104,738 rows quarantined
104,738 duplicate rows
```

### Streaming DQ result

| run_time                         | rows_received | rows_valid | rows_quarantined | duplicate_rows | duplicate_rate | dq_pass_rate |
| -------------------------------- | ------------: | ---------: | ---------------: | -------------: | -------------: | -----------: |
| 2026-09-28T10:27:42.027583+00:00 |       244,276 |    139,538 |          104,738 |        104,738 |       0.428769 |     0.571231 |

The duplicate rate is:

```text
104,738 / 244,276 = 42.8769%
```

The streaming DQ pass rate is:

```text
139,538 / 244,276 = 57.1231%
```

---

## Combined Day 6 Result

The previously verified batch processing result was:

```text
1,712,856 valid
0 quarantined
0 duplicates
```

Combining the batch result with the successful streaming result gives the overall Day 6 platform result:

| Metric           | Batch + Streaming |
| ---------------- | ----------------: |
| Rows received    |         1,957,132 |
| Rows valid       |         1,852,394 |
| Rows quarantined |           104,738 |
| Duplicate rows   |           104,738 |
| Duplicate rate   |          0.053516 |
| DQ pass rate     |          0.946484 |

Calculation:

```text
Total received
= 1,712,856 + 244,276
= 1,957,132
```

```text
Total valid
= 1,712,856 + 139,538
= 1,852,394
```

```text
Total quarantined
= 104,738
```

```text
DQ pass rate
= 1,852,394 / 1,957,132
= 94.6484%
```

The valid total of:

```text
1,852,394
```

matches the complete original Sparkov-simulated transaction dataset size.

---

## Processing Optimization

The first implementation created one Silver Parquet output for each small streaming Bronze JSONL file.

With 1,682 Bronze files, this resulted in excessive Azure storage operations and slow processing.

The optimized implementation buffers streaming records into approximately 50,000-row processing batches.

### Initial approach

```text
1,682 Bronze JSONL files
        ↓
1,682 validation/write operations
        ↓
many small Silver files
```

### Optimized approach

```text
1,682 Bronze JSONL files
        ↓
50,000-row in-memory processing batches
        ↓
5 Silver Parquet outputs
```

The Bronze layer remains unchanged. The optimization is applied only to the Bronze → Silver processing strategy.

---

## Authentication

The processor uses:

```python
DefaultAzureCredential(
    exclude_shared_token_cache_credential=True
)
```

Azure authentication is therefore handled through the Azure identity chain rather than embedding storage keys or credentials in the repository.

No storage account keys or Event Hubs connection strings are stored in Git.

---

## Day 6 Evidence

The following evidence was captured during implementation:

* successful ADF batch ingestion
* successful Event Hubs streaming replay
* Bronze batch and streaming population
* duplicate/replay behavior
* Bronze → Silver processing
* Silver batch output
* Silver streaming output
* DQ metrics
* optimized processing behavior

Key verified Azure paths:

```text
bronze/transactions/batch/
bronze/transactions/streaming/

silver/transactions/batch/
silver/transactions/streaming/

audit/dq_metrics/run_date=2026-09-28/
```

---

## Day 6 Completion Criteria

| Requirement                    | Status   |
| ------------------------------ | -------- |
| Batch Bronze available         | Complete |
| Streaming Bronze available     | Complete |
| Batch → Silver validation      | Complete |
| Streaming → Silver validation  | Complete |
| Deterministic event ID         | Complete |
| Duplicate detection            | Complete |
| Idempotent event handling      | Complete |
| Quarantine logic               | Complete |
| DQ metrics                     | Complete |
| Optimized streaming processing | Complete |
| Silver outputs verified        | Complete |

Day 6 establishes the data reliability layer required before the machine-learning workload begins.

The next stage is Day 7: feature engineering and fraud-risk modelling using the validated Silver transaction data.
