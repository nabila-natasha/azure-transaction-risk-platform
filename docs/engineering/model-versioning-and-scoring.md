# Model Versioning, Scoring Refactor, and Validation

## 1. Purpose of This Document

This document records the engineering decisions behind the saved XGBoost model, ADLS artifact storage, scoring-script refactor, automated tests, and read-only comparison against the existing Gold dataset.

It explains what was implemented, why each change was needed, what problem it addresses, how it was validated, and what limitations remain.

This is a technical reference for future maintenance, troubleshooting, portfolio explanations, and interviews.

---

## 2. Background: What Problem Were We Solving?

The platform already had a Gold dataset containing scored streaming transactions. The scoring workflow needed a reliable way to load the intended model and reproduce those scores.

Relying on an unspecified or locally saved model would make it harder to answer important questions:

- Which exact model produced these predictions?
- Are the model's expected input features consistent with the current data?
- Can the scoring job run without depending on a developer's local files?
- Can we validate a new scoring implementation without risking existing Gold data and the Power BI report?
- Can automated tests catch future changes that break this contract?

The changes introduce a more controlled model-loading and scoring workflow.

They do not, by themselves, establish a fully automated model registry, continuous retraining system, or production fraud-detection service.

## 3. High-Level Workflow

```text
Silver streaming transactions
             |
             v
Feature engineering
             |
             v
Validate the 11-feature contract
             |
             v
Load the pinned XGBoost model from ADLS
             |
             v
Generate fraud probabilities
             |
             v
Apply prediction threshold and risk bands
             |
             v
Validate the scoring output
             |
             v
Dry-run / read-only parity validation
             |
             v
Gold write only when explicitly required
```

The important separation is between generating and validating scores and writing those scores to the Gold dataset.

A successful dry run does not modify Gold. A parity comparison also reads the existing Gold dataset without modifying it.

---

## 4. Why We Refactored `scripts/score_transactions.py`

### 4.1 Previous Concern

A scoring job needs to use the intended trained model consistently. Depending on a local model file makes execution dependent on the files available in a particular environment.

It also makes it easier to accidentally score transactions using a different model from the one used to generate the existing Gold dataset.

### 4.2 Change Introduced

The scoring script was refactored to load a pinned model artifact from Azure Data Lake Storage (ADLS) rather than relying only on a local model file.

The configured model run ID is:

```text
20261012T024013Z
```

The model is loaded from:

```text
gold/ml/artifacts/xgboost/20261012T024013Z/model.json
```

The loader reads the model manifest and model data from ADLS, validates the expected run ID and feature list, loads the XGBoost model, and checks the model's feature names where available.

The loader retains local-loading behavior when no ADLS filesystem is provided, allowing unit tests to exercise the local model-loading path.

### 4.3 Why This Matters

- **Consistency:** The scoring job uses an explicitly selected model run.
- **Portability:** The model can be loaded from shared cloud storage.
- **Traceability:** The run ID identifies the selected artifact version.
- **Validation:** Incompatible feature contracts can be rejected before predictions are generated.
- **Testing:** The local-loading path remains useful for isolated tests.

### 4.4 What This Does Not Mean

A pinned run ID is a controlled reference, but it is not a complete model registry or deployment approval system.

The current run ID is configured in the script. A future improvement could move model selection into a configuration file or pipeline parameter, provided that the selected run is still validated and recorded.

The scoring script also needs appropriate Azure authentication and permissions to read the artifact files from ADLS.

---

## 5. Why We Validate the 11-Feature Contract

The model expects these features in this order:

1. `amt`
2. `city_pop`
3. `lat`
4. `long`
5. `merch_lat`
6. `merch_long`
7. `transaction_hour`
8. `day_of_week`
9. `month`
10. `customer_age`
11. `distance_km`

### The Risk Without a Feature Contract

A model can receive data with the correct number of columns but the wrong meaning or order. For example, a distance value could accidentally be supplied where a transaction amount is expected.

That could produce misleading predictions without an obvious runtime error.

### The Control We Added

The loader validates the expected feature list against the model manifest and checks the model's feature names where available.

The feature-contract tests also exercise valid and invalid loading cases.

This is a compatibility check between the scoring code and the model artifact. It does not guarantee that every feature is statistically correct, current, or free of data-quality problems.

---

## 6. The Four Model Artifacts

The artifacts are stored under this ADLS prefix:

```text
gold/ml/artifacts/xgboost/20261012T024013Z/
```

| Artifact | Purpose | Why It Matters |
|---|---|---|
| `model.json` | Serialized XGBoost model | Allows the scoring process to reload the trained model without retraining it. |
| `manifest.json` | Run and artifact metadata, including the model run ID and feature contract | Helps identify the intended model version and validate compatibility. |
| `metrics.json` | Recorded model evaluation metrics | Preserves evaluation results for review and comparison. |
| `predictions.parquet` | Saved prediction output from the model workflow | Provides structured prediction data for later inspection and reproducibility checks. |

