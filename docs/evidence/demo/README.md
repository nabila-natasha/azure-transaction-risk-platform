# API Demonstration Evidence

These screenshots document the transaction-risk API demonstration across local VS Code and Azure Cloud Shell environments, the interactive API documentation, prediction validation, and Azure DevOps pipeline execution.

## Screenshot Index

| File | Purpose |
|---|---|
| `01-api-health.PNG` | Demonstrates that the API health endpoint responds successfully. |
| `02-web-app-prediction.PNG` | Shows the project's web interface for submitting a transaction. |
| `03-api-prediction-response.PNG` | Shows the API prediction response, including fraud probability, predicted class, risk band, and model metadata. |
| `04-parity-summary.PNG` | Records the 1,000-transaction prediction parity validation summary. |
| `05-azure-devops-pipeline.PNG` | Shows the successful Azure DevOps pipeline run. |
| `06-api-docs.PNG` | Shows the FastAPI Swagger UI documentation page rendered through Azure Cloud Shell Web Preview. |
| `07-local-api-docs.PNG` | Shows the FastAPI interactive documentation page served by the API running locally. |
| `08-local-api-prediction.PNG` | Shows a successful local prediction request and its response from the saved model. |
| `09-local-api-model-info.png` | Shows the local API model metadata, including the model version and run ID. |
| `10-local-api-server.PNG` | Shows the local VS Code terminal running the API server. |

## Validation Highlights

- The API was started and tested in local VS Code and Azure Cloud Shell environments.
- The API health endpoint, model-information endpoint, and prediction endpoint were tested during the demonstrations.
- The local API was demonstrated through its interactive `/docs` interface using the saved baseline model.
- The Swagger UI documentation page was successfully opened through Cloud Shell Web Preview after correcting the OpenAPI document URL to work with the preview proxy path.
- A 1,000-transaction replay was performed for prediction parity validation.
- All six parity checks passed for all sampled transactions.
- Zero API request errors and zero mismatch records were reported in the recorded replay.
- The automated test suite reported 43 passing tests in the recorded test run.
- The Docker GitHub Actions workflow subsequently validated containerized inference using the actual saved XGBoost model and the private model artifacts.

The screenshots support the engineering documentation and recorded test results. They do not replace the detailed methodology, results, and limitations documented in `docs/engineering/api-prediction-parity-validation.md`.

## Interpretation and Limitations

The API demonstration uses a saved model artifact and synthetic request data. The parity validation compares API predictions against existing Gold predictions. Neither activity, on its own, proves real-world fraud-detection accuracy.

Running the API locally or in Cloud Shell demonstrates that the service can run in those interactive environments. It does not constitute a persistent production deployment, production-scale performance testing, or a full security assessment.

The successful Docker workflow provides separate evidence that the actual saved model can be loaded and used for inference inside a container. It does not mean the API is publicly deployed or continuously available.

For environment setup, startup commands, and Cloud Shell Web Preview troubleshooting notes, see `docs/engineering/api-local-and-cloud-shell-runbook.md`.

For model storage, checksum verification, model versioning, and rollback, see `docs/engineering/model-lifecycle-and-versioning.md`.
