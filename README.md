# Azure Transaction Risk Platform

An end-to-end Azure data engineering and machine learning platform for processing financial transaction data, applying data-quality controls, engineering risk-related features, and preparing data for machine learning.

The project demonstrates a production-oriented Azure architecture using Infrastructure as Code, event-driven ingestion, data lake processing, automated testing, Terraform CI/CD, production approval, deployment validation, and rollback procedures.

> **Portfolio note:** This project uses synthetic/public-style transaction data and does not use real customer financial information.

---

## 1. Project Overview

Financial transaction datasets can contain valid records alongside duplicates, missing values, inconsistent fields, and potentially anomalous transaction behaviour.

This project demonstrates how transaction data can move through a controlled cloud data engineering and ML workflow:

```text
Source Transaction Data
        |
        v
Azure Ingestion
        |
        v
Bronze Layer
        |
        v
Data Quality Checks
        |
   +----+----+
   |         |
 Valid     Invalid
   |         |
   v         v
Silver   Quarantine
   |
   v
Feature Engineering
   |
   v
ML Dataset
   |
   v
Machine Learning
   |
   v
Validation / Model Smoke Tests
```

The project focuses on the engineering lifecycle around a transaction-risk workload rather than claiming production fraud-detection performance.

---

## 2. Objectives

The project demonstrates the following data engineering, cloud engineering, ML engineering, and DevOps capabilities:

* Azure data lake architecture
* Infrastructure as Code with Terraform
* Event-driven ingestion using Azure Event Hubs
* Bronze and Silver data layers
* Data-quality validation and quarantine
* Deterministic transaction/event identifiers
* Feature engineering for ML
* Reproducible ML dataset preparation
* Automated Python testing with pytest
* Azure DevOps CI/CD
* Terraform plan and apply workflows
* Production environment approval
* Terraform plan artifact promotion
* Deployment smoke validation
* Rollback procedures
* Git-based development workflow
* Azure service connection-based authentication
* Separation of testing from production infrastructure changes

---

## 3. Technology Stack

| Area                    | Technology                                                |
| ----------------------- | --------------------------------------------------------- |
| Cloud                   | Microsoft Azure                                           |
| Infrastructure as Code  | Terraform                                                 |
| Storage                 | Azure Data Lake Storage / Azure Storage                   |
| Streaming / Ingestion   | Azure Event Hubs                                          |
| Data Processing         | Python, Pandas, PyArrow                                   |
| Machine Learning        | Python / scikit-learn workflow                            |
| Testing                 | pytest                                                    |
| CI/CD                   | Azure DevOps Pipelines                                    |
| Source Control          | Git / GitHub                                              |
| Authentication          | Azure DevOps service connection / Azure identity          |
| Environment Approval    | Azure DevOps Environment                                  |
| Data Format             | Parquet                                                   |
| Development Environment | Azure Cloud Shell                                         |
| API Framework           | FastAPI                                                   |
| API Server              | Uvicorn                                                   |
| Model Serving           | Saved XGBoost model and versioned model artifacts         |
| Model Artifact Storage  | Azure Data Lake Storage / configurable local model bundle |
| API Documentation       | OpenAPI / Swagger UI                                      |
| Browser Interface       | HTML / JavaScript web application                         |
| API Testing             | pytest, FastAPI TestClient, and prediction contract tests |

---

## 4. Architecture

The platform separates infrastructure provisioning, ingestion, data processing, ML preparation, testing, and deployment automation.

### Logical Architecture

```text
                         GitHub
                           |
                           v
                  Azure DevOps CI/CD
                     /           \
                    /             \
             Terraform          Python Tests
                 |                  |
                 v                  v
          Azure Resources      Code Validation
                 |
        +--------+---------+
        |                  |
        v                  v
 Azure Event Hubs      Azure Storage
        |                  |
        |                  v
        |               Bronze
        |                  |
        |                  v
        +-------------> Silver
                           |
                           v
                    Feature Engineering
                           |
                           v
                       ML Dataset
                           |
                           v
                    ML Validation
```

### ML Scoring and API Architecture

```text
Silver Transaction Data
          |
          v
   Feature Engineering
          |
          v
  Saved Model Artifacts
  + Model Manifest
          |
          v
   FastAPI Scoring API
          |
     +----+----+
     |         |
     v         v
  Web App   API Clients
     |         |
     +----+----+
          |
          v
  Prediction Response
  - Fraud Probability
  - Predicted Class
  - Risk Band
  - Model Version
  - Model Run ID
```

