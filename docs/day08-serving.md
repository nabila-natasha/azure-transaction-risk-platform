# Day 8 — ML Scoring, Synapse Serverless Serving & Power BI

## 1. Objective

Day 8 extends the transaction-risk platform from machine-learning evaluation into an analytics-serving layer.

The objectives are to:

1. Produce transaction-level ML scores from the XGBoost model.
2. Store scored transactions in the Gold layer of ADLS Gen2.
3. Expose Gold data through Azure Synapse Serverless SQL.
4. Create serving views for downstream analytics.
5. Connect Power BI to the serving layer.
6. Build three purposeful dashboards for different analytical users.

### Day 8 Architecture

```text
ADLS Gen2
│
├── silver/transactions/batch
│       │
│       └── XGBoost training data
│
├── silver/transactions/streaming
│       │
│       └── Evaluation / scoring data
│
├── gold/ml/
│   ├── xgboost_metrics.parquet
│   ├── isolation_forest_metrics.parquet
│   ├── shap_feature_importance.parquet
│   └── scored_transactions/
│       └── scored_transactions.parquet
│
└── audit/dq_metrics/run_date=...
        │
        ▼
Azure Synapse Serverless SQL
        │
        ├── Transaction Investigation
        ├── Executive Overview
        ├── ML Explainability
        └── Pipeline Health
        │
        ▼
Power BI
```

---

## 2. XGBoost Scoring Design

The XGBoost model uses the Silver **batch** dataset for training and the Silver **streaming evaluation** dataset for evaluation and transaction-level scoring.

This separation is intentional:

```text
Silver Batch
1,712,856 rows
      │
      ▼
XGBoost Training
      │
      ▼
Trained Model
      │
      ▼
Silver Streaming Evaluation
139,538 valid rows
      │
      ▼
Transaction Scoring
      │
      ▼
Gold Scored Transactions
139,538 rows
```

The batch dataset is therefore **not** included in the transaction-level serving output.

The existing model evaluation metrics were also calculated on the streaming evaluation population. Keeping transaction-level scoring aligned with that same population makes the model evaluation results and Power BI transaction-level results directly traceable.

---

## 3. Training Features

The XGBoost model uses the following 11 features:

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

The same feature-engineering logic is applied during both training and scoring.

This consistency is important because changing feature definitions between training and serving can introduce **training/serving skew**.

### 3.1 Feature Engineering

The scoring pipeline derives:

| Feature            | Derivation                                                    |
| ------------------ | ------------------------------------------------------------- |
| `transaction_hour` | Hour extracted from `event_time`                              |
| `day_of_week`      | Day of week extracted from `event_time`                       |
| `month`            | Month extracted from `event_time`                             |
| `customer_age`     | Difference between `event_time` and `dob`, expressed in years |
| `distance_km`      | Haversine distance between customer and merchant coordinates  |

The model input remains restricted to the 11 defined features.

Additional transaction attributes such as merchant, category, city, state, transaction ID, and event metadata are retained for analytics but are **not passed to the model**.

---

## 4. XGBoost Model Configuration

The scoring script retrains the same XGBoost configuration used during model evaluation:

```text
n_estimators = 300
max_depth = 6
learning_rate = 0.05
subsample = 0.8
colsample_bytree = 0.8
objective = binary:logistic
eval_metric = aucpr
scale_pos_weight = non_fraud / fraud
random_state = 42
n_jobs = -1
```

Class imbalance is handled using:

```text
scale_pos_weight = non_fraud / fraud
```

The transaction-scoring threshold is:

```text
0.50
```

Model version:

```text
xgboost-v1
```

---

## 5. Scored Transaction Output

The transaction-level scoring output is stored at:

```text
gold/ml/scored_transactions/scored_transactions.parquet
```

The current output contains:

```text
139,538 rows
```

The output was successfully written to ADLS Gen2 on **2026-09-29**.

The serving output contains both model results and descriptive transaction attributes.

### 5.1 Output Fields

Important fields include:

```text
trans_num
event_id
event_time
ingestion_time
merchant
category
amt
city
state
zip
lat
long
city_pop
merch_lat
merch_long
is_fraud
fraud_probability
predicted_fraud
risk_band
model_threshold
model_version
source
```

### 5.2 Risk Bands

The operational risk bands are:

|      Fraud Probability | Risk Band |
| ---------------------: | --------- |
|              `<= 0.30` | Low       |
| `> 0.30` and `<= 0.70` | Medium    |
|               `> 0.70` | High      |

The risk band is separate from the binary model classification.

For example, a transaction with:

```text
fraud_probability = 0.319691
predicted_fraud    = 0
risk_band          = Medium
```

is not classified as fraud at the 0.50 model threshold but is still placed in the Medium operational risk band.

This allows Power BI users to distinguish between the model's binary classification threshold and a broader operational risk-prioritization view.

---

