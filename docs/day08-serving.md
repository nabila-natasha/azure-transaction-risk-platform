# Day 8 — ML Scoring, Synapse Serverless Serving & Power BI

## 1. Objective

Day 8 extends the transaction-risk platform from machine-learning evaluation
into a business-facing analytics-serving layer.

The objectives were to:

1. Produce transaction-level ML scores from the XGBoost model.
2. Store scored transactions in the Gold layer of ADLS Gen2.
3. Expose Gold and audit data through Azure Synapse Serverless SQL.
4. Create curated serving views for downstream analytics.
5. Connect Power BI Desktop to the Synapse serving layer.
6. Build a consolidated fraud-risk overview dashboard.
7. Build a transaction investigation dashboard.
8. Preserve the analytical grain of each serving dataset rather than creating
   artificial relationships between incompatible datasets.

### Day 8 Architecture

```text
ADLS Gen2
    │
    ├── gold/ml/scored_transactions/
    ├── gold/ml/xgboost_metrics.parquet
    ├── gold/ml/shap_feature_importance.parquet
    ├── gold/ml/isolation_forest_metrics.parquet
    └── audit/dq_metrics/
            │
            ▼
    Synapse Serverless SQL
            │
            ▼
    transaction_risk_serving
            │
            ▼
          serving
            │
            ├── vw_transaction_investigation
            ├── vw_executive_overview
            ├── vw_xgboost_metrics
            ├── vw_shap_feature_importance
            ├── vw_isolation_forest_metrics
            └── vw_pipeline_health
            │
            ▼
       Power BI Desktop
            │
            ├── Fraud Risk Overview
            └── Transaction Investigation
```

The completed architecture separates:
- **ADLS Gen2** — durable storage for curated ML and audit outputs.
- **Synapse Serverless SQL** — SQL-based analytical serving layer.
- **Power BI Desktop** — business analysis, investigation, and model monitoring interface.

---

## 2. XGBoost Scoring Design

The XGBoost model uses the Silver batch dataset for training and the Silver streaming evaluation dataset for transaction-level scoring.

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

The batch dataset is therefore **not** included in the transaction-level serving population.

The existing model evaluation metrics were also calculated on the streaming evaluation population. Keeping transaction-level scoring aligned with the same population makes the model evaluation results and Power BI transaction-level results directly traceable.

### Training and scoring populations  

| Population                  |          Rows | Purpose                                  |
| --------------------------- | ------------: | ---------------------------------------- |
| Silver batch                |     1,712,856 | XGBoost training                         |
| Silver streaming evaluation | 139,538 valid | Transaction-level scoring and evaluation |
| Gold scored transactions    |       139,538 | Synapse and Power BI serving             |

The scoring pipeline applies the same feature-engineering logic used during
model evaluation.

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

The current scoring implementation retrains the model using the defined configuration before scoring the streaming evaluation population.

A production implementation would normally persist and version the trained model artifact rather than retraining it during every scoring run.

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

The engineered features are persisted in the Gold output so that downstream Synapse and Power BI consumers do not need to recreate the feature engineering.

---

## 6. Risk Bands and Model Classification

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

This transaction is not classified as fraud at the 0.50 model threshold but is still placed in the Medium operational risk band.

This allows Power BI users to distinguish between:  
- the model's binary classification threshold; and
- a broader operational risk-prioritization view.

The risk band should therefore not be interpreted as a confirmed fraud decision.

---

## 7. Current Scoring Results

The current scoring run produced:

| Metric        |    Result |
| ------------- | --------: |
| Training rows | 1,712,856 |
| Scoring rows  |   139,538 |
| Output rows   |   139,538 |

### 7.1 Risk-Band Distribution

| Risk Band | Transactions |
| --------- | -----------: |
| Low       |      133,327 |
| Medium    |        4,166 |
| High      |        2,045 |

### 7.2 Binary Predictions

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

## 8. Model Evaluation Results

The XGBoost evaluation output is stored at:

```text
gold/ml/xgboost_metrics.parquet
```

### 8.1 Overall Metrics

| Metric  |  Value |
| ------- | -----: |
| ROC-AUC | 0.9826 |
| PR-AUC  | 0.3622 |

Because fraud is highly imbalanced, PR-AUC provides an important complementary view of model performance alongside ROC-AUC.

### 8.2 Threshold Analysis

| Threshold | Precision | Recall |
| --------: | --------: | -----: |
|      0.30 |     3.74% | 89.92% |
|      0.50 |     6.06% | 84.50% |
|      0.70 |     9.73% | 77.13% |