The API loads a saved model bundle rather than retraining the model for each request. 
It derives the required features from the submitted transaction, applies the configured
scoring threshold, and returns a structured prediction response.

The browser interface provides a user-friendly way to submit a transaction to the API 
and inspect its prediction.

### Deployment Architecture

```text
GitHub
  |
  v
Azure DevOps CI
  |
  +--> Python Tests
  |
  +--> Terraform Validate
  |
  +--> Terraform Plan
           |
           v
     Plan Artifact
           |
           v
Azure DevOps CD
           |
           v
Production Approval
           |
           v
Terraform Apply
           |
           v
Smoke Validation
```

---

## 5. Data Lake Layers

### Bronze

The Bronze layer preserves ingested transaction data in a structured lake format.

Its purpose is to provide a landing layer before business-quality transformations are applied.

Typical responsibilities include:

* Preserving incoming records
* Maintaining ingestion metadata
* Supporting replay and debugging
* Providing an auditable input to downstream processing

### Silver

The Silver layer contains validated and cleaned transaction records.

Processing includes:

* Schema validation
* Required-field validation
* Duplicate detection
* Type normalization
* Data-quality rules
* Separation of invalid records into quarantine

The Silver layer is the primary trusted dataset used for downstream feature engineering.

### Quarantine

Records that fail validation are separated rather than silently discarded.

This allows invalid data to be investigated without contaminating the trusted Silver dataset.

---

## 6. Data Quality

The platform treats data quality as part of the data pipeline rather than as an afterthought.

Examples of implemented controls include:

* Required-field validation
* Data-type validation
* Duplicate detection
* Validity checks for transaction fields
* Separation of invalid records
* Validation of expected ML feature columns

A deterministic transaction/event identifier is used where appropriate to support repeatable duplicate detection.

The resulting processing model is:

```text
Raw / Bronze Data
       |
       v
  Validation
       |
   +---+---+
   |       |
 Valid   Invalid
   |       |
   v       v
Silver  Quarantine
```

---

## 7. Feature Engineering

The ML dataset uses a controlled feature contract.

The expected feature set is:

```text
amt
city_pop
lat
long
merch_lat
merch_long
transaction_hour
day_of_week
month
customer_age
distance_km
```

Feature engineering combines original transaction attributes with derived temporal and geospatial features.

Examples include:

* Transaction hour
* Day of week
* Month
* Customer age
* Geographic transaction distance

The feature contract is explicitly tested so that changes to the upstream data structure do not silently change the ML input.

---

## 8. Machine Learning

For the detailed rationale behind model versioning, the four ADLS artifacts, scoring-script changes, contract tests, dry-run validation, 
and read-only Gold parity checks, see [Model Versioning and Scoring Engineering Notes](docs/engineering/model-versioning-and-scoring.md).

The project prepares a Silver-derived dataset for machine learning.

The ML workflow separates:

1. Data preparation
2. Feature engineering
3. Feature-contract validation
4. Model-input validation
5. Model smoke testing

The objective is to demonstrate the engineering lifecycle surrounding an ML workload rather than claim 
production fraud-detection performance.

Model results should therefore be interpreted as portfolio and engineering validation rather than 
as a production financial-risk model.

### Model Artifacts and Versioning

The project separates model training and validation from online scoring. A saved model bundle 
and its manifest allow the scoring API to load a specific model run without retraining during an API request.

The model metadata identifies the model version, model run, expected features, and scoring configuration. 
This supports reproducibility and traceability when investigating individual predictions.

The API uses the existing XGBoost scoring implementation and configured threshold. It does not require 
changes to the existing Gold dataset to serve predictions.

### API and Browser-Based Scoring

The FastAPI application exposes:

| Endpoint | Purpose |
|---|---|
| `/health` | Basic API health check |
| `/model-info` | Returns model metadata; requires an API key |
| `/predict` | Validates and scores a transaction; requires an API key |
| `/docs` | Interactive Swagger UI documentation |
| `/openapi.json` | OpenAPI specification |

The prediction response includes the fraud probability, predicted class, risk band, model version, 
model run ID, threshold, and request ID.

