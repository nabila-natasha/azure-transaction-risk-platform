# Day 7 — Machine Learning and Risk Analytics

## Overview

Day 7 adds the machine learning layer to the Azure transaction risk platform.

The objective is to build a reproducible fraud-risk modelling workflow on top of the Silver transaction data produced by the Bronze-to-Silver processing layer.

The implementation uses:

* XGBoost for supervised fraud classification
* Isolation Forest for unsupervised anomaly detection
* SHAP for model explainability
* Lightweight offline feature-drift diagnostics
* ADLS Gen2 Gold outputs for ML evaluation evidence

The ML workflow is intentionally implemented as an offline portfolio-scale workflow rather than a production model-serving platform.

---

## Architecture

```text
                    SILVER
                       │
             ┌─────────┴─────────┐
             │                   │
      Historical Batch     December Streaming
      Jan 2019–Nov 2020       Dec 2020
             │                   │
             └─────────┬─────────┘
                       │
                Feature Engineering
                       │
          ┌────────────┼────────────┐
          │            │            │
       XGBoost    Isolation Forest  SHAP
          │            │            │
          │            │            └── Explanations
          │            │
          │            └── Anomaly Score
          │
          └── Fraud Probability
                       │
                       ▼
                     GOLD
                    gold/ml
                       │
          ┌────────────┼─────────────┐
          │            │             │
       XGBoost      Isolation       SHAP
       Metrics       Forest       Importance
                     Metrics
```

---

## 1. Training and Evaluation Strategy

A chronological split was used instead of randomly mixing all transactions.

### Training population

Historical Batch Silver data:

* Period: 2019-01-01 to 2020-11-30
* Rows: 1,712,856
* Fraud: 9,393
* Non-fraud: 1,703,463
* Fraud rate: 0.5484%

### Evaluation population

Later Streaming Silver data:

* Period: 2020-12-01 to 2020-12-31
* Rows: 139,538
* Fraud: 258
* Non-fraud: 139,280
* Fraud rate: 0.1849%

The model therefore learns from historical transactions and is evaluated on a later time period.

This provides a simple time-aware evaluation design and avoids randomly mixing future observations into the training population.

The two datasets were intentionally not combined for model training.

---

## 2. Feature Engineering

The ML workflow uses 11 numerical features.

### Transaction features

* `amt`

### Geographic and population features

* `city_pop`
* `lat`
* `long`
* `merch_lat`
* `merch_long`

### Temporal features

* `transaction_hour`
* `day_of_week`
* `month`

### Customer and geographic-distance features

* `customer_age`
* `distance_km`

### Derived features

`transaction_hour`, `day_of_week`, and `month` are derived from `event_time`.

`customer_age` is calculated from transaction time and date of birth.

`distance_km` is calculated using the Haversine formula between the customer and merchant coordinates.

The same feature-engineering logic is applied to both the historical training population and the later evaluation population.

No selected ML feature contained null values.

---

## 3. XGBoost Fraud Classification

XGBoost is the primary supervised fraud-risk model.

The target variable is:

```text
is_fraud
```

The model produces:

```text
fraud_probability
```

### Model configuration

```text
n_estimators      = 300
max_depth         = 6
learning_rate     = 0.05
subsample         = 0.8
colsample_bytree  = 0.8
objective         = binary:logistic
eval_metric       = aucpr
random_state      = 42
```

Because fraud is highly imbalanced, `scale_pos_weight` was calculated from the historical training population:

```text
scale_pos_weight = 181.35
```

This gives greater training weight to the minority fraud class.

---

## 4. XGBoost Evaluation

At the default probability threshold of 0.50:

```text
ROC-AUC:    0.9826
PR-AUC:     0.3622
Precision:  0.0606
Recall:     0.8450
```

Confusion matrix:

```text
[[135900   3380]
 [    40    218]]
```

The model identifies a large proportion of known fraud cases, but the low precision demonstrates the operational cost of classifying a rare event: many transactions flagged as fraud are not actually fraudulent.

For this reason, accuracy is not used as the primary evaluation measure.

PR-AUC, precision, recall, and threshold trade-offs provide more useful information for this highly imbalanced problem.

---

## 5. Threshold Analysis

The model probability threshold was evaluated at three values.

| Threshold | Precision | Recall |  TP |    FP | FN |      TN |
| --------: | --------: | -----: | --: | ----: | -: | ------: |
|      0.30 |    0.0374 | 0.8992 | 232 | 5,979 | 26 | 133,301 |
|      0.50 |    0.0606 | 0.8450 | 218 | 3,380 | 40 | 135,900 |
|      0.70 |    0.0973 | 0.7713 | 199 | 1,846 | 59 | 137,434 |

The threshold analysis demonstrates the trade-off between capturing more fraud and generating more false positives.

A lower threshold increases recall while producing more false positives.

A higher threshold reduces false positives while missing more known fraud cases.

The project does not prescribe a single operational threshold because the appropriate threshold would depend on the business cost of false positives versus false negatives.

---

## 6. XGBoost Feature Importance

The model's built-in feature importance was:

| Feature            | Importance |
| ------------------ | ---------: |
| `amt`              |   0.528571 |
| `transaction_hour` |   0.265547 |
| `customer_age`     |   0.038183 |
| `city_pop`         |   0.031925 |
| `month`            |   0.022579 |
| `long`             |   0.021521 |
| `lat`              |   0.020492 |
| `day_of_week`      |   0.019167 |
| `merch_long`       |   0.018730 |
| `merch_lat`        |   0.017371 |
| `distance_km`      |   0.015914 |

The model relied most heavily on transaction amount and transaction hour in this experiment.

These values describe model behavior and should not be interpreted as causal relationships.

---

## 7. Isolation Forest Anomaly Detection

