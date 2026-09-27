## Project 4 Operational Ingestion Split

The source dataset is provided as two CSV files (`fraudTrain.csv` and
`fraudTest.csv`) by the original uploader. Those filenames represent the
uploader's original machine-learning organization and are **not** used
as the batch/streaming boundary for this project.

For Project 4, the transaction records were divided chronologically by
`trans_date_trans_time`:

| Ingestion path     | Transaction period                        |      Rows |
| ------------------ | ----------------------------------------- | --------: |
| Batch / historical | 2019-01-01 00:00:18 → 2020-11-30 23:59:45 | 1,712,856 |
| Streaming replay   | 2020-12-01 00:00:55 → 2020-12-31 23:59:34 |   139,538 |

The historical period is ingested through Azure Data Factory into ADLS
Gen2 Bronze.

The later chronological period is replayed through Azure Event Hubs at
an accelerated cadence to simulate near-real-time transaction ingestion.
The original `trans_date_trans_time` value is retained as `event_time`.

Both ingestion paths converge in the Bronze layer and are processed by
the common Bronze-to-Silver validation and data-quality gate implemented
on Day 6.

The source data is Sparkov-simulated transaction data and is used to
demonstrate the platform architecture and analytics workflow. It does
not represent a live banking transaction feed or real customer
transaction data.