A browser-based web application provides an interface for submitting transactions to the scoring API. 
Input validation, API authentication, structured error responses, and request logging support a more controlled scoring workflow.

The Swagger UI is configured to use a relative OpenAPI URL so that the documentation also renders correctly 
through Azure Cloud Shell Web Preview.

**Deployment scope:** The API and web interface have been exercised in local development and Azure Cloud Shell. 
This demonstrates the scoring workflow but does not represent a continuously running production API deployment.

---

## 9. Automated Testing

The repository contains automated tests covering:

* Feature engineering
* ML feature contract
* Data quality
* Model smoke validation

The latest recorded automated test run completed with:

```text
43 passed, 1 warning
```

The suite covers data quality, feature engineering, ML feature contracts, model scoring,
API request validation, prediction response contracts, and related scoring behaviour.

The warning concerns a Starlette deprecation notice involving `httpx` and `starlette.testclient`; 
it did not cause test failures.

The API was also checked through its health endpoint, model-information endpoint, 
prediction endpoint, and interactive documentation during development.

Python syntax validation is also performed using:

```bash
python -m compileall scripts
```

The CI pipeline executes the automated test suite before Terraform planning.

### Test Flow

```text
Python Source
     |
     v
Syntax Validation
     |
     v
   pytest
     |
     +--> Data Quality Tests
     |
     +--> Feature Engineering Tests
     |
     +--> ML Contract Tests
     |
     +--> Model Smoke Tests
```

---

## 10. Infrastructure as Code

Azure infrastructure is managed using Terraform.

The Terraform workflow is:

```text
terraform init
        |
        v
terraform validate
        |
        v
terraform plan
        |
        v
Plan Artifact
        |
        v
Production Approval
        |
        v
terraform apply
```

The Terraform plan is published as a pipeline artifact.

The CD deployment downloads and applies the previously generated plan artifact rather than generating a different plan during deployment.

This helps maintain consistency between the infrastructure change that was reviewed and the infrastructure change that is ultimately applied.

---

## 11. Azure DevOps CI

The CI pipeline validates the project before infrastructure deployment.

The pipeline performs:

1. Repository checkout
2. Build environment validation
3. Python dependency installation
4. Python syntax validation
5. pytest execution
6. Azure authentication
7. Terraform initialization
8. Terraform validation
9. Terraform plan

The CI pipeline was validated by pushing directly to `main`.

A terminal `git push origin main` automatically triggered Azure DevOps CI, and the resulting pipeline completed successfully.

The verified execution path was:

```text
git push origin main
        |
        v
      GitHub
        |
        v
Azure DevOps CI
        |
        v
Default Agent Pool
        |
        v
 bello-cloudshell
        |
        v
Python Tests + Terraform Plan
        |
        v
  CI Successful
```

Azure DevOps run:

```text
#20261001.11
```

completed successfully.

The CD pipeline remains a separate controlled release workflow and is not automatically triggered by CI.

---

## 12. Azure DevOps CD

The CD pipeline is intentionally separated from CI.

The deployment workflow is:

```text
Terraform Plan
      |
      v
Publish tfplan Artifact
      |
      v
Production Apply Stage
      |
      v
terraform-production Approval
      |
      v
Terraform Apply
      |
      v
Post-deployment Smoke Validation
```

The production environment provides an explicit approval point before Terraform changes are applied.

This creates a separation between:

```text
Build / Test
```

and:

```text
Production Infrastructure Change
```

---

## 13. Deployment Smoke Validation

After Terraform Apply, the CD pipeline validates the deployment.

The smoke validation checks:

* Azure subscription context
* Resource group existence
* Resource provisioning state
* Deployed Azure resources

The production resource group used by this project is:

```text
rg-transaction-risk-platform
```

The smoke validation was successfully executed during the final CD run.

---

## 14. CI/CD Security

Secrets are not committed to the repository.

The Terraform pipeline receives the Synapse SQL administrator password through the Azure DevOps pipeline variable:

```text
SYNAPSE_SQL_ADMIN_PASSWORD
```

Terraform receives this value through:

```text
TF_VAR_synapse_sql_admin_password
```

Azure authentication is handled through the Azure DevOps service connection:

```text
sc-transaction-risk-platform
```

This avoids embedding Azure credentials directly in Terraform or pipeline source code.

### Security Flow

