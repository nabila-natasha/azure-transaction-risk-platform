# API Demonstration Evidence

These screenshots document the transaction-risk API demonstration, API documentation interface, automated validation results, and Azure DevOps pipeline evidence.

| File | Purpose |
|---|---|
| `01-api-health.PNG` | Demonstrates that the API health endpoint responds successfully. |
| `02-web-app-prediction.PNG` | Shows the project's web interface for submitting a transaction. |
| `03-api-prediction-response.PNG` | Shows the API prediction response, including fraud probability, predicted class, risk band, and model metadata. |
| `04-parity-summary.PNG` | Records the 1,000-transaction prediction parity validation summary. |
| `05-azure-devops-pipeline.PNG` | Shows the successful Azure DevOps pipeline run. |
| `06-api-docs.PNG` | Shows the FastAPI Swagger UI documentation page successfully rendered through Azure Cloud Shell Web Preview. |

## Validation highlights

- The API was started and tested in both local VS Code and Azure Cloud Shell environments.
- The API health endpoint, model-information endpoint, and prediction endpoint were tested during the demonstration.
- The Swagger UI documentation page was successfully opened through Cloud Shell Web Preview after correcting the OpenAPI document URL to work with the preview proxy path.
- 1,000 transactions were replayed through the API for prediction parity validation.
- All six parity checks passed for all sampled transactions.
- Zero API request errors and zero mismatch records were reported in the recorded replay.
- The automated test suite reported 43 passing tests in the recorded test run.

The screenshots support the engineering documentation and recorded test results. They do not replace the detailed methodology, results, and limitations documented in `docs/engineering/api-prediction-parity-validation.md`.

The demonstration uses a saved model artifact and synthetic request data for the API walkthrough. The parity validation compares API predictions against existing Gold predictions. Neither activity, on its own, proves real-world fraud-detection accuracy.

Running the API in Cloud Shell demonstrates that the service can run in that interactive environment. It does not constitute a persistent production deployment, production-scale performance testing, or a full security assessment.

For environment setup, startup commands, and the Cloud Shell Web Preview troubleshooting notes, see `docs/engineering/api-local-and-cloud-shell-runbook.md`.