The threshold analysis demonstrates the operational trade-off between identifying more fraudulent transactions and reducing false positives.

In this evaluation:  
- a lower threshold increases recall and generates more positive classifications;
- a higher threshold increases precision and reduces recall.  

The project does not treat one threshold as universally optimal.

The appropriate operating point would depend on business costs, investigation capacity, false-positive workload, and the relative impact of false negatives.

---

## 9. SHAP Explainability

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

The Power BI visual is therefore titled:

> **Global SHAP Feature Importance**

rather than being presented as an explanation of the exact reason an individual transaction was classified as fraud.

---

## 10. Isolation Forest Results

The unsupervised anomaly-detection output is stored at:

```text
gold/ml/isolation_forest_metrics.parquet
```

### 10.1 Overall Metrics

| Metric             |   Value |
| ------------------ | ------: |
| ROC-AUC            |  0.8198 |
| PR-AUC             |  0.0125 |
| Evaluation rows    | 139,538 |
| Anomalies detected |  16,381 |
| Anomaly rate       |  11.74% |

### 10.2 Fraud Rate by Anomaly Group

| Group                  | Observed Fraud Rate |
| ---------------------- | ------------------: |
| Normal transactions    |             0.0820% |
| Anomalous transactions |             0.9584% |

The anomalous group has a higher observed fraud rate than the normal group in this evaluation population.

Isolation Forest is therefore treated as a complementary unsupervised anomaly signal, rather than a replacement for the supervised XGBoost classifier.

These metrics are surfaced on the consolidated Fraud Risk Overview dashboard.

---

## 11. Data Quality and Pipeline Health

Data-quality metrics are stored at:

```text
audit/dq_metrics/run_date=2026-09-28/dq_metrics.parquet
```

### 11.1 Current Metrics

| Metric           |   Value |
| ---------------- | ------: |
| Rows received    | 244,276 |
| Rows valid       | 139,538 |
| Rows quarantined | 104,738 |
| Duplicate rows   | 104,738 |
| Duplicate rate   |  42.88% |
| DQ pass rate     |  57.12% |

The current quarantine population is dominated by duplicate records.

The quarantine population remains visible in Power BI rather than being hidden because data-quality behavior is an important part of the engineering story.

---

## 12. Synapse Serverless Serving Layer

Azure Synapse Serverless SQL provides the analytical serving layer over the ADLS Gen2 Parquet data.

### 12.1 Synapse Resources

**Workspace**

```text
syn-transaction-bello
```

**Serverless SQL endpoint**

The Power BI connection uses the Serverless SQL endpoint exposed by the `syn-transaction-bello` Synapse workspace.

```text
syn-transaction-bello.sql.azuresynapse.net
```

The project uses **Serverless SQL** rather than a Dedicated SQL pool for the serving layer.

### 12.2 Serving Database and Schema

Database:

```text
transaction_risk_serving
```

Schema:

```text
serving
```

The serving views query Parquet directly from ADLS Gen2 using Synapse Serverless `OPENROWSET`.

No separate physical serving tables are required for the current implementation.

### 12.3 Completed Serving Views

The following six serving views have been created and validated:

```text
serving.vw_transaction_investigation
serving.vw_executive_overview
serving.vw_xgboost_metrics
serving.vw_shap_feature_importance
serving.vw_isolation_forest_metrics
serving.vw_pipeline_health
```

| Serving View                   | Analytical Purpose                                 |
| ------------------------------ | -------------------------------------------------- |
| `vw_transaction_investigation` | Transaction-level investigation and model scoring  |
| `vw_executive_overview`        | Date/state transaction and flagged-risk aggregates |
| `vw_xgboost_metrics`           | XGBoost evaluation and threshold analysis          |
| `vw_shap_feature_importance`   | Global SHAP feature importance                     |
| `vw_isolation_forest_metrics`  | Isolation Forest evaluation metrics                |
| `vw_pipeline_health`           | Pipeline and data-quality metrics                  |

The SQL definitions are stored in:
`sql/serving/01_create_serving_layer.sql`

The serving views were validated using Synapse Serverless SQL queries before being consumed by Power BI.

---

## 13. Power BI Reporting Layer

Power BI Desktop connects to the Synapse Serverless serving database.

The completed reporting layer contains two dashboard pages:

1. Fraud Risk Overview
2. Transaction Investigation