```text
Azure DevOps
     |
     +--> Service Connection
     |         |
     |         v
     |    Azure Authentication
     |
     +--> Secure Pipeline Variable
               |
               v
       TF_VAR_* Environment Variable
               |
               v
            Terraform
```

---

## 15. Production Approval

The CD deployment uses the Azure DevOps environment:

```text
terraform-production
```

The environment acts as a controlled approval gate before Terraform Apply.

This separates:

```text
Build / Test
```

from:

```text
Production Infrastructure Change
```

and demonstrates a controlled deployment workflow rather than automatically applying every Terraform change.

---

## 16. Rollback

Rollback procedures are documented in:

```text
docs/rollback.md
```

The rollback approach is:

```text
Identify Deployment Issue
        |
        v
Revert Problematic Git Change
        |
        v
Run CI Validation
        |
        v
Generate Terraform Plan
        |
        v
Production Approval
        |
        v
Apply Corrected State
        |
        v
Smoke Validation
```

The project intentionally uses a controlled rollback procedure rather than claiming that infrastructure rollback is automatically performed.

---

## 17. Day 11 Production Readiness

Day 11 focused on turning the earlier engineering work into a controlled deployment workflow.

### Completed Day 11 Work

* Added automated Python test execution
* Added ML validation tests
* Added feature-contract tests
* Added data-quality tests
* Added model smoke tests
* Added a real Silver-derived test fixture
* Added pytest configuration
* Added CI test execution
* Added deployment smoke validation
* Added Terraform plan artifact promotion
* Added production environment approval
* Added rollback documentation
* Merged production-readiness work into `main`
* Executed CI successfully on `main`
* Executed CD successfully on `main`
* Verified final Git state

---

## 18. Final Validation

The final repository state was validated on the `main` branch.

The authoritative remote branch is:

```text
origin/main
```

Final Git validation is performed with:

```bash
git status
```

Expected clean state:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

The final CI pipeline was validated by pushing directly to `main`.

The final CD pipeline was separately executed against `main` and completed successfully, including:

* Terraform Plan
* Terraform Plan Artifact
* Production Approval
* Terraform Apply
* Post-Deployment Smoke Validation

---

## 19. GitHub Push Trigger Validation

The GitHub-to-Azure DevOps CI integration was validated by pushing directly from the terminal:

```bash
git push origin main
```

```text
The verified execution path is:

GitHub Push
      |
      v
Azure DevOps CI
      |
      v
Default Agent Pool
      |
      v
bello-cloudshell
      |
      v
CI Execution
      |
      v
CI Successful
```

Azure DevOps run:

```text
#20261001.11
```

was created from the repository push and completed successfully.

This confirms that a push to `main` automatically triggers the CI pipeline.

The CD pipeline remains intentionally separate from the CI trigger. A successful CI run does not automatically execute Terraform Apply. CD is manually initiated as a controlled release workflow and uses the `terraform-production` approval environment before infrastructure changes are applied.

---

## 20. Repository Structure

A simplified repository structure is:

```text
azure-transaction-risk-platform/
│
├── .github/
│   ├── workflows/
│   │   ├── docker-build.yml
|
├── api/
│   ├── main.py
│   └── static/
│       └── index.html
├── .gitignore
├── README.md
├── azure-pipelines-ci.yml
├── azure-pipelines-cd.yml
├── pytest.ini
├── requirements.txt
├── requirements-api-test.txt
├── requirements-api.txt
│
├── data/
│   └── fixtures/
│
├── docs/
│   ├── engineering/
│   │   ├── model-versioning-and-scoring.md
│   └── evidence/
│   |   └── demo/
│   └── ...
│
├── infra/
│   └── terraform/
│       ├── README.md
│       ├── main.tf
│       ├── providers.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── ...
│
├── ingestion/
│   ├── event_hubs/
│   │   ├── producer.py
│   │   └── consumer.py
│   └── processing/
│       └── bronze_to_silver.py
├── sql/
│   └── serving/
│       └── 01_create_serving_layer.sql
│
├── scripts/
│   ├── __init__.py
│   └── ...
│
├── src/
│   ├── model_store.py
│   ├── scoring.py
│   └── features.py
|
├── tests/
│   ├── fixtures/
│   └── ...
│
└── sandbox-day1/
    └── ...
```
`sandbox-day1/` contains historical Terraform experimentation retained for reference. The authoritative infrastructure configuration used by the current project and CI/CD workflow is maintained under `infra/terraform/`.