## 6. Current Scoring Results

The current scoring run produced:

| Metric        |    Result |
| ------------- | --------: |
| Training rows | 1,712,856 |
| Scoring rows  |   139,538 |
| Output rows   |   139,538 |

### 6.1 Risk-Band Distribution

| Risk Band | Transactions |
| --------- | -----------: |
| Low       |      133,327 |
| Medium    |        4,166 |
| High      |        2,045 |

### 6.2 Binary Predictions

At the `0.50` model threshold:

| Prediction          | Transactions |
| ------------------- | -----------: |
| Predicted non-fraud |      135,940 |
| Predicted fraud     |        3,598 |

The Gold output contains exactly the 139,538 streaming evaluation transactions.

The scored output was verified in ADLS Gen2:

```text
gold/ml/scored_transactions/scored_transactions.parquet
```

Current file size is approximately **21.1 MB**.

---

## 7. Model Evaluation Results

The XGBoost evaluation output is stored at:

```text
gold/ml/xgboost_metrics.parquet
```

### 7.1 Overall Metrics

| Metric  |  Value |
| ------- | -----: |
| ROC-AUC | 0.9826 |
| PR-AUC  | 0.3622 |

Because fraud is highly imbalanced, PR-AUC provides an important complementary view of model performance alongside ROC-AUC.

### 7.2 Threshold Analysis

| Threshold | Precision | Recall |
| --------: | --------: | -----: |
|      0.30 |     3.74% | 89.92% |
|      0.50 |     6.06% | 84.50% |
|      0.70 |     9.73% | 77.13% |

The threshold analysis demonstrates the operational trade-off between identifying more fraudulent transactions and reducing false positives.

A lower threshold captures more fraud cases but generates more false positives. A higher threshold produces fewer positive alerts but reduces recall.

---

## 8. SHAP Explainability

Global SHAP feature importance is stored at:

```text
gold/ml/shap_feature_importance.parquet
```

The current features ranked by mean absolute SHAP value are:

| Rank | Feature            | Mean Absolute SHAP |
| ---: | ------------------ | -----------------: |
|    1 | `amt`              |           3.370900 |
|    2 | `transaction_hour` |           1.121264 |
|    3 | `month`            |           0.552961 |
|    4 | `customer_age`     |           0.372982 |
|    5 | `city_pop`         |           0.257780 |
|    6 | `day_of_week`      |           0.171224 |
|    7 | `long`             |           0.116711 |
|    8 | `lat`              |           0.107139 |
|    9 | `merch_lat`        |           0.070166 |
|   10 | `merch_long`       |           0.069404 |
|   11 | `distance_km`      |           0.063416 |

This is **global feature importance**.

Mean absolute SHAP values describe the magnitude of model contribution across the evaluated population. They do not provide a row-level explanation for why an individual transaction was flagged.

Therefore, the Day 8 dashboard should describe this as:

> **Global Model Explainability**

rather than claiming that it explains the exact reason an individual transaction was flagged.

---

## 9. Isolation Forest Results

The unsupervised anomaly-detection output is stored at:

```text
gold/ml/isolation_forest_metrics.parquet
```

### 9.1 Overall Metrics

| Metric             |   Value |
| ------------------ | ------: |
| ROC-AUC            |  0.8198 |
| PR-AUC             |  0.0125 |
| Evaluation rows    | 139,538 |
| Anomalies detected |  16,381 |
| Anomaly rate       |  11.74% |

### 9.2 Fraud Rate by Anomaly Group

| Group                  | Observed Fraud Rate |
| ---------------------- | ------------------: |
| Normal transactions    |             0.0820% |
| Anomalous transactions |             0.9584% |

The anomalous group has a substantially higher observed fraud rate than the normal group.

Isolation Forest is therefore treated as a **complementary unsupervised anomaly signal**, rather than a replacement for the supervised XGBoost classifier.

---

## 10. Data Quality / Pipeline Health

Data-quality metrics are stored at:

```text
audit/dq_metrics/run_date=2026-09-28/dq_metrics.parquet
```

### 10.1 Current Metrics

| Metric           |   Value |
| ---------------- | ------: |
| Rows received    | 244,276 |
| Rows valid       | 139,538 |
| Rows quarantined | 104,738 |
| Duplicate rows   | 104,738 |
| Duplicate rate   |  42.88% |
| DQ pass rate     |  57.12% |

The current quarantine population is dominated by duplicate records.

This should remain visible in Pipeline Health reporting rather than being hidden, because data-quality behavior is an important part of the production-style engineering story.

---

## 11. Synapse Serverless Serving Layer

Azure Synapse Serverless SQL provides the analytical serving layer over the ADLS Gen2 Parquet data.

### 11.1 Synapse Resources

**Workspace**

```text
syn-transaction-bello
```

**Serverless SQL endpoint**

```text
syn-transaction-bello.sql.azuresynapse.net
```