The ML explainability content was consolidated into the Fraud Risk Overview rather than maintaining a separate ML-only page.

This provides a more compact reporting experience while retaining:  
- transaction activity;
- model flagging;
- pipeline/data-quality health;
- XGBoost threshold analysis;
- global SHAP importance; and
- Isolation Forest anomaly metrics.

---

## 14. Power BI Data Model

The Power BI model intentionally contains no relationships between the serving views.

This is a deliberate design decision because the datasets have different analytical grains.

| Serving View                   | Grain                          |
| ------------------------------ | ------------------------------ |
| `vw_transaction_investigation` | One row per scored transaction |
| `vw_executive_overview`        | Date/state aggregate           |
| `vw_xgboost_metrics`           | Metric/threshold               |
| `vw_shap_feature_importance`   | Feature                        |
| `vw_isolation_forest_metrics`  | Model evaluation               |
| `vw_pipeline_health`           | Pipeline run                   |

Creating arbitrary relationships between these views could cause row multiplication or misleading aggregations.

Therefore, each serving view is used independently according to its analytical purpose.

The Power BI data-model screenshot is stored at:
`docs/evidence/day08-data-model.PNG`

The screenshot demonstrates the deliberate **no-relationship model design**.

---

## 15. Dashboard 1 — Fraud Risk Overview

Purpose: Provide a consolidated view of transaction activity, model risk, ML behavior, and pipeline/data-quality health.

Primary audience: Management, fraud-risk stakeholders, data/ML stakeholders.

The completed dashboard contains the following sections:

```text
Fraud Risk Overview
├── Transaction KPIs
├── Isolation Forest KPIs
├── Transaction Volume Over Time
├── Pipeline & Data Quality
├── Flagged Transactions by State
├── XGBoost Threshold: Precision vs Recall
└── Global SHAP Feature Importance
```

### 15.1 Transaction and ML KPI Cards

The dashboard displays:

| KPI                       | Current Value |
| ------------------------- | ------------: |
| Transaction Count         |       139.54K |
| Flagged Transactions      |         3,598 |
| Flagged Transaction Value |        $1.17M |
| Average Fraud Probability |         4.56% |
| Anomaly Rate              |        11.74% |
| Normal Group Fraud Rate   |        0.082% |
| Anomaly Group Fraud Rate  |       0.9584% |
| Isolation Forest PR-AUC   |        0.0125 |

### Fraud Probability Formatting

The underlying `fraud_probability` is a numeric value between `0` and `1`.

Power BI formats the measure/column as a percentage for business readability.

Examples:

```text
0.00916 → 0.92%
0.07990 → 7.99%
0.97320 → 97.32%
```

The percentage formatting does not change the underlying model output.

### 15.2 Transaction Volume Over Time

A line chart displays transaction volume by transaction date.

Title:  

`Transaction Volume Over Time`

This provides a high-level view of transaction activity across the evaluation period.

### 15.3 Flagged Transactions by State

A horizontal bar chart displays model-flagged transaction counts by state.

Title:

Flagged Transactions by State

The chart represents transactions classified as positive by the current XGBoost threshold. It should not be interpreted as confirmed fraud losses by state.

### 15.4 Pipeline and Data Quality

The dashboard displays:

- Rows Received
- Rows Valid
- Rows Quarantined
- DQ Pass Rate

Current values:

```text
Received        244.28K
Valid           139.54K
Quarantined     104.74K
DQ Pass Rate     57.12%
```

The quarantine population is intentionally visible.

### 15.5 XGBoost Threshold: Precision vs Recall

The dashboard contains a line chart titled:

`XGBoost Threshold: Precision vs Recall`

The visual uses the XGBoost serving view:

`serving.vw_xgboost_metrics`

The visual is filtered to:

`metric_type = threshold_analysis`

The X-axis is:

`threshold`

The Y-axis contains:

```text
precision
recall
```

The displayed thresholds are:

```text
0.30
0.50
0.70
```

The visual demonstrates the precision/recall trade-off without treating one threshold as universally optimal.

### 15.6 Global SHAP Feature Importance

The dashboard contains a horizontal bar chart titled:

`Global SHAP Feature Importance`

The visual uses:

```text
feature
mean_absolute_shap
rank
```

The current visual confirms that amt has the highest mean absolute SHAP value in the evaluated population, followed by `transaction_hour` and `month`.

This is a global model-level view, not a row-level explanation.

### 15.7 Power BI Evidence

Screenshot:

`docs/evidence/day08-powerbi-fraud-risk-overview.PNG`

The screenshot demonstrates that the Synapse serving layer is successfully consumed by Power BI and that transaction, model, explainability, and pipeline metrics can be presented together.

---

## 16. Dashboard 2 — Transaction Investigation

**Purpose**: Provide an operational interface for inspecting individual scored transactions.

**Primary audience** : Fraud analysts, investigators, and technical stakeholders reviewing model outputs.

### 16.1 Filters

The completed dashboard provides:  
- State
- Category
- Risk
- Predicted Fraud

These filters allow an analyst to narrow the transaction population before reviewing individual records.

### 16.2 Investigation Table

The table exposes transaction-level information including:  

```text
Transaction Number
Event Time
Merchant
Category
Amount
City
State
Transaction Hour
Age
Distance (km)
Fraud Probability
```

The table is intended to allow an analyst to move from a filtered population to individual transaction context.

The workflow is:

```text
Filter
  ↓
Identify transactions of interest
  ↓
Inspect transaction context
  ↓
Review engineered risk indicators
  ↓
Review fraud probability / risk classification
  ↓
Human investigation
```

The dashboard is intended for **investigation and prioritization**, not automated adjudication.

### 16.3 Category Presentation

The source category values contain technical naming conventions such as:

```text
shopping_net
grocery_pos
gas_transport
misc_net
```

Power BI uses a presentation-friendly display field so these values can be shown as:

```text
Shopping Net
Grocery Pos
Gas Transport
Misc Net
```

The underlying raw `category` value remains available in the serving data.

This is a **presentation transformation**, not a change to the source transaction classification.

### 16.4 Merchant Presentation

The synthetic transaction dataset contains merchant naming patterns such as:

```text
fraud_Kuhn LLC
fraud_Kozey-Boehm
```

Power BI uses a presentation display field where required to remove technical dataset prefixes for readability.

For example:

`fraud_Kuhn LLC`

can be displayed as:

`Kuhn LLC`

This is a display normalization only.

A merchant appearing with a fraud_ prefix in the synthetic source does not mean that the merchant itself should be interpreted as a confirmed fraudulent business.

### 16.5 Transaction Amount

The underlying `amt` field remains numeric.

For Power BI presentation, the field is formatted as **USD currency**.

For example:

`1061.81 → $1,061.81`

This allows the field to remain numeric and aggregatable while providing a
business-readable presentation.

The documentation therefore refers to the dashboard value as **transaction amount displayed in USD**, rather than implying independently verified currency metadata.

### 16.6 Fraud Probability

The underlying `fraud_probability` is stored as a decimal value between `0` and `1`.

Power BI displays it as a **percentage**.

Examples:

```text
0.00916 → 0.92%
0.07990 → 7.99%
0.97320 → 97.32%
```

This percentage representation is appropriate for the dashboard because it makes model probabilities easier for business users to interpret.

### 16.7 Event Time

The underlying field:

`event_time`

represents the transaction event timestamp.

For transaction investigation, the semantic meaning of the field should remain event timestamp, rather than being reduced to a reporting date.

Power BI may automatically expose a date hierarchy containing: 

```text
Year
Quarter
Month
Day
```

when a date/time field is added to a visual.

For the investigation table, the underlying `event_time` field should be used when the actual transaction timestamp is required, particularly when time-of-day is relevant to fraud investigation.

The derived model feature:

`transaction_hour`

is retained separately for ML analysis.

### 16.8 Power BI Evidence

Screenshot:

`docs/evidence/day08-powerbi-transaction-investigation.PNG`

The screenshot demonstrates the transaction-level investigation interface, including filtering, transaction context, engineered risk indicators, and model-derived risk information.

---

## 17. Business Metric Definitions

The Power BI dashboard uses the following terminology.

### Transaction Count

Number of scored transactions in the serving population.

### Flagged Transactions

Transactions where:

`predicted_fraud = 1`

using the current model threshold of `0.50`.

### Flagged Transaction Value

The sum of transaction amounts associated with model-flagged transactions.

This should not be described as:  
- confirmed fraud loss;
- realized fraud loss;
- recovered fraud; or
- realized revenue.

The value represents the transaction amount associated with model flags.

### Average Fraud Probability

The average XGBoost fraud probability across the filtered transaction population.

Power BI displays this value as a percentage.

### Anomaly Rate

The proportion of the evaluation population identified as anomalous by the Isolation Forest model.

### Normal Group Fraud Rate

