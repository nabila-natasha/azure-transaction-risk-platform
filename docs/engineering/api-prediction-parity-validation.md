# API Prediction Parity Validation

## 1. Purpose of This Document

This document records the engineering rationale, implementation, validation
results, and limitations of the API prediction parity test implemented in
`scripts/replay_parity.py`.

The purpose is to explain not only what was tested, but why the test matters
when moving a machine learning model from an offline data-processing workflow
into an API service.

The validation compares predictions already stored in the Gold dataset with
predictions returned by the locally running FastAPI service when the same
transactions are submitted to it.

The test is designed to detect deployment and inference inconsistencies,
including:

- The API loading an unexpected model version or model run.
- The API deriving features differently from the existing scoring workflow.
- Prediction probabilities changing unexpectedly.
- Fraud classifications or risk bands differing from the Gold results.
- The API returning incorrect model metadata.
- Missing or incorrectly matched transaction records between Silver and Gold.
- API request failures during replay.

This is a prediction parity and deployment-correctness test. It is not a
replacement for model evaluation, fraud-detection performance measurement,
security testing, or production monitoring.

## 2. Background: How the Project's Data and Model Fit Together

The transaction risk platform separates data preparation, model training,
offline scoring, and API inference.

The relevant data flow is:

1. **Silver batch transactions**
   - Contains 1,712,856 transaction records.
   - Covers the batch training period from 2019-01-01 to 2020-11-30.
   - Supplies the data used to train the XGBoost classifier.

2. **Saved model artifact**
   - Model run ID: `20261012T024013Z`.
   - Model version: `xgboost-v1`.
   - Default classification threshold: `0.5`.
   - The artifact includes the model and its manifest, which describes the
     training run and expected feature contract.

3. **Silver streaming transactions**
   - Contains 139,538 transaction records from the December 2020 replay.
   - Supplies the raw transaction fields needed to reproduce API requests.
   - Despite the name "streaming", these records are replayed from stored
     files for this offline validation; this test is not a live streaming
     throughput or latency test.

4. **Gold scored transactions**
   - Contains 139,538 previously scored transaction records.
   - Stores the existing fraud probabilities, predicted classes, risk bands,
     model version, threshold, and transaction event IDs.
   - Acts as the reference output for the parity comparison.

5. **FastAPI inference service**
   - Loads the saved model in local mode.
   - Accepts raw transaction fields through the prediction endpoint.
   - Derives the model features, runs inference, and returns a prediction
     together with model metadata.

The intended comparison is:

    Raw Silver transaction
             |
             v
       FastAPI /predict
             |
             v
       API prediction
             |
             +-------------------+
                                 |
                                 v
                     Compare with Gold prediction
                                 ^
                                 |
                       Gold scored transaction

The API and Gold predictions must refer to the same transaction. Therefore,
the replay script joins Silver and Gold using `event_id`, rather than assuming
that the records appear in the same row order.

## 3. Why Prediction Parity Is Needed

A model can perform well during training and offline evaluation but still
produce inconsistent results when deployed behind an API.

For example, the offline scoring process may derive a transaction's hour,
customer age, or geographic distance in one way, while the API derives one
of those features differently. The model file may be correct, but a mismatch
in feature preparation can change its prediction.

Other potential problems include:

- Loading a different model artifact from the intended one.
- Using a different classification threshold.
- Changing the order or names of input features.
- Returning a risk band that does not agree with the probability or class.
- Returning stale or incorrect model-version metadata.
- Failing to handle a valid request correctly.

Prediction parity helps identify these issues by submitting the same raw
transaction to the API and comparing the result against its existing Gold
prediction.

A successful result provides evidence that the API reproduces the reference
scoring behavior for the tested transactions.

### Analogy

Think of Gold as a reference answer sheet and the API as a second person
solving the same questions.

We first make sure that both are answering the same questions by matching
their transaction IDs. We then compare their answers and relevant metadata.

If the answers match consistently, that supports the conclusion that the API
is applying the model and inference logic consistently with the reference
results.

It does not prove that the original answer sheet is correct in the real world.
That requires separate model evaluation and validation against appropriate
ground-truth outcomes.

## 4. Validation Environment

The parity test was executed against a locally running API in Azure Cloud
Shell, using the saved model artifact downloaded and verified outside the
Azure data-processing workflow.

The API was configured in local model mode, so the inference request did not
need to load the model from ADLS for every prediction.

The API exposed the following relevant endpoints:

- `GET /health`: checks whether the API is healthy.
- `GET /model-info`: reports model metadata and requires `X-API-Key`.
- `POST /predict`: returns a prediction and requires `X-API-Key`.

The test used the following expected model settings:

| Setting | Value |
|---|---|
| Model version | `xgboost-v1` |
| Expected model run ID | `20261012T024013Z` |
| Classification threshold | `0.5` |
| Probability comparison tolerance | `1e-6` |
| API base URL | `http://localhost:8000` |
| Silver source | `silver/transactions/streaming` |
| Gold reference | `gold/ml/scored_transactions/scored_transactions.parquet` |

The API key was supplied through an environment variable rather than being
included as a literal secret in the replay script.

The expected run ID is configured separately so that the test can fail if
the API unexpectedly loads a different model run.

## 5. Model Feature Contract

The XGBoost model expects the following 11 derived or numerical features:

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

The replay script submits the raw transaction fields expected by the API.
The API derives the model features and runs inference.

This is important because the test validates the API's complete inference
path, including feature derivation, rather than only calling the model object
directly with a preconstructed feature vector.

The feature contract reported by the API was checked against the expected
model information.

## 6. What the Replay Script Does

The implementation is in `scripts/replay_parity.py`.

### Step 1: Check API health and model information

The script calls `/health` and `/model-info` before replaying transactions.

It verifies that the service is reachable and that the model version, run ID,
feature list, and threshold are available.

The replay stops if the reported model run does not match the expected run
ID. This avoids silently validating predictions from an unintended model.

### Step 2: Read Silver and Gold data

The script reads the Silver streaming Parquet files from ADLS and reads the
Gold scored-transactions Parquet file.

It checks the expected columns and examines the transaction identifiers
before joining the datasets.

### Step 3: Match transactions by event ID

The script matches Silver and Gold records using `event_id`.

This is essential because the order of rows in two Parquet datasets is not
guaranteed to be identical.

The validation checks for duplicate identifiers and reports the number of
matched and unmatched records. It does not assume that matching row counts
alone prove that the datasets contain the same transactions.

### Step 4: Check the Gold model metadata

The script checks that the Gold model version and threshold agree with the
model information returned by the API.

The Gold dataset contains `model_version` and `model_threshold`, but it does
not contain `model_run_id`. Therefore, the API's run ID is compared with the
explicitly configured expected run ID. The script cannot independently prove
from the Gold dataset alone that Gold was generated by that exact training
run.

### Step 5: Select a sample across risk bands

The script supports a configurable sample size:

    python scripts/replay_parity.py --sample-size 100

For the larger validation, the following command was used:

    python scripts/replay_parity.py --sample-size 1000

The selected sample covers the Low, Medium, and High Gold risk bands. The
larger replay used 1,000 records, with 334 Low, 333 High, and 333 Medium
records selected.

This balanced sample is useful for checking API behavior across different
prediction-risk categories. It is not a prevalence-weighted sample of all
transactions, so the distribution must not be interpreted as the natural
distribution of transaction risk in the full dataset.

### Step 6: Replay each raw transaction through the API

For every selected transaction, the script submits the required raw fields
to `POST /predict`.

It then compares the returned prediction with the Gold reference for the
same `event_id`.

### Step 7: Save evidence

The script writes three files under `docs/evidence/parity/`:

- `summary.json`: overall counts, configuration, metadata, and pass/fail
  result.
- `details.csv`: row-level comparison results.
- `mismatches.csv`: rows that did not pass the parity checks.

The evidence uses hashed event identifiers rather than storing raw
transaction fields in the comparison files. These hashes support consistent
matching within the evidence without reproducing the original identifiers.

The files are validation evidence, not a substitute for protecting the
underlying source datasets and API credentials.

## 7. Checks Performed for Each Replayed Transaction

Six comparisons are recorded for each transaction.

| Check | What it verifies | Why it matters |
|---|---|---|
| Probability match | Absolute difference between API and Gold fraud probabilities is no greater than `1e-6`. | Detects changes in model inference or feature preparation. |
| Class match | API `predicted_fraud` equals the Gold predicted class. | Confirms the resulting binary classification agrees. |
| Risk-band match | API risk band equals the Gold risk band. | Confirms the API's risk categorisation agrees with the reference. |
| Model-version match | API model version equals the Gold model version. | Detects a version mismatch. |
| Run-ID match | API model run ID equals the configured expected run ID. | Detects an unintended API model run. Gold itself has no run-ID field. |
| Threshold match | API threshold equals the Gold threshold. | Confirms both use the same decision threshold. |

