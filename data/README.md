# Project 4 Data

## Source Dataset

Project 4 uses Sparkov-simulated financial transaction data.

The source dataset is synthetic/simulated and does not represent real banking customers or live financial transactions.

The original source distribution contains:

```text
fraudTrain.csv
fraudTest.csv
```

The filenames reflect the original machine-learning organization of the dataset.

For this project, those filenames are **not** used as the architectural batch/streaming boundary.

---

## Operational Ingestion Split

The transaction records were divided chronologically using:

```text
trans_date_trans_time
```

The resulting operational ingestion paths are:

| Ingestion Path     | Transaction Period                        |      Rows |
| ------------------ | ----------------------------------------- | --------: |
| Batch / historical | 2019-01-01 00:00:18 → 2020-11-30 23:59:45 | 1,712,856 |
| Streaming replay   | 2020-12-01 00:00:55 → 2020-12-31 23:59:34 |   139,538 |

This split was deliberately based on transaction time rather than the original `fraudTrain.csv` / `fraudTest.csv` filenames.

---

## Batch Ingestion

The historical transaction period is ingested through:

```text
Azure Data Factory
        ↓
ADLS Gen2
        ↓
Bronze
```

The batch path demonstrates scheduled/historical ingestion into the data lake.

---

## Streaming Replay

The later chronological transaction period is replayed through:

```text
Transaction records
        ↓
Event Hubs
        ↓
ADLS Bronze
```

The replay uses Azure Event Hubs to simulate near-real-time transaction ingestion at an accelerated cadence.

The original:

```text
trans_date_trans_time
```

value is retained as:

```text
event_time
```

The platform can therefore distinguish the time the transaction occurred from the time the event was received/processed.

---

## Common Bronze Layer

Both ingestion paths converge in the Bronze layer:

```text
Azure Data Factory ──────┐
                         ├──→ Bronze
Azure Event Hubs ────────┘
```

Bronze acts as the landing layer before data-quality processing.

The architecture intentionally keeps ingestion concerns separate from downstream validation.

---

## Bronze-to-Silver Processing

Bronze data is processed through the common data-quality gate:

```text
Bronze
  ↓
Validation
  ├── Valid records
  │      ↓
  │    Silver
  │
  └── Invalid records
         ↓
      Quarantine
```

Validation includes controls such as:

* Required-field checks
* Data-type validation
* Duplicate handling
* Transaction-field validation
* Schema/contract checks

---

## Silver Layer

Silver contains trusted transaction data used by downstream analytics and machine-learning preparation.

The ML workflow derives features from the Silver dataset rather than directly from raw source files.

This provides a clear separation between:

```text
Raw / landed data
        ↓
Validated data
        ↓
ML features
```

---

## ML Dataset

Feature engineering includes:

```text
amt
city_pop
lat
long
merch_lat
merch_long
transaction_hour
day_of_week
month
customer_age
distance_km
```

A Silver-derived Parquet fixture is also used by the automated test suite:

```text
tests/fixtures/silver_transactions_sample.parquet
```

---

## Data Characteristics

The source data is Sparkov-simulated transaction data.

It is used to demonstrate:

* Batch ingestion
* Streaming ingestion
* Data lake architecture
* Data-quality processing
* Feature engineering
* ML workflow validation
* Fraud-risk analytics

It should not be interpreted as:

* A live banking feed
* Real customer transaction data
* A production fraud-detection model
* Evidence of real financial risk

---

## Design Principle

The important architectural decision is that the source file organization is separated from the operational ingestion design.

The project treats:

```text
fraudTrain.csv
fraudTest.csv
```

as source-distribution details.

The platform instead defines its own operational boundary based on transaction time:

```text
Historical period
    → Batch ingestion

Later period
    → Streaming replay
```

This better represents how an actual data platform could separate historical backfill from ongoing event ingestion.
