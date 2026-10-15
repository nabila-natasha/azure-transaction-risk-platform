# API Local Development and Azure Cloud Shell Runbook

## 1. Purpose

This document explains how to start and test the project's FastAPI transaction-risk scoring service in two interactive development environments:

1. Local VS Code terminal on Windows.
2. Azure Cloud Shell.

It also records the cause and resolution of the Swagger UI `/docs` issue encountered through Azure Cloud Shell Web Preview.

The objective is reproducibility and troubleshooting. The commands and screenshots demonstrate API execution in development environments; they do not establish a persistent production deployment.

## 2. API Architecture and Runtime Behaviour

The API exposes these main endpoints:

| Endpoint | Method | Purpose | Authentication |
|---|---|---|---|
| `/` | GET | Serves the project's web interface. | No API key |
| `/health` | GET | Returns a basic service-health response. | No API key |
| `/model-info` | GET | Returns model metadata. | `X-API-Key` |
| `/predict` | POST | Accepts raw transaction fields and returns a risk prediction. | `X-API-Key` |
| `/docs` | GET | Displays interactive Swagger UI documentation. | No API key |
| `/openapi.json` | GET | Returns the API's OpenAPI specification. | No API key |

The exact authentication behaviour should be kept consistent with the implementation and its tests.

The application is created through the factory `api.main:create_app`. Uvicorn starts that factory and hosts the resulting FastAPI application.

### Model configuration

The API uses environment variables to determine its runtime configuration.

| Variable | Purpose |
|---|---|
| `API_KEY` | Key used by protected API endpoints. |
| `MODEL_SOURCE` | Selects the configured model source, such as `local`. |
| `MODEL_DIR` | Directory containing the local model artifacts. |
| `MODEL_RUN_ID` | Expected model run identifier used for model metadata and traceability. |

For the documented local-model demonstration, the expected model version is `xgboost-v1` and the model run ID is `20261012T024013Z`.

The local model directory must contain the required artifacts, including `manifest.json` and `model.json`. Use the directory that actually contains those files; do not assume the same absolute path exists on every machine.

Environment variables are process-specific. Set them in the same terminal session that starts Uvicorn. Do not commit real API keys or other secrets to the repository.

## 3. Running the API Locally in VS Code on Windows

### 3.1 Prerequisites

- The repository has been cloned or otherwise made available locally.
- The local Python virtual environment exists.
- The API dependencies are installed.
- The saved model artifacts are available.
- The terminal is opened at the repository root.

The demonstrated Windows environment used `.venv-local-api` and the project's `requirements-api.txt`. The virtual environment avoids relying on globally installed Python packages.

### 3.2 Start the API

In a VS Code PowerShell terminal, change to the repository root if necessary:

```powershell
cd "C:\Users\nabila\Desktop\Nabila\mine\azure-transaction-risk-platform"
```

Set the runtime variables:

```powershell
$env:API_KEY = "replace-with-a-local-test-key"
$env:MODEL_SOURCE = "local"
$env:MODEL_DIR = "$PWD\model-backup-20261012T024013Z"
$env:MODEL_RUN_ID = "20261012T024013Z"
```

The `MODEL_DIR` example assumes the backup directory is under the repository root. If the directory is elsewhere, set it to the actual location.

Start the API using the virtual environment's Python executable:

```powershell
.\.venv-local-api\Scripts\python.exe -m uvicorn `
  --factory api.main:create_app `
  --host 127.0.0.1 `
  --port 8000
```

Using the executable directly avoids requiring PowerShell activation of the virtual environment. This is useful when the machine's execution policy prevents running the environment's activation script.

Keep this terminal open while testing the API.

### 3.3 Test the API

Open a browser on the same computer and visit:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

The health endpoint should return:

```json
{"status":"ok"}
```

For protected endpoints, send the API key in the `X-API-Key` request header. For example, in PowerShell:

```powershell
$headers = @{ "X-API-Key" = "replace-with-a-local-test-key" }

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/model-info" `
  -Headers $headers `
  -Method Get
```

Use the same key that was set in the terminal running Uvicorn.

For `/predict`, submit a request conforming to the API's `Transaction` schema. The API derives its model features server-side and returns a prediction and model metadata.

### 3.4 Important distinction

`127.0.0.1` is the loopback address of the computer on which the API is running. A browser on another computer cannot use that address to reach this local service.

This local run demonstrates development and inference behaviour. It is not an externally accessible deployment.

## 4. Running the API in Azure Cloud Shell

### 4.1 Prerequisites

- The repository is available in the Cloud Shell home directory.
- The Python environment contains the API's dependencies.
- The saved model artifact is available in the Cloud Shell environment.
- The model directory contains the required files.
- The runtime variables are set in the terminal that starts Uvicorn.

Cloud Shell environments and files should not be assumed to persist indefinitely. A terminated or recreated session may require environment recreation or restoration of the model artifacts.

### 4.2 Verify the repository and model files

From the repository root:

```bash
cd ~/azure-transaction-risk-platform
pwd
ls -la
```

Set the model directory to the directory containing the extracted artifacts. For example, if the files are in the home directory's model backup folder:

```bash
export MODEL_DIR="$HOME/model-backup-20261012T024013Z"
```

Verify the required files:

```bash
test -f "$MODEL_DIR/manifest.json" && echo "Manifest found"
test -f "$MODEL_DIR/model.json" && echo "Model file found"
```

If either file is missing, do not change the model loader merely to bypass the error. Locate or restore the expected artifacts first.

If the ZIP backup is available but the extracted directory is missing, inspect the archive:

```bash
unzip -l "$HOME/model-backup-20261012T024013Z.zip"
```

Extract it into a separate restoration directory, then locate the manifest:

```bash
mkdir -p "$HOME/model-backup-restore-20261012T024013Z"

unzip -o \
  "$HOME/model-backup-20261012T024013Z.zip" \
  -d "$HOME/model-backup-restore-20261012T024013Z"

find "$HOME/model-backup-restore-20261012T024013Z" \
  -type f -name "manifest.json" -print
```

Set `MODEL_DIR` to the directory that contains both `manifest.json` and `model.json`. Confirm both files are present before starting the API.

### 4.3 Set runtime variables and start Uvicorn

Activate the existing environment if its activation script is available. The demonstrated Cloud Shell environment used a Python executable at `/tmp/transaction-risk-api-venv/bin/python`.

```bash
export API_KEY="replace-with-a-local-test-key"
export MODEL_SOURCE="local"
export MODEL_RUN_ID="20261012T024013Z"
```

Set `MODEL_DIR` to the verified artifact directory, then start the service:

```bash
/tmp/transaction-risk-api-venv/bin/python -m uvicorn \
  --factory api.main:create_app \
  --host 0.0.0.0 \
  --port 8000
```

The `0.0.0.0` bind address allows the service to listen on available network interfaces in the Cloud Shell environment. It is not the address to type into the laptop's browser.

Keep this terminal open. If startup fails, read the full traceback before changing code. A missing model artifact, missing API key, or missing dependency is different from a Web Preview routing problem.

### 4.4 Test the service from another Cloud Shell terminal

Open a second terminal and run:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/docs
curl -i http://127.0.0.1:8000/openapi.json
```

Expected results:

- `/health` returns HTTP `200 OK` and `{"status":"ok"}`.
- `/docs` returns HTTP `200 OK` and Swagger UI HTML.
- `/openapi.json` returns HTTP `200 OK` and a JSON document whose `openapi` field is `3.1.0`.

These checks test the service inside Cloud Shell. They do not, by themselves, prove that the browser-facing Web Preview proxy works correctly.

## 5. Accessing the API Through Cloud Shell Web Preview

Use Cloud Shell's Web Preview feature to preview port `8000`. Open the preview URL generated by Cloud Shell and append the relevant path, such as `/docs`.

Do not manually construct a proxy host or assume the preview URL will remain the same between sessions.

The preview URL contains an additional path prefix for the proxy. For example, it may have a structure like:

```text
https://<preview-host>/<session-or-proxy-prefix>/proxy/8000/
```

The actual host and prefix are generated by the environment.

### 5.1 Distinguishing a server issue from a preview issue

If `/docs` fails in the browser, first test these endpoints through the generated preview URL:

- `/health`
- `/openapi.json`
- `/docs`

Interpret the results as follows:

| Observation | Likely area to investigate |
|---|---|
| Uvicorn fails during startup | Configuration, dependency, API key, or model-loading problem |
| Local Cloud Shell `curl` fails | Service startup, route, or application problem |
| Preview `/health` fails | Preview configuration, proxy routing, or service reachability |
| Preview `/openapi.json` returns the correct OpenAPI JSON but `/docs` fails | Swagger UI's OpenAPI URL resolution or browser-side loading |
| Preview `/docs` works and lists the endpoints | Documentation UI and specification loading are working |

A `200 OK` response from `/docs` proves that HTML was returned. It does not prove that Swagger UI successfully fetched the OpenAPI document and rendered its endpoints.

## 6. Troubleshooting Record: Why `/docs` Failed in Cloud Shell

### 6.1 Symptoms

During the Cloud Shell demonstration, the API was able to return:

- `200 OK` from `/health`.
- `200 OK` from `/docs`.
- `200 OK` from `/openapi.json`.

The OpenAPI response included:

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Transaction Risk Scoring API",
    "version": "1.0.0"
  }
}
```

However, the browser displayed a Swagger UI error stating that the provided definition did not specify a valid version field.

### 6.2 Root cause

FastAPI's default Swagger UI HTML referenced the OpenAPI document with an absolute path:

```javascript
url: '/openapi.json'
```

A path beginning with `/` is resolved from the root of the current host. It does not automatically preserve an additional path prefix used by a reverse proxy.

