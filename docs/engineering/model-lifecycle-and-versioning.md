
# Model Lifecycle, Artifact Integrity, and Versioning

## 1. Purpose

This document describes how the transaction-risk model moves from offline
training to versioned artifact storage, validation, API loading, and inference.

The design separates model development from serving. The API consumes an
existing model instead of retraining it whenever the service starts.

## 2. Architecture and Responsibilities

| Component | Responsibility |
|---|---|
| Offline training process | Trains and evaluates a candidate model |
| `model.json` | Stores the serialized XGBoost model |
| `manifest.json` | Records model metadata, including the run ID and feature contract |
| `metrics.json` | Preserves the candidate's evaluation metrics |
| `SHA256SUMS` | Records expected SHA-256 hashes for artifact-integrity checks |
| Private model repository | Stores model artifacts separately from public application code |
| GitHub Actions | Retrieves and validates artifacts, builds the container, and tests the service |
| API container | Loads the mounted model and scores incoming transactions |

The public project repository contains application code and automation.
The model artifact repository is private so the serialized model is not
committed into the public application source.

## 3. Current Baseline

| Property | Value |
|---|---|
| Model run ID | `20261012T024013Z` |
| Model format | XGBoost JSON |
| Model file | `model.json` |
| Runtime artifact directory | `/models` |
| Expected feature count | 11 |
| Model loading | Load the saved artifact; do not retrain on API startup |

Expected feature names and order:

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

Feature names and order are part of the model's input contract. A model
that expects a different schema must not silently replace this baseline.

## 4. Artifact Integrity and Private Access

The CI workflow retrieves artifacts from the private repository using a
GitHub Actions secret containing a read-only repository access token.

The token is used for authentication; it must not be written into source
code, printed in logs, or included in the container image.

Before the model is used, the workflow verifies the recorded SHA-256
checksums. It also validates the expected model run ID and feature contract.

These checks serve different purposes:

- **Private access** controls who can retrieve the artifacts.
- **Checksums** detect whether files differ from the expected versions.
- **Manifest validation** checks that the selected artifacts identify the
  intended model version and input contract.
- **Inference tests** verify that the loaded model can actually score a
  transaction through the API.

A checksum confirms file integrity against the trusted checksum record;
it does not, by itself, prove that a model is accurate or trustworthy.

## 5. Container Loading and Inference

The Docker workflow builds the API image separately from the model artifacts.
At runtime, the model repository checkout is mounted read-only at `/models`.

This separation avoids baking the model into the application image and
allows model artifacts to be managed independently of API code.

The service is configured to load the selected local artifact using its
model configuration, including `MODEL_SOURCE`, `MODEL_DIR`, and
`MODEL_RUN_ID`. An API key is required for protected endpoints.

The prediction endpoint returns the model's fraud probability, predicted
class, risk band, and model run ID. The metadata endpoint exposes model
information for authorized inspection.

## 6. Automated Validation Evidence

The successful Docker GitHub Actions workflow validates the model-serving
path using the saved baseline model rather than a synthetic replacement.

The workflow includes:

- Retrieval of the private model artifacts
- SHA-256 checksum verification
- Validation of the expected run ID and feature contract
- Docker image build
- Container startup with model artifacts mounted at `/models`
- API health check
- Authentication failure checks
- Invalid-request validation
- Model metadata validation
- A successful prediction using the saved model
- Container cleanup

Successful workflow run: **[Insert the URL of the successful GitHub Actions run]**

This evidence demonstrates a tested containerized inference path. It does
not mean the API is publicly deployed or running continuously.

## 7. Repeatable Model-Update Procedure

A new model must be treated as a candidate release, not as an in-place
replacement of the working baseline.

1. Train and evaluate the candidate offline.
2. Assign a unique model run ID.
3. Save the model, manifest, metrics, and checksum file.
4. Validate the manifest's run ID and exact feature names and order.
5. Verify the checksum file against the candidate artifacts.
6. Store the candidate as a separate version in the private model repository.
7. Preserve the current baseline unchanged and record the candidate's
   immutable Git commit or release tag.
8. Update the workflow's private-repository reference and expected run ID
   to select the candidate. Keep the baseline reference available for rollback.
9. Run the complete GitHub Actions validation before accepting the candidate.
10. Promote the candidate only after all checks pass.

The workflow's repository reference and expected run ID must agree. Merely
changing the run ID without retrieving the matching artifacts is not a
valid model update.

## 8. Rollback

If a candidate fails checksum verification, violates the feature contract,
fails inference tests, or produces unacceptable evaluation results, do not
promote it.

Restore the previously approved artifact reference and matching run ID,
then rerun the validation workflow. Retaining an immutable baseline makes
rollback explicit and reproducible.

## 9. Engineering Trade-offs

- **Private repository:** Separates model access from public application code.
- **Checksum verification:** Detects unintended artifact changes before use.
- **Pinned model run ID:** Makes the selected model explicit and testable.
- **Separate model and image:** Keeps model releases independent of API image builds.
- **No training at startup:** Reduces startup work and prevents an API restart
  from unexpectedly producing a different model.
- **Automated inference tests:** Validate behavior, not just whether an image builds.

## 10. Limitations and Future Improvements

The current workflow validates a specific baseline model. A future
production implementation could add a formal model registry, automated
candidate evaluation thresholds, signed artifact provenance, deployment
approval gates, monitoring for model drift, and a documented promotion
process.

These are future enhancements, not capabilities claimed by the current
portfolio implementation.