---

## 21. End-to-End Workflow

This project demonstrates an integrated engineering workflow rather than an isolated Python or Azure exercise:

```text
Data Ingestion
      |
      v
Data Lake
      |
      v
Data Quality
      |
      v
Trusted Silver Data
      |
      v
Feature Engineering
      |
      v
ML Preparation
      |
      v
Automated Testing
      |
      v
Infrastructure as Code
      |
      v
      CI
      |
      v
    CD Plan
      |
      v
Plan Artifact
      |
      v
Production Approval
      |
      v
Terraform Apply
      |
      v
Deployment Validation
      |
      v
Rollback Procedure
```

The project therefore demonstrates practical integration between:

* Data engineering
* Cloud infrastructure
* Machine learning engineering
* Data quality
* Automated testing
* Infrastructure as Code
* CI/CD
* Production governance

---

## 22. Interview Summary

A concise explanation of the project:

> I built an Azure transaction-risk data platform that takes transaction data through ingestion, Bronze and Silver data layers, data-quality validation, feature engineering, and ML preparation. I provisioned the Azure infrastructure with Terraform and implemented Azure DevOps CI/CD with automated Python tests, Terraform planning and deployment, production approval, Terraform plan artifact promotion, and post-deployment smoke validation. A direct GitHub push to `main` automatically triggers the CI pipeline on a self-hosted Azure DevOps agent running in Azure Cloud Shell, while CD remains a separate controlled deployment workflow. I also documented a controlled rollback process.

> I also extended the project with a saved-model scoring API and a browser-based transaction interface. The FastAPI service loads versioned model artifacts, validates incoming transactions, derives the required features, and returns prediction results with model metadata. I added API contract tests and documented the local and Cloud Shell execution workflows. The latest recorded automated test run passed all 43 tests. The API demonstration validates the scoring workflow without claiming a persistent production deployment or real-world fraud-detection accuracy.

---

## 23. Project Status

**Project status: Production-readiness implementation completed.**

### Validated Components

* Azure infrastructure
* Terraform
* Data ingestion
* Data quality
* Silver processing
* Feature engineering
* ML validation
* Automated tests
* Azure DevOps CI
* GitHub-to-Azure DevOps CI trigger
* Azure DevOps CD
* Terraform plan artifact promotion
* Production approval
* Deployment smoke validation
* Rollback documentation
* Final Git validation

The final CI workflow has been validated through a direct GitHub push to `main`.

The final CD workflow has been separately validated through a controlled manual deployment, including production approval, Terraform Apply, and post-deployment smoke validation.

The project therefore demonstrates a complete separation between:

```text
Automatic CI Validation
```

and:

```text
Controlled CD Deployment
```

### API and ML Serving Scope

The model-artifact, API-scoring, browser-interface, and API-testing workflows have been 
validated during development. The latest recorded test run passed 43 tests.

The API demonstration runs in local development and Azure Cloud Shell. It should be 
distinguished from the separately validated Terraform infrastructure deployment workflow: a 
successful infrastructure CD run does not, by itself, mean the scoring API is deployed as 
a persistent production service.

---


## 24. Docker and API Validation

### Container Build and Model Delivery

- GitHub Actions builds the Docker image for validation; the image is not published to a container registry.
- The trained XGBoost model is stored in a separate private repository rather than the public application repository.
- GitHub Actions retrieves the model artifacts using a repository-scoped read token stored as a secret.
- The workflow verifies SHA-256 checksums and validates the pinned model run ID and feature contract.
- The model artifacts are mounted read-only at `/models` during container validation rather than baked into the application image.

### Automated API Validation

The successful Docker workflow validates the API using the actual saved model, not a synthetic substitute.

- API health check
- Authentication rejection for protected endpoints
- Invalid request validation
- Model metadata and run ID verification
- Successful transaction prediction using the saved XGBoost model
- Container cleanup after testing

### Model Baseline

- Model run ID: `20261012T024013Z`
- Model type: XGBoost
- Decision threshold: `0.50`
- Expected feature count: 11
- Artifact storage: private model repository
- Runtime artifact path: `/models`

### Local API Validation

The API has also been demonstrated locally using the saved model through the browser-based API interface at `/docs`. The local demonstration validates the practical inference flow without requiring Docker to be installed on the company laptop.

### Current Limitations

