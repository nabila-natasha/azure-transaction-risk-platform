# ML Model Artifacts and Gold Metrics — 12 October 2026

## Objective

Improve reproducibility and traceability of the XGBoost fraud-scoring
workflow while preserving the existing Power BI Gold contract and
Azure DevOps CI/CD behavior.

## Completed

### 1. Reproducible XGBoost training artifacts

Updated `scripts/train_xgboost.py` to save the outputs of a training run
under `artifacts/ml/xgboost/`:

- `model.json`: trained XGBoost model.
- `metrics.json`: evaluation metrics and threshold analysis.
- `predictions.parquet`: evaluation predictions at thresholds 0.30, 0.50,
  and 0.70.
- `manifest.json`: run metadata, feature list, model parameters, data
  periods, and artifact filenames.

The artifacts were uploaded to the timestamped ADLS directory:

`gold/ml/artifacts/xgboost/20261012T024013Z/`

Timestamped run directories preserve the record of individual runs
instead of overwriting the previous run.

### 2. XGBoost Gold metrics sourced from training results

Updated `scripts/write_ml_gold_outputs.py` to support:

`python scripts/write_ml_gold_outputs.py --xgboost-only`

With this option, the script reads the local `metrics.json` and updates
only:

`gold/ml/xgboost_metrics.parquet`

The update completed successfully for run `20261012T024013Z`, writing
four rows: overall metrics and threshold-analysis rows for 0.30, 0.50,
and 0.70. The existing ten-column Gold metrics schema was preserved.

The `--xgboost-only` option returns before writing Isolation Forest
metrics or SHAP feature importance.

### 3. Evaluation baseline

Evaluation dataset: 139,538 rows, including 258 fraud-positive rows.

At threshold 0.50:

- ROC-AUC: approximately 0.9826
- PR-AUC: approximately 0.3622
- Precision: approximately 0.0606
- Recall: approximately 0.8450
- True positives: 218
- False positives: 3,380
- False negatives: 40
- True negatives: 135,900

The threshold results illustrate the trade-off between fraud detection
and false alarms. The evaluation period is used for reporting, not for
tuning the threshold.

## Work in progress

`scripts/score_transactions.py` currently trains a model when executed.
The intended improvement is to load a saved, versioned model instead.

Before implementing or releasing that change, validate:

- The exact ordered feature contract and feature engineering.
- Model artifact loading and manifest compatibility.
- The existing scored-transactions Gold path and column schema.
- Probability and prediction consistency.
- Existing automated tests and Azure DevOps CI/CD behavior.
- Power BI compatibility before replacing the existing Gold output.

The existing Gold scoring output must not be overwritten by an unvalidated
test run.

## Git and artifact policy

Generated local model artifacts should not be committed by default.
Commit source code, tests, and documentation. Keep versioned run artifacts
in ADLS and retain the manifest and metrics for traceability.

## Status

The training artifacts and XGBoost Gold metrics update are complete.
Model-loading changes, compatibility tests, CI/CD verification, and final
documentation remain pending.