The probability tolerance allows for very small floating-point differences.
A tolerance of `1e-6` is sufficiently strict for this validation while
avoiding the assumption that every floating-point calculation must be
represented identically in every environment.

A passing probability comparison does not independently prove that the
probability is calibrated or that the model is accurate. It means the API
probability agrees with the stored reference within the specified tolerance.

## 8. Validation Results

### Dataset reconciliation

| Metric | Result |
|---|---:|
| Silver Parquet files | 5 |
| Silver streaming rows | 139,538 |
| Gold scored rows | 139,538 |
| Matched event IDs | 139,538 |
| Unmatched Silver IDs | 0 |

All 139,538 Silver streaming records matched Gold records by `event_id`.
There were no unmatched Silver identifiers.

This establishes that the datasets were successfully reconciled for the
replay workflow. It does not by itself prove that the contents of every
source field are correct or that the original fraud labels are correct.

### API model information

| Metric | Result |
|---|---|
| API health | Passed |
| API model version | `xgboost-v1` |
| API model run ID | `20261012T024013Z` |
| API threshold | `0.5` |
| Gold model version | `xgboost-v1` |
| Gold threshold | `0.5` |
| Gold run ID available | No |

The API returned the expected model version, run ID, and threshold. The Gold
version and threshold agreed with the API.

The run-ID limitation remains important: the expected run ID was checked
against API metadata, not independently verified from a run-ID field in Gold.

### Results of the 1,000-transaction replay

| Check | Passing records | Result |
|---|---:|---|
| Probability match | 1,000 / 1,000 | Pass |
| Predicted class match | 1,000 / 1,000 | Pass |
| Risk-band match | 1,000 / 1,000 | Pass |
| Model-version match | 1,000 / 1,000 | Pass |
| Expected run-ID match | 1,000 / 1,000 | Pass |
| Threshold match | 1,000 / 1,000 | Pass |
| API request errors | 0 | Pass |
| Mismatch rows | 0 | Pass |
| Overall replay result | `true` | Pass |

The replay completed all 1,000 requests without request errors. Every
record passed all six checks, and the mismatch report contained only its
header.

The recorded probability differences were zero for the inspected records.
The script nevertheless uses the configured tolerance rather than requiring
exact equality.

The saved summary was generated at:

    2026-10-14T03:07:47.553185+00:00

All results above refer to this specific 1,000-record replay and its saved
evidence.

### Automated test results

The project test suite was also executed:

    python -m pytest tests -q

Result:

    43 passed, 1 warning in 7.74s

The warning was a `StarletteDeprecationWarning` concerning the use of
`httpx` with `starlette.testclient`. It did not cause any tests to fail.
It should be reviewed as a dependency-maintenance item rather than treated
as a failed validation.

The repository whitespace check was run:

    git diff --check

It completed without reporting whitespace errors.

## 9. What These Results Prove

The results provide evidence that, for the 1,000 sampled transactions:

- The local API was reachable and returned model metadata.
- The API reported the expected model run and version.
- The API reproduced the Gold fraud probabilities within the configured
  tolerance.
- The API reproduced the Gold predicted classes and risk bands.
- The API used the same reported threshold as Gold.
- No request failures or parity mismatches occurred in the sample.
- The selected Silver records could be matched to Gold by `event_id`.
- The automated project test suite passed.

Taken together, these results support the conclusion that the tested API
inference path is consistent with the existing Gold scoring output for the
sample.

## 10. What These Results Do Not Prove

It is important not to overstate the validation.

### This is not a model-accuracy test

Parity compares the API with existing Gold predictions. If both the API and
Gold are wrong in the same way, parity can still pass.

Fraud detection performance must be evaluated separately against suitable
ground-truth labels using metrics such as precision, recall, PR-AUC, and
ROC-AUC, with appropriate consideration of class imbalance and the evaluation
design.

### This is not a production-load test

The requests were replayed sequentially against a local API. The test does
not establish production throughput, concurrent-request behavior, tail
latency, autoscaling behavior, or resilience under sustained load.

### This is not a full security assessment

The parity checks do not prove that authentication, authorization, secret
management, network controls, rate limiting, or all input-validation paths
are secure. Those concerns require separate tests and review.

### This does not validate every possible transaction

Only 1,000 of the 139,538 matched records were replayed through the API.
The full datasets were reconciled by event ID, but API parity was not tested
for every record.

### This does not independently establish the exact Gold model run