The observed fraud rate among transactions classified as normal by the Isolation Forest evaluation.

### Anomaly Group Fraud Rate

The observed fraud rate among transactions classified as anomalous by the Isolation Forest evaluation.

### DQ Pass Rate

The proportion of received records that passed the pipeline's current data-quality processing.

---

## 18. Training and Serving Separation

The Gold scored transaction output contains descriptive fields in addition
to model features.

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

These additional columns are retained for analytical serving but are not model inputs.

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

Persisting the engineered features in Gold also makes the scoring output traceable and avoids requiring downstream consumers to reproduce the feature engineering logic.

---

## 19. Cloud Shell Resource Consideration

An initial scoring approach attempted to load and score the full transaction population, approximately 1.85 million rows, in Cloud Shell.

The process was terminated because of memory pressure.

The scoring scope was subsequently aligned with the existing 139,538-row streaming evaluation dataset.

This approach:  
- matches the existing model evaluation population;
- avoids unnecessary memory pressure in Cloud Shell;
- produces a reproducible serving dataset; and
- keeps model evaluation and transaction-level dashboard results directly traceable.

For a production-scale implementation, scoring would normally be moved into distributed or managed compute rather than relying on Cloud Shell memory.

---

## 20. Day 8 Evidence

The following artifacts provide evidence for the completed Day 8 serving and BI layer.

| Evidence                 | Location                                                    | Demonstrates                                         |
| ------------------------ | ----------------------------------------------------------- | ---------------------------------------------------- |
| Serving SQL              | `sql/serving/01_create_serving_layer.sql`                   | Six Synapse Serverless serving views                 |
| Scored transactions      | `gold/ml/scored_transactions/scored_transactions.parquet`   | 139,538 scored transactions                          |
| XGBoost metrics          | `gold/ml/xgboost_metrics.parquet`                           | Model and threshold evaluation                       |
| SHAP output              | `gold/ml/shap_feature_importance.parquet`                   | Global feature importance                            |
| Isolation Forest metrics | `gold/ml/isolation_forest_metrics.parquet`                  | Unsupervised anomaly evaluation                      |
| Pipeline DQ metrics      | `audit/dq_metrics/run_date=2026-09-28/dq_metrics.parquet`   | Validation and quarantine evidence                   |
| Power BI overview        | `docs/evidence/day08-powerbi-fraud-risk-overview.png`       | Consolidated transaction, ML, and pipeline dashboard |
| Power BI investigation   | `docs/evidence/day08-powerbi-transaction-investigation.png` | Transaction-level investigation interface            |
| Power BI data model      | `docs/evidence/day08-data-model.PNG`                        | Deliberate no-relationship analytical model          |

---

## 21. Day 8 Implementation Status

### Completed
- XGBoost model evaluation
- XGBoost threshold analysis
- Global SHAP analysis
- Isolation Forest evaluation
- Data-quality metrics
- Transaction-level XGBoost scoring
- Gold scored transaction output
- ADLS verification of scored transaction output
- Synapse Serverless database
- `serving` schema
- Six Synapse Serverless serving views
- Serving-layer validation
- Power BI connection to Synapse Serverless
- Power BI data-model design
- Fraud Risk Overview dashboard
- Transaction Investigation dashboard
- Power BI evidence screenshots
- Day 8 serving documentation
  
### Evidence of Power BI Implementation

The completed Power BI layer demonstrates:

```text
ADLS Gold / Audit
       ↓
Synapse Serverless SQL
       ↓
Curated Serving Views
       ↓
Power BI Desktop
       ↓
Business Overview
       +
Transaction Investigation
```

The model deliberately keeps the serving views at their native analytical grains rather than introducing artificial relationships.

---

## 22. Production Enhancements

The core Day 8 implementation is complete.

Potential production-scale enhancements include:  
- Persisted and versioned model artifacts rather than retraining during scoring.
- Managed identity or service-principal authentication for automated workloads.
- Power BI Service deployment and governed semantic models.
- Incremental and partition-aware serving.
- Model monitoring and drift detection.
- Alerting for pipeline and data-quality failures.
- Formal model governance and approval processes.
- A documented classification-threshold policy based on fraud costs and investigation capacity.
- Distributed or managed compute for larger-scale scoring.
- Row-level/local SHAP explanations for individual investigations.
- Automated refresh and deployment of the Power BI reporting layer.

These are future production enhancements and are not required to claim that the Day 8 portfolio implementation is complete.