These files serve different purposes. The model contains the learned model structure and parameters; the manifest describes the run; the metrics record evaluation results; and the Parquet file stores prediction data.

Keeping them together under a run-specific prefix makes it easier to associate the model with its metadata and recorded results.

### Important Distinction

Storing four artifacts is not the same as having a complete model registry. A more mature implementation could add automated model promotion, approval status, artifact checksums, retention rules, and a pipeline-driven selection mechanism.

The presence of saved predictions also does not, by itself, prove that those predictions can be reproduced. Reproducibility requires compatible input data, feature engineering, model settings, and validation.

---

## 7. Model Results and Interpretation

The recorded evaluation results include approximately:

| Metric | Recorded Value |
|---|---:|
| ROC-AUC | 0.9826 |
| PR-AUC | 0.3622 |

The dataset is highly imbalanced, so ROC-AUC alone is not sufficient to judge the model's usefulness.

At the 0.50 threshold, the recorded validation results were approximately:

| Measure | Value |
|---|---:|
| Precision | 0.0606 |
| Recall | 0.8450 |
| True positives | 218 |
| False positives | 3,380 |
| False negatives | 40 |
| True negatives | 135,900 |

The high recall comes with many false positives. In a real transaction-risk workflow, these predictions would require an appropriate investigation process, threshold selection, cost analysis, and additional validation.

These results demonstrate an ML engineering workflow on simulated data. They should not be presented as proof of production fraud-detection performance or real financial loss prevention.

---

## 8. Why We Added `tests/test_score_transactions_contract.py`

### Problem Addressed

A model-loading refactor can introduce regressions even if the main scoring script appears to work on one dataset.

Examples include:

- An unexpected feature list
- A missing model file
- A model that cannot be loaded
- A mismatch between the declared and actual model features

### Test Coverage Added

The new contract tests cover three cases:

1. A saved model can be loaded when the feature contract matches.
2. A mismatched feature list is rejected.
3. A missing model raises an error.

These tests complement the existing data-quality, feature-engineering, ML-contract, and model-smoke tests.

### Why Test Failures Should Stop the Pipeline

A test failure is a signal that a change may have broken expected behavior. Catching it in CI is preferable to discovering the issue after the scoring job has run or a downstream report has been affected.

The tests do not prove that every cloud permission, network connection, or live ADLS operation will always work. They validate the behaviors covered by the test cases.

---

## 9. Why We Added ADLS Model Loading

The scoring script now supports loading the pinned model directly from ADLS using the configured filesystem client.

This reduces dependence on a model file being present in the current working directory and aligns model selection with the shared artifact location.

The ADLS loader validates the manifest's run ID and feature contract before using the model.

### Operational Considerations

- The executing identity needs permission to read the relevant ADLS files.
- The artifact prefix and run ID must exist.
- The model and manifest must belong to the intended run.
- Authentication failures and missing artifacts should be investigated rather than silently bypassed.
- The local-loading path remains useful for unit tests, but the validated cloud path is the one used by the current scoring entry point.

---

## 10. Why We Ran a Dry Run Before Considering a Gold Write

The scoring script supports a dry-run mode.

A dry run lets us validate the number of scored transactions, output columns, prediction values, and risk-band distribution without writing the results to Gold.

The successful dry run reported:

| Validation Measure | Result |
|---|---:|
| Scoring rows | 139,538 |
| Output columns | 32 |
| Low risk | 133,327 |
| Medium risk | 4,166 |
| High risk | 2,045 |
| Predicted fraud = 0 | 135,940 |
| Predicted fraud = 1 | 3,598 |

The output checks also cover duplicate transaction IDs and probability values outside the valid range.

### Why This Matters

Gold is consumed by downstream analytics, including the Power BI report. Overwriting it without validating the output could introduce unexpected changes into those reports.

A dry run provides a lower-risk checkpoint before any write operation.

---

## 11. Why We Compared New Scores with Existing Gold

After switching to ADLS model loading, we ran a read-only parity comparison.

The comparison:

1. Loaded the streaming Silver transactions.
2. Recreated the model features.
3. Loaded the pinned model from ADLS.
4. Generated new fraud probabilities.
5. Read the existing Gold Parquet dataset.
6. Matched records using `trans_num`.
7. Compared probabilities, predicted-fraud labels, and risk bands.

The comparison used one-to-one transaction ID matching and checked for duplicate IDs.

### Recorded Results

| Validation | Result |
|---|---:|
| Existing Gold rows | 139,538 |
| Matched rows | 139,538 |
| Maximum probability difference | 0 |
| Prediction disagreements | 0 |
| Risk-band disagreements | 0 |
| Gold modified | No |

