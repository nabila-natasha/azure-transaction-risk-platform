# Transaction Risk Scoring API — Implementation and Operations Guide

## 1. Overview

This document describes the implementation, validation, operation, and troubleshooting of the transaction risk scoring API within the Azure Transaction Risk Analytics Platform.

The API exposes the existing XGBoost model through FastAPI and provides a browser-based interface for submitting transaction details and viewing prediction results.

The implementation covers API integration, input validation, model loading, authentication, automated testing, browser integration, and operational guidance.

### Objectives

- Expose the pinned XGBoost model through a REST API.
- Validate incoming transaction data before scoring.
- Protect model-information and prediction endpoints with API-key authentication.
- Provide a simple browser interface for interactive testing.
- Verify the API using automated tests and real-model smoke tests.
- Document how to run and troubleshoot the service across Cloud Shell, GitHub Codespaces, and local VS Code environments.

### Current implementation status

| Component | Status |
|---|---|
| FastAPI scoring service | Implemented and tested |
| Pydantic request validation | Implemented and tested |
| API-key authentication | Implemented and smoke-tested |
| Local loading of pinned model artifacts | Implemented and tested |
| Browser-based scoring interface | Implemented and tested |
| Cloud Shell Web Preview routing fix | Implemented and verified |
| Automated regression tests | 43 passed in the latest recorded run |
| ADLS-backed model-loading validation | Planned for follow-up |
| API-versus-Gold prediction parity | Planned for follow-up |

## 2. Architecture

```text
Browser
  |
  | Transaction details + X-API-Key
  v
HTML / CSS / JavaScript
  |
  | POST /predict
  v
FastAPI
  |
  | Validate raw input
  | Derive model features
  v
Pinned XGBoost model
  |
  | Fraud probability
  | Predicted class
  | Risk band
  v
JSON response
  |
  v
Browser displays prediction
```

The API uses the existing model rather than training a new model when a request arrives.

For the local demonstration, a previously trained model artifact is downloaded from ADLS and loaded from local storage. The API does not need to access ADLS for every prediction when using this local model configuration.

### Key model identifiers

| Setting | Value |
|---|---|
| Model version | `xgboost-v1` |
| Model run ID | `20261012T024013Z` |
| Decision threshold | `0.50` |
| Model type | XGBoost classifier |

## 3. Implementation phases

### Phase 1 — Baseline and repository review

The existing repository, model-loading logic, scoring code, requirements files, and tests were reviewed before integrating the API.

The purpose was to preserve the existing transaction-risk platform and introduce the API as an extension rather than replacing the existing data-engineering and analytics components.

### Phase 2 — API integration and dependency validation

The API implementation and supporting tests were integrated into the repository.

The API dependencies and API test dependencies were organized in separate requirements files. The implementation was validated in the pandas 3 environment.

The CI pipeline was updated to install the dependencies needed by the API tests before executing the test suite.

### Phase 3 — Model-serving API

The FastAPI application was configured to load the pinned model bundle, validate transaction requests, derive model features, and return predictions.

The application also implements API-key authentication for protected endpoints and request logging for operational troubleshooting.

### Phase 4 — Real-model smoke test

The API was started in Azure Cloud Shell, and the health, model-information, and prediction endpoints were tested.

A direct prediction request returned HTTP 200 with a valid JSON response from the real XGBoost model.

### Phase 5 — Browser interface and regression validation

A browser interface was created in `api/static/index.html`. The page provides transaction input fields, a sample-data button, and a result panel.

The first browser test revealed that Azure Cloud Shell Web Preview was routing requests to the wrong relay path. The request URL was corrected, the browser was refreshed, and prediction requests then succeeded.

The full regression test suite was rerun successfully.

## 4. API implementation details

### 4.1 Project files

The main files associated with the API are:

```text
api/
├── main.py
└── static/
    └── index.html

src/
├── model_store.py
├── scoring.py
└── features.py

tests/
└── api_service/
    ├── conftest.py
    └── test_api_service.py

requirements-api.txt
requirements-api-azure.txt
requirements-api-test.txt
```

The existing project may contain additional files and tests. This list highlights the main files involved in API serving.