Isolation Forest provides a separate unsupervised anomaly signal.

Unlike XGBoost, it was not trained using the `is_fraud` target.

The model was fitted on a fixed random sample of 100,000 historical training transactions.

Configuration:

```text
n_estimators  = 200
max_samples   = 10,000
contamination = auto
random_state  = 42
```

The resulting anomaly score is independent of the supervised fraud probability.

Higher anomaly scores indicate observations that the Isolation Forest considers more unusual.

---

## 8. Isolation Forest Results

On the December evaluation population:

```text
Evaluation transactions: 139,538
Anomalies detected:        16,381
Normal transactions:      123,157
Anomaly rate:               11.7395%
```

Diagnostic comparison against the known fraud labels:

```text
ROC-AUC: 0.8198
PR-AUC:  0.0125
```

Fraud rate by anomaly group:

```text
Normal transactions:
123,157 transactions
Fraud rate: 0.0820%

Anomalous transactions:
16,381 transactions
Fraud rate: 0.9584%
```

The anomalous group therefore contains a higher observed fraud rate than the normal group.

However, Isolation Forest remains an **unsupervised anomaly detector**, not a supervised fraud classifier. The fraud labels were used only for diagnostic comparison after the model was fitted.

---

## 9. SHAP Explainability

SHAP was used to explain the XGBoost model at both global and individual levels.

A reproducible sample of 5,000 December evaluation transactions was used for SHAP analysis.

### Global SHAP importance

Mean absolute SHAP values:

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

SHAP provides a different perspective from the model's built-in feature importance.

Mean absolute SHAP values describe the average magnitude of each feature's contribution to model output.

---

## 10. Individual SHAP Explanation

The highest fraud-probability transaction in the 5,000-row SHAP sample had:

```text
Fraud probability: 0.996335
Actual fraud:      1
Amount:            720.83
Transaction hour:  2
Customer age:      32.71
Distance:          66.28 km
```

The largest local SHAP contributors were:

```text
amt                 +4.323833
transaction_hour    +0.962906
customer_age        +0.372294
month               -0.330435
city_pop            +0.142429
```

A positive SHAP value pushes the prediction toward the model's fraud class relative to the model's baseline, while a negative value pushes it in the opposite direction.

This provides an example of moving beyond a simple prediction and identifying which features contributed to an individual model decision.

---

## 11. Offline Drift Diagnostics

A lightweight diagnostic was added to compare the historical training population with the December evaluation population.

The comparison includes:

* mean
* median
* standard deviation
* percentage change in mean
* fraud-rate comparison

Selected observations:

```text
Amount mean:
Training       70.1648
Evaluation     68.8209
Change         -1.9153%

Transaction hour mean:
Training       12.8100
Evaluation     12.7588
Change         -0.3998%

Customer age mean:
Training       46.2001
Evaluation     47.0469
Change         +1.8330%

Distance mean:
Training       76.1100
Evaluation     76.1335
Change         +0.0310%
```

The geographic features and transaction-hour distribution were relatively stable.

The `month` feature differs substantially because the training population spans January 2019 through November 2020, while the evaluation population consists entirely of December 2020 transactions. Therefore, the month difference is an expected consequence of the chronological evaluation design rather than evidence of a production data-quality problem.

The fraud rate changed from:

```text
Training:   0.5484%
Evaluation: 0.1849%
Change:    -0.3635 percentage points
```

These diagnostics are descriptive only.

They do not constitute production drift monitoring and do not automatically trigger model retraining.

---

## 12. Gold ML Outputs

Validated Day 7 results are persisted under:

```text
gold/ml/
```

### XGBoost metrics

```text
gold/ml/xgboost_metrics.parquet
```

Contains:

* ROC-AUC
* PR-AUC
* precision
* recall
* threshold
* true positives
* false positives
* false negatives
* true negatives

### Isolation Forest metrics

```text
gold/ml/isolation_forest_metrics.parquet
```

Contains:

* ROC-AUC diagnostic
* PR-AUC diagnostic
* evaluation row count
* anomaly count
* normal transaction count
* anomaly rate
* fraud rate for normal transactions
* fraud rate for anomalous transactions

### SHAP feature importance

```text
gold/ml/shap_feature_importance.parquet
```

Contains:

* feature
* mean absolute SHAP value
* feature rank

These Gold datasets provide machine-readable evidence of the validated ML results for downstream analytics or reporting.

---

## 13. Reproducibility

The ML environment is pinned in `requirements.txt`:

```text
xgboost==3.4.1
scikit-learn==1.9.1
shap==0.52.0
```

The main ML scripts are:

```text
scripts/
├── prepare_ml_dataset.py
├── train_xgboost.py
├── train_isolation_forest.py
├── explain_xgboost_shap.py
├── profile_ml_drift.py
└── write_ml_gold_outputs.py
```

All models use `random_state=42` where applicable.

The chronological data split and feature engineering are reproduced consistently across the ML scripts.

---

## 14. Day 7 Deliverables

Day 7 completed the following:

* Chronological ML train/evaluation split
* Feature engineering
* Highly imbalanced fraud classification
* XGBoost supervised model
* Precision/recall and PR-AUC evaluation
* Confusion matrix
* Probability threshold analysis
* Isolation Forest anomaly detection
* Diagnostic comparison of anomaly scores against fraud labels
* Global SHAP explanations
* Individual SHAP explanation
* Offline feature-distribution diagnostics
* Fraud-rate drift comparison
* Gold ML evaluation outputs
* Reproducible ML dependencies

The resulting architecture separates:

```text
Supervised risk prediction
        +
Unsupervised anomaly detection
        +
Model explainability
        +
Offline drift diagnostics
```

This completes the machine learning vertical slice of the Azure transaction risk platform.