### Why We Did Not Rewrite Gold

The newly generated scores exactly matched the existing Gold results. There was therefore no demonstrated scoring change that required a Gold rewrite.

Keeping Gold untouched avoided an unnecessary write and preserved the existing dataset used by downstream analytics.

### What Parity Proves—and What It Does Not

The comparison establishes that the current scoring implementation, using the selected model and the compared input data, reproduces the existing Gold probabilities and classifications.

It does not prove that the model is accurate in the real world, that the input data is free from all errors, or that a different model version would produce the same results.

It also does not test a Gold write. No write was performed during this validation.

---

## 12. Automated Validation and CI

The current validation milestone includes:

- 19 Python tests passing locally
- Azure DevOps CI completing successfully for the scoring refactor
- A successful dry run using the pinned model in ADLS
- A read-only comparison against the existing Gold dataset
- Zero differences in the compared probabilities, predictions, and risk bands

### Commands Used

Run the automated tests:

```bash
pytest -q
```

Run the scoring script in dry-run mode using its supported CLI option:

```bash
python scripts/score_transactions.py --dry-run
```

The second command should only be used if the script's current CLI configuration still exposes `--dry-run`. Confirm with:

```bash
python scripts/score_transactions.py --help
```

The read-only parity check was run as a separate Python snippet. It should not be confused with the unit tests or with a Gold write.

### Commit History Associated with This Work

- `1d68f3f` — `feat: version XGBoost training artifacts`
- `51355f1` — `refactor: score transactions with saved XGBoost model`
- `d5d7794` — `refactor: load pinned XGBoost model from ADLS`

These commits represent successive stages of artifact versioning, saved-model scoring, and cloud-based model loading.

Use `git show <commit>` to inspect the exact changes in the repository.

---

## 13. Troubleshooting Reference

### Tests Fail After Changing the Feature List

Check the feature list in the scoring code, the manifest, and the model. The model and scoring contract must agree.

### The Model Cannot Be Loaded from ADLS

Check:

- The configured run ID
- The artifact directory and filenames
- The Azure identity used by Cloud Shell or the pipeline
- Storage permissions
- Whether the files are present in ADLS

Do not silently switch to another model if the pinned model cannot be read.

### Dry-Run Row Counts Differ

Check the streaming Silver source, filters, transaction ID uniqueness, and feature-engineering logic before considering any Gold write.

### Parity Comparison Shows Differences

Do not overwrite Gold immediately. First investigate:

- Whether the same source records were used
- Whether the same model run was loaded
- Whether feature engineering changed
- Whether the probability threshold or risk-band boundaries changed
- Whether transaction IDs match one-to-one

Document the reason for any expected difference before approving a downstream data update.

### A CI Test Fails

Reproduce the failure locally where possible, identify the regression, and fix the underlying issue. Do not remove or weaken a test merely to make the pipeline green.

---

## 14. Interview Explanation

### Short Version

"I versioned the XGBoost training artifacts in ADLS and refactored the scoring job to load a pinned model version. The job validates the model's feature contract before scoring. I added tests for valid and invalid model loading, then ran a dry run and compared the new output with the existing Gold dataset. All 139,538 transaction IDs matched, with zero differences in probabilities, predicted-fraud labels, or risk bands. Since the results were identical, I left Gold untouched rather than performing an unnecessary write."

### Why This Is an Engineering Decision, Not Just an ML Exercise

The work addresses model artifact management, data/model compatibility, automated regression testing, safe validation, and protection of downstream analytics.

It demonstrates a controlled approach to changing a data pipeline rather than simply training a model and replacing an existing dataset.

### Limitations to State Honestly

- The transaction dataset is simulated.
- The model has not been established as suitable for real financial-risk decisions.
- Artifact versioning is implemented, but this is not a complete model registry or automated model-promotion framework.
- The parity check validates equivalence with the existing Gold output; it does not establish real-world model effectiveness.
- The parity check and dry run did not modify Gold.

---

## 15. Current Status and Next Improvements

### Completed and Validated

- Versioned XGBoost artifacts stored in ADLS
- Pinned model run configured for scoring
- ADLS model-loading path implemented
- Feature contract validated
- Model-loading contract tests added
- 19 tests passed
- Azure DevOps CI succeeded
- Dry-run scoring completed
- Read-only parity comparison completed
- Existing Gold left unchanged

### Potential Future Improvements

These are possible next steps, not claims that they are already implemented:

- Move the model run ID into controlled pipeline configuration.
- Add checksums or hashes to detect artifact corruption.
- Add explicit model approval and promotion metadata.
- Record scoring-run metadata and counts in a monitoring table.
- Add a controlled, separately approved Gold publication step.
- Monitor precision, recall, false-positive volume, and data drift when representative ground-truth data becomes available.
- Define rollback behavior for a future model or scoring change.