Gold contains the model version and threshold but not the model run ID.
The expected run ID was checked against the API, but the Gold artifact cannot
independently identify that same run from the available metadata.

### This does not establish real-world fraud outcomes

The replay demonstrates consistency with stored predictions, not whether
transactions were truly fraudulent or whether a financial institution would
have prevented losses.

## 11. How to Reproduce the Validation

### Prerequisites

- The repository and its Python environment are available.
- The required project dependencies are installed.
- Azure access is configured for reading the Silver and Gold Parquet files.
- The local model artifact is available and matches the expected run.
- The API is running on `http://localhost:8000`.
- The API key used by the replay script matches the running API's key.

Start the API in the first terminal using the project's documented local
model configuration. For the validation environment used in this run, the
configuration was:

    cd ~/azure-transaction-risk-platform
    source /tmp/transaction-risk-api-venv/bin/activate
    export MODEL_SOURCE=local
    export MODEL_DIR="$HOME/model-backup-20261012T024013Z"
    export MODEL_RUN_ID=20261012T024013Z
    export API_KEY=day3-local-test-key
    python -m uvicorn --factory api.main:create_app --host 0.0.0.0 --port 8000

Keep this terminal running while the replay executes in a second terminal.

In the second terminal, activate the project environment and configure the
expected run ID and API key:

    cd ~/azure-transaction-risk-platform
    source .venv/bin/activate
    export API_KEY=day3-local-test-key
    export EXPECTED_MODEL_RUN_ID=20261012T024013Z

Run a smaller smoke test:

    python scripts/replay_parity.py --sample-size 100

Then run the larger sample:

    python scripts/replay_parity.py --sample-size 1000

The script writes its evidence to:

    docs/evidence/parity/details.csv
    docs/evidence/parity/mismatches.csv
    docs/evidence/parity/summary.json

**Important:** The script overwrites these evidence files when it runs again.
Commit or copy evidence that you need to preserve before executing a new
replay.

After the replay, run the automated tests:

    python -m pytest tests -q

Then inspect the changes:

    git diff --check
    git status --short

The commands above reflect the Cloud Shell environment used for this
validation. A different machine or environment may require different
activation paths and credentials.

## 12. Evidence Files and Interpretation

### `summary.json`

This is the primary summary for the recorded run. It includes:

- Replay timestamp.
- Silver and Gold source paths.
- Row and identifier reconciliation counts.
- Requested and completed sample sizes.
- API model metadata and expected run ID.
- Probability tolerance.
- Counts for each parity check.
- Request-error and mismatch counts.
- Overall pass/fail result.
- The limitation concerning the absent Gold model run ID.

### `details.csv`

This provides a row-level record of the replay. It includes the hashed event
identifier, HTTP status, comparison results, probability values, class and
risk-band values, model metadata, threshold values, and a combined pass/fail
indicator.

It is useful for diagnosing individual mismatches without including the raw
transaction fields in the evidence file.

### `mismatches.csv`

This contains the records that failed one or more recorded checks. For the
successful 1,000-record replay, the file contains only its header, indicating
that there were no mismatch records.

An empty mismatch report should always be interpreted alongside the summary:
the request-error count and overall pass/fail status should also be checked.

## 13. Engineering Follow-ups

The following are useful future improvements, not prerequisites for
interpreting the successful run above:

1. Add the model run ID to Gold scoring metadata so that the exact model run
   can be traced from offline predictions to API inference.
2. Consider a full API replay when execution time and service capacity allow.
3. Add automated CI tests for feature derivation and representative parity
   fixtures that do not require live Azure access.
4. Review the Starlette/httpx deprecation warning and update dependencies
   deliberately, with tests.
5. Add separate tests for invalid inputs, missing API keys, incorrect API
   keys, and malformed requests.
6. Perform load and latency testing before making production-performance
   claims.
7. Ensure saved evidence, source datasets, and credentials follow the
   project's data-protection and access-control requirements.

## 14. Final Conclusion

The 1,000-transaction API prediction parity replay passed all six comparison
checks for every sampled transaction. There were no API request errors and
no mismatch records. All 139,538 Silver streaming records matched Gold by
event ID, and the automated test suite reported 43 passing tests.

These results provide strong evidence that the tested local FastAPI inference
path reproduces the existing Gold predictions for the sampled transactions.

The result should be described as **successful API prediction parity
validation**, not as proof of model accuracy, production readiness, or
production-scale performance. The missing model run ID in Gold remains a
documented traceability limitation.