The Cloud Shell Web Preview URL includes a proxy path before the API routes. Consequently, Swagger UI could request `/openapi.json` at the wrong browser path, rather than requesting the API's OpenAPI document under the preview prefix.

This explains why the raw JSON could be correct when opened directly through the preview URL while Swagger UI still reported an invalid definition: the UI and the direct JSON request were not necessarily requesting the same URL.

The issue was not evidence of an invalid OpenAPI version. The returned `3.1.0` version was valid. It was also not evidence that the XGBoost model or `src/model_store.py` needed to be changed.

### 6.3 Fix applied

The default FastAPI `/docs` route was disabled and replaced with a custom documentation route using `get_swagger_ui_html`.

The FastAPI initialization became:

```python
app = FastAPI(
    title="Transaction Risk Scoring API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
)
```

The following import was added:

```python
from fastapi.openapi.docs import get_swagger_ui_html
```

The custom route was added after the app was created:

```python
@app.get("/docs", include_in_schema=False)
def custom_docs():
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title="Transaction Risk Scoring API - Swagger UI",
    )
```

The key difference is:

- **Before:** `url: '/openapi.json'` — an absolute path from the host root.
- **After:** `openapi_url="openapi.json"` — a relative path resolved from the documentation page's URL, preserving the Cloud Shell preview prefix in this environment.

Disabling the default documentation route prevents a duplicate `/docs` route from being registered. The custom route replaces it; the API's OpenAPI specification endpoint remains enabled.

### 6.4 Why the fix works: an analogy

Imagine that Cloud Shell Web Preview is a building with a special entrance. The API's real `/openapi.json` is a room inside that entrance.

The original absolute URL tells Swagger UI, "Go to the building's main entrance and look for `/openapi.json`." But the API is reachable through the special preview entrance, so that route may lead somewhere else.

The relative URL tells Swagger UI, "From the documentation page you're viewing, find `openapi.json` alongside it." This retains the preview path and directs the request to the API document served through the same proxy.

The JSON document itself did not need to change. We corrected how Swagger UI locates it.

### 6.5 Verification after the fix

After restarting Uvicorn, the Cloud Shell preview successfully rendered the Swagger UI page and displayed the API endpoints.

This fix was verified in the Cloud Shell Web Preview environment. Local VS Code continued to serve the API using its local address.

The solution addresses the demonstrated proxy-path problem. If a different deployment uses a different proxy prefix or a configured FastAPI `root_path`, verify the generated URL in that environment rather than assuming every proxy behaves identically.

## 7. Local VS Code Versus Azure Cloud Shell

| Aspect | Local VS Code | Azure Cloud Shell |
|---|---|---|
| Where Python runs | On the local computer | In the Cloud Shell environment |
| Example address | `http://127.0.0.1:8000` | Cloud Shell Web Preview URL |
| How the browser reaches the API | Direct loopback connection on the same computer | Through the Cloud Shell preview proxy |
| Model files | Local filesystem | Cloud Shell filesystem or restored artifacts |
| Environment lifetime | Depends on the local machine and process | Interactive session and filesystem availability may change |
| Primary use in this project | Local development, debugging, and repeatable API checks | Demonstration of API execution in Cloud Shell and verification of preview routing |
| Production deployment? | No | No |

Both environments can run the same application code, but they do not necessarily have the same filesystem, Python environment, network path, or session lifetime.

Successful execution in both environments provides useful portability evidence. It does not establish production hosting, high availability, or production performance.

## 8. Operational and Security Notes

- Do not commit API keys, credentials, access tokens, or other secrets.
- Use synthetic request data for public portfolio screenshots.
- Do not expose sensitive request or response fields in evidence.
- Keep the API key in the `X-API-Key` header for protected endpoints.
- Stop the Uvicorn process when the demonstration is complete.
- Avoid creating additional Azure resources or enabling paid services solely to obtain a screenshot.
- A successful health check is not a substitute for model validation, API security testing, or operational monitoring.
- A successful `/docs` page demonstrates API discoverability, not authorization enforcement or model accuracy.

## 9. Related Documentation and Evidence

- Prediction parity methodology, results, and limitations: `docs/engineering/api-prediction-parity-validation.md`
- API demonstration screenshots: `docs/evidence/demo/`
- Parity summary and row-level results: `docs/evidence/parity/`
- API implementation: `api/main.py`
- Model loading and configuration: `src/model_store.py`

## 10. Summary

The transaction-risk FastAPI service was successfully run in both local VS Code and Azure Cloud Shell. The Cloud Shell API returned valid health, documentation HTML, and OpenAPI JSON responses. Swagger UI initially failed to render because its absolute OpenAPI URL did not account for the Cloud Shell preview proxy prefix.

Replacing the default `/docs` route with a custom route that uses the relative OpenAPI URL `openapi.json` resolved the issue in the tested environment. The model-loading code did not need to be changed for this problem.

These results document successful interactive API execution and a practical reverse-proxy troubleshooting lesson. They should not be described as evidence of a persistent production deployment.
