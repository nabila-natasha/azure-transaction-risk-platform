# API Demonstration Evidence

These screenshots document the local transaction-risk API demonstration
and the associated validation results.

| File | Purpose |
|---|---|
| `01-api-health.PNG` | Demonstrates that the API health endpoint responds successfully. |
| `02-web-app-prediction.PNG` | Shows the project's web interface for submitting a transaction. |
| `03-api-prediction-response.PNG` | Shows the API prediction response and returned model metadata. |
| `04-parity-summary.PNG` | Records the 1,000-transaction parity validation summary. |
| `05-azure-devops-pipeline.PNG` | Shows the successful Azure DevOps pipeline run. |

## Validation highlights

- 1,000 transactions replayed through the local API.
- All six parity checks passed for all sampled transactions.
- Zero API request errors and zero mismatch records.
- 43 automated tests passed in the recorded test run.

The screenshots are supporting evidence, not a substitute for the detailed
methodology and limitations documented in
`docs/engineering/api-prediction-parity-validation.md`.

The demonstration uses a local API and synthetic request data. It does not
claim production deployment, production-scale performance, or real-world
fraud-detection accuracy.