| File | Responsibility |
|---|---|
| `api/main.py` | FastAPI application, routes, authentication, validation handling, and request logging |
| `api/static/index.html` | Browser interface, styling, form handling, and prediction display |
| `src/model_store.py` | Model configuration and loading |
| `src/scoring.py` | Model scoring and prediction outputs |
| `src/features.py` | Feature-engineering logic |
| `tests/api_service/` | API-specific tests |
| `requirements-api.txt` | API runtime dependencies |
| `requirements-api-azure.txt` | Additional dependencies for Azure-backed operation |
| `requirements-api-test.txt` | Dependencies needed to execute API tests |

### 4.2 Raw transaction input

The API accepts eight raw transaction fields:

| Field | Description |
|---|---|
| `event_time` | Transaction date and time |
| `dob` | Customer date of birth |
| `amt` | Transaction amount |
| `city_pop` | Population of the customer's city |
| `lat` | Customer latitude |
| `long` | Customer longitude |
| `merch_lat` | Merchant latitude |
| `merch_long` | Merchant longitude |

The date fields use datetime validation. Numerical fields have defined range constraints, and additional validation checks that the date of birth precedes the transaction time and that customer age does not exceed 120 years.

Extra request fields are rejected rather than silently accepted.

### 4.3 Derived model features

The API derives the following 11 features for the model:

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

This design keeps feature engineering on the server. The browser submits raw transaction information rather than constructing the model feature vector itself.

### 4.4 API endpoints

| Method | Endpoint | Purpose | Authentication |
|---|---|---|---|
| GET | `/` | Serves the browser interface | Not required |
| GET | `/health` | Checks service health | Not required |
| GET | `/model-info` | Returns model version, run ID, features, and threshold | API key |
| POST | `/predict` | Scores a transaction | API key |
| GET | `/docs` | Provides FastAPI's interactive API documentation | Not required by the current configuration |

The current implementation requires an API key for `/model-info` and `/predict`. The health endpoint is intentionally public for basic service checks.

The API logs request metadata, including request ID, HTTP method, path, status code, latency, and model run ID where available. Validation errors omit submitted input values from the error response.

## 5. Running the API in Azure Cloud Shell

### 5.1 Prerequisites

The Cloud Shell environment must have:

- The project repository available.
- The required Python dependencies installed.
- The pinned model artifacts available locally.
- A valid `API_KEY` environment variable.

The model files used for the demonstration were stored in:

```text
/tmp/transaction-risk-model/
├── manifest.json
└── model.json
```

The model directory was populated by downloading the artifacts from ADLS.

**Important:** `/tmp` is temporary storage. Its contents may disappear after a session or environment restart. The model files must be downloaded again if they are no longer available.

### 5.2 Configure environment variables

From the repository root, configure the model and API settings:

```bash
export API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export MODEL_SOURCE=local
export MODEL_DIR=/tmp/transaction-risk-model
export MODEL_RUN_ID=20261012T024013Z
```

The generated key is a secret. Do not commit it, paste it into project documentation, or expose it in screenshots.

To display the key in your private terminal when you need to enter it in the browser, run:

```bash
echo "$API_KEY"
```

If the API server was started before a new key was generated, restart the server. The running process uses the key it received when it started.

### 5.3 Start Uvicorn

Run the following command from the repository root:

```bash
uvicorn --factory api.main:create_app \
  --host 127.0.0.1 \
  --port 8000 \
  > /tmp/risk-api.log 2>&1 &

echo $! > /tmp/risk-api.pid
sleep 2
cat /tmp/risk-api.log
```

The log should indicate that the application startup completed and Uvicorn is listening on port 8000.

If startup fails, inspect `/tmp/risk-api.log` before retrying.

### 5.4 Test the health endpoint

```bash
curl -i http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The HTTP status should be `200 OK`.

### 5.5 Test the model-information endpoint

```bash
curl -i \
  -H "X-API-Key: $API_KEY" \
  http://127.0.0.1:8000/model-info
```

A successful response includes the model version, run ID, expected features, and threshold.

### 5.6 Submit a prediction

```bash
curl -i -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "event_time": "2026-10-13T13:15:00",
    "dob": "1994-02-26T00:00:00",
    "amt": 5000,
    "city_pop": 20000,
    "lat": 48.8878,
    "long": -100.9893,
    "merch_lat": 40.351813,
    "merch_long": -122.230347
  }'