- The API has been validated locally and through automated container testing; it is not claimed to be publicly deployed or continuously available.
- Model version promotion is documented as a repeatable procedure; a second model version has not yet been promoted and validated.
- Production hosting, production secrets management, operational monitoring, and production-scale performance validation remain outside the current implementation.

See [Model Lifecycle, Artifact Integrity, and Versioning](docs/engineering/model-lifecycle-and-versioning.md) for the model delivery, integrity, and versioning design.

---

## 25. Model Lifecycle, Artifact Integrity, and Inference

### End-to-End Lifecycle

The fraud-scoring API uses a saved XGBoost model. Model training and API inference are separate activities: the model is trained and evaluated offline, while the API loads an existing model for predictions. Starting the API does not retrain the model.

1. **Train and evaluate:** Train the model using the project's transaction data and engineered features. Evaluate the candidate before releasing it.
2. **Version:** Associate the saved model with a unique model run ID. The current baseline is `20261012T024013Z`.
3. **Store privately:** Keep `model.json`, `manifest.json`, `metrics.json`, and `SHA256SUMS` in the private `azure-transaction-risk-model-artifacts` repository. Model artifacts are kept separate from the public project source code.
4. **Verify integrity:** The Docker GitHub Actions workflow retrieves the private artifacts using a repository-scoped read token and verifies their SHA-256 checksums before building and testing the container.
5. **Validate the model contract:** The workflow checks the pinned run ID and expected feature contract. The model must use the expected 11 features in the correct order.
6. **Load and score:** The container loads the saved model from the mounted `/models` directory and uses it to score transactions through the API.
7. **Test the service:** The workflow tests API health, authentication, invalid input handling, model metadata, and a prediction using the real saved model.

### Current Baseline

- Model run ID: `20261012T024013Z`
- Model format: XGBoost JSON (`model.json`)
- Artifact location: private model repository
- Runtime artifact location: `/models`
- Expected feature count: 11
- API prediction output: fraud probability, predicted class, and risk band

The API reports model metadata, including its version and run ID, so a prediction can be associated with the model used to generate it.

### Automated Validation Evidence

The successful GitHub Actions Docker workflow demonstrates that the workflow can retrieve the real model artifacts, verify their checksums and expected model contract, build the API image, and execute inference inside the container.

**Successful workflow run:** [View Docker build and real-model inference validation](https://github.com/nabila-natasha/azure-transaction-risk-platform/actions/runs/38841433984)

This is automated container validation, not a claim that the API is publicly deployed or continuously running.

See [`docs/engineering/model-lifecycle-and-versioning.md`](docs/engineering/model-lifecycle-and-versioning.md) for the detailed lifecycle and model-update procedure.

---

## 26. Evidence

Selected screenshots demonstrating the implementation and validation of the platform.

### CI/CD Validation

- [Azure DevOps CI — Successful](docs/evidence/day11-ci-success.PNG)
- [Azure DevOps CD — Successful](docs/evidence/day11-cd-success.PNG)

### Data Engineering & Security

- [ADF RBAC](docs/evidence/day03-adf-rbac.PNG)
- [Synapse RBAC](docs/evidence/day08-syn-rbac.PNG)
- [Terraform State Storage RBAC](docs/evidence/day09-sttfstatebello-storage-rbac.PNG)
- [Azure DevOps Workload Identity Federation](docs/evidence/day09-azure-devops-workload-identity-federation.PNG)

### Data & Analytics

- [Data Model](docs/evidence/day08-data-model.PNG)
- [Power BI Fraud Risk Overview](docs/evidence/day08-powerbi-fraud-risk-overview.PNG)
- [Power BI Transaction Investigation](docs/evidence/day08-powerbi-transaction-investigation.PNG)

### ML Scoring API Demonstration

See [API Demonstration Evidence](docs/evidence/demo/README.md) for screenshots covering:

- Local API startup and interactive FastAPI documentation
- Local model metadata and prediction response
- API health and browser-based prediction interface
- Prediction parity validation
- Azure Cloud Shell Web Preview
- Azure DevOps pipeline execution

The successful Docker GitHub Actions workflow provides additional automated evidence of checksum verification, model contract validation, and inference using the actual saved model inside a container.

The evidence supports the demonstrated functionality and recorded validation results. It is not a claim of production-scale performance, persistent public deployment, or real-world fraud-detection accuracy.