The project uses **Serverless SQL** rather than a Dedicated SQL pool for the serving layer.

### 11.2 Serving Schema

The intended serving schema is:

```text
serving
```

### 11.3 Planned Serving Views

```text
serving.vw_transaction_investigation
serving.vw_executive_overview
serving.vw_ml_explainability
serving.vw_pipeline_health
```

The views will read the Gold ML outputs and audit data stored in ADLS Gen2.

> **Status:** Synapse serving views are planned for the next implementation step.

---

## 12. Power BI Reporting Layer

Power BI will consume the Synapse Serverless serving layer.

Three primary dashboards are planned.

### 12.1 Dashboard 1 — Executive Overview

**Audience:** Executive / management

**Purpose:** Provide a high-level view of transaction activity, model alerts, fraud patterns, and operational exposure.

Potential metrics and visuals:

* Transaction volume
* Observed fraud rate
* Predicted fraud count
* High-risk transaction count
* Flagged transaction value
* Geographic distribution
* Fraud trend over time
* Risk-band distribution

**Metric definition**

"Flagged transaction value" represents the transaction amount associated with model-flagged transactions.

It should **not** be described as realized fraud loss or realized revenue.

---

### 12.2 Dashboard 2 — Transaction Investigation

**Audience:** Fraud analyst / investigator

**Purpose:** Allow analysts to inspect individual scored transactions.

Potential filters:

* Transaction ID
* Event date/time
* Merchant
* Category
* City
* State
* Risk band
* Predicted fraud
* Probability range

Useful fields include:

```text
trans_num
event_time
merchant
category
amt
city
state
fraud_probability
predicted_fraud
risk_band
model_threshold
model_version
```

The dashboard is intended for **investigation and prioritization**, not automated adjudication.

---

### 12.3 Dashboard 3 — ML Explainability

**Audience:** Data scientist / ML engineer / technical stakeholder

**Purpose:** Show model behavior and performance rather than individual transaction investigation.

Potential visuals:

* ROC-AUC
* PR-AUC
* Precision vs. threshold
* Recall vs. threshold
* Confusion-matrix metrics
* Global SHAP feature importance
* Isolation Forest anomaly rate
* Fraud rate for anomalous vs. normal transactions
* Model version
* Model threshold

The dashboard should clearly distinguish **global SHAP importance** from row-level explanations.

---

## 13. Training/Serving Separation

The Gold scored transaction output contains descriptive fields in addition to model features.

Examples include:

```text
merchant
category
city
state
trans_num
event_id
fraud_probability
risk_band
```

These additional columns do not create training/serving skew because they are not model inputs.

Training/serving consistency applies to the actual model feature vector:

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

These features and their engineering logic must remain consistent between training and scoring.

---

## 14. Cloud Shell Resource Consideration

An initial scoring approach attempted to load and score the full transaction population, approximately 1.85 million rows, in Cloud Shell.

The process was terminated because of memory pressure.

The scoring scope was subsequently aligned with the existing 139,538-row streaming evaluation dataset.

This approach:

* matches the existing model evaluation population;
* avoids unnecessary memory pressure in Cloud Shell;
* produces a reproducible serving dataset;
* keeps model evaluation and transaction-level dashboard results directly traceable.

For a production-scale implementation, scoring would normally be moved into distributed or managed compute rather than relying on Cloud Shell memory.

---

## 15. Day 8 Architecture

The completed and planned flow is:

```text
Azure Data Lake Storage Gen2
│
├── Silver Batch
│      └── 1,712,856 training rows
│                │
│                ▼
│          XGBoost Training
│                │
│                ▼
│          XGBoost Model
│
├── Silver Streaming Evaluation
│      └── 139,538 valid rows
│                │
│                ▼
│          XGBoost Scoring
│                │
│                ▼
│      Gold Scored Transactions
│
├── Gold ML Metrics
│      ├── XGBoost metrics
│      ├── SHAP importance
│      └── Isolation Forest metrics
│
└── Audit
       └── Data-quality metrics
                │
                ▼
        Synapse Serverless SQL
                │
                ▼
          Serving Views
                │
                ▼
             Power BI
```

---

## 16. Day 8 Status

### Completed

* XGBoost model evaluation
* Threshold analysis
* Global SHAP analysis
* Isolation Forest evaluation
* Data-quality metrics
* Transaction-level XGBoost scoring
* Gold scored transaction output
* ADLS verification of scored transaction output
* Day 8 serving architecture definition

### Next Steps

* Configure Synapse Serverless access to ADLS
* Create the `serving` schema
* Create and validate serving views
* Connect Power BI to Synapse Serverless
* Build the Executive Overview dashboard
* Build the Transaction Investigation dashboard
* Build the ML Explainability dashboard
* Capture final dashboard evidence
* Update this document with final Synapse and Power BI implementation details