```

This is a reproducible example of a direct backend request. It uses a fixed transaction timestamp, which is important when comparing results across environments.

## 6. Browser interface

### 6.1 User interface implementation

The file `api/static/index.html` contains the page structure, styling, and JavaScript.

The interface provides:

- API-key entry through a password field.
- Transaction date and time.
- Transaction amount and city population.
- Customer date of birth.
- Customer and merchant coordinates.
- A sample-data button.
- A prediction result panel displaying fraud probability, classification, risk band, threshold, model version, model run ID, and request ID.

The browser sends JSON to `/predict` with the `X-API-Key` header and renders the API response.

The sample-data button fills the form. The actual prediction occurs only after the user clicks **Score transaction**.

### 6.2 Serving the page through FastAPI

The `GET /` route in `api/main.py` reads `api/static/index.html` and returns it as HTML.

This allows the page and API to be served by the same application.

### 6.3 Azure Cloud Shell Web Preview

Cloud Shell Web Preview exposes the service through a URL that contains a proxy path, for example:

```text
https://<relay-host>/<preview-id>/proxy/8000/
```

The actual relay hostname and preview ID are assigned by Azure and should not be hardcoded into the application.

Initially, the browser code used:

```javascript
fetch("/predict", {
```

The leading slash caused the request to resolve from the relay root instead of preserving the preview path. The browser consequently received an XML `404 Not Found` response.

The corrected code is:

```javascript
fetch(new URL("predict", window.location.href), {
```

This resolves `predict` relative to the current page URL and preserves the Cloud Shell preview path when the page URL ends in `/`.

After the change, the browser successfully reached the API and displayed the prediction.

**Important:** The browser address bar normally remains on the same page when a prediction is submitted. JavaScript sends the request in the background, so the absence of a page navigation is expected.

## 7. Using the API from other environments

The API URL depends on where the server is running and where the request originates.

`127.0.0.1` always refers to the local machine or environment in which the command is executed. It does not automatically refer to a different computer or remote environment.

### 7.1 Azure Cloud Shell

For `curl` commands executed inside the same Cloud Shell environment as Uvicorn:

```bash
curl http://127.0.0.1:8000/health
```

For browser access, open Azure Cloud Shell Web Preview on port 8000 and use the URL provided by Azure.

### 7.2 GitHub Codespaces

If the API is running inside the Codespace, `curl` from that same Codespace can use:

```bash
curl http://127.0.0.1:8000/health
```

For browser access, use the forwarded-port URL provided by Codespaces.

The model artifacts and dependencies must also be available inside the Codespace. Files downloaded into Cloud Shell are not automatically present in a separate Codespace.

### 7.3 Local VS Code terminal

If the API is running on the same desktop, a local terminal can use:

```bash
curl http://127.0.0.1:8000/health
```

Open the browser interface at:

```text
http://127.0.0.1:8000/
```

The local environment needs its own compatible dependencies and a copy of the model artifacts. A model file stored in Cloud Shell's `/tmp` directory is not automatically available on the desktop.

### 7.4 Should the HTML URL change for each environment?

Normally, no. The relative URL:

```javascript
new URL("predict", window.location.href)
```

allows the page to call the API through the same origin and directory path.

This works when the page and API are served together under the same routing prefix. If the API is moved to a different host or a reverse proxy uses a different path arrangement, the deployment must be configured accordingly.

For production deployments, an explicit, environment-specific API base URL or reverse-proxy configuration may be more appropriate.

### 7.5 Common startup issues

| Symptom | Likely cause | Action |
|---|---|---|
| Connection refused | API is not running or port is incorrect | Check the Uvicorn log and start the server |
| API key rejected | Missing key or key differs from the running server's key | Check the private shell environment and restart if necessary |
| Model files not found | Temporary files are missing or the model directory is incorrect | Check `MODEL_DIR` and download the artifacts again |
| Browser receives XML 404 | Request is reaching an incorrect relay path | Inspect the Network tab and preserve the preview path |
| Validation returns HTTP 422 | Request data is invalid | Check required fields, date order, and numeric ranges |
| Different fraud probabilities | Transaction inputs or model configuration differ | Compare all inputs, model run, and feature engineering |

## 8. Understanding and comparing predictions

The recorded direct backend smoke test returned:

| Field | Result |
|---|---|
| Fraud probability | Approximately 41.71% |
| Predicted fraud | `0` |
| Risk band | Medium |
| Model version | `xgboost-v1` |
| Model run ID | `20261012T024013Z` |
| Threshold | `0.50` |

A subsequent browser prediction displayed a fraud probability of 37.99%.

The model can return different probabilities for different transaction inputs, even when the same model version is used. The transaction timestamp affects derived features such as hour, day of week, month, and customer age. Other transaction values also affect the prediction.

To compare the browser and backend results accurately:

1. Use the same model run and model artifacts.
2. Submit identical raw values for all eight input fields.
3. Check that both requests use the same feature-engineering code and threshold.
4. Compare the returned probabilities and classifications.

Identical inputs and model configuration should produce matching scores apart from insignificant numerical differences.

A predicted non-fraud classification does not prove that a transaction is legitimate or safe. A fraud probability is a model estimate and should be interpreted in the context of the project's evaluation metrics and operational controls.

## 9. Testing and validation results

### 9.1 Automated tests

The full regression test suite was executed with:

```bash
python -m pytest tests -q
```

The latest recorded result was:

```text
43 passed, 1 warning
```

The warning is a Starlette deprecation warning related to the use of `httpx` with `starlette.testclient`. It did not cause the test run to fail, but it should be reviewed during dependency maintenance.

### 9.2 Diff validation

The following command completed without reporting whitespace errors:

```bash
git diff --check
```

### 9.3 Homepage validation

The homepage was checked directly from Cloud Shell:

```bash
curl -sS -o /dev/null \
  -w 'Homepage: HTTP %{http_code} | %{content_type}\n' \
  http://127.0.0.1:8000/
```

The observed result was:

```text
Homepage: HTTP 200 | text/html; charset=utf-8
```

### 9.4 Real-model smoke test

The direct `POST /predict` request returned HTTP 200 and valid JSON from the pinned model.

The browser interface was subsequently verified after correcting the preview URL.

### 9.5 Evidence

The browser prediction screenshot is named:

```text
web-page-fraud-prediction.PNG
```

If included in the repository, store it in a dedicated location such as `docs/evidence/` and reference it from the main project README or this document.

Before committing the screenshot, confirm that it does not expose the API key, credentials, or other secrets.

## 10. Security and operational considerations

- Do not commit API keys, credentials, or other secrets.
- Do not include API keys in documentation, source code, or screenshots.
- The current browser interface is a controlled demonstration, not a production authentication design.
- A public deployment requires appropriate authentication, transport security, rate limiting, secret management, and operational monitoring.
- The API currently uses local model artifacts for the demonstrated scoring path.
- Temporary files under `/tmp` should not be treated as durable model storage.
- The health endpoint is public in the current implementation.
- Model probabilities should not be presented as definitive evidence of fraud or transaction safety.

## 11. Follow-up implementation plan

The following work remains outside the validated scope described above.

### 11.1 ADLS-backed model loading

Validate that the API can retrieve the pinned model artifacts directly from ADLS using the intended Azure authentication and authorization configuration.

### 11.2 Prediction parity validation

Replay a small sample of Silver transactions through the API and compare its predictions with the corresponding existing Gold results.

The comparison should confirm:

- Model run and version.
- Feature names and order.
- Feature-engineering logic.
- Decision threshold.
- Probability and classification consistency.

### 11.3 Operational validation

Review startup failures, missing model artifacts, authentication failures, invalid input responses, and logging behaviour.

Document the intended recovery procedure and deployment configuration before moving to a more production-like environment.

## 12. Summary

The transaction risk scoring API is implemented and has passed its recorded regression tests. The service loads the pinned XGBoost model, validates transaction input, protects scoring endpoints with an API key, and returns prediction results through JSON.

A browser interface was added and successfully connected to the API. The Azure Cloud Shell preview issue was traced to an incorrectly resolved request URL and fixed by resolving the prediction endpoint relative to the current page.

The next major validation step is to verify ADLS-backed model loading and compare API predictions with existing Gold results. This will establish consistency between the existing analytics pipeline and the online scoring service.
