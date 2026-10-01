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

| Area                    | Technology                                       |
| ----------------------- | ------------------------------------------------ |
| Cloud                   | Microsoft Azure                                  |
| Infrastructure as Code  | Terraform                                        |
| Storage                 | Azure Data Lake Storage / Azure Storage          |
| Streaming / Ingestion   | Azure Event Hubs                                 |
| Data Processing         | Python, Pandas, PyArrow                          |
| Machine Learning        | Python / scikit-learn workflow                   |
| Testing                 | pytest                                           |
| CI/CD                   | Azure DevOps Pipelines                           |
| Source Control          | Git / GitHub                                     |
| Authentication          | Azure DevOps service connection / Azure identity |
| Environment Approval    | Azure DevOps Environment                         |
| Data Format             | Parquet                                          |
| Development Environment | Azure Cloud Shell                                |

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

The project prepares a Silver-derived dataset for machine learning.

The ML workflow separates:

1. Data preparation
2. Feature engineering
3. Feature-contract validation
4. Model-input validation
5. Model smoke testing

The objective is to demonstrate the engineering lifecycle surrounding an ML workload rather than claim production fraud-detection performance.

Model results should therefore be interpreted as portfolio and engineering validation rather than as a production financial-risk model.

---

## 9. Automated Testing

The repository contains automated tests covering:

* Feature engineering
* ML feature contract
* Data quality
* Model smoke validation

The test suite was successfully executed with:

```text
16 passed
```

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

The CI pipeline has been manually executed successfully against the `main` branch.

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

The final repository state was validated as follows:

```text
Branch:
main

HEAD:
654eff1

Remote:
origin/main

Working tree:
clean
```

Final Git validation:

```bash
git status
```

Result:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

The final CI pipeline completed successfully.

The final CD pipeline completed successfully, including:

* Terraform Plan
* Terraform Apply
* Production approval
* Post-deployment smoke validation

---

## 19. Known CI Trigger Configuration Item

The Azure DevOps pipeline has been validated successfully through manual execution.

One remaining integration item is the automatic GitHub push trigger:

```text
GitHub Push
    |
    X
Azure DevOps Automatic CI Trigger
```

Manual execution against `main` succeeds, so this remaining item is isolated to the GitHub-to-Azure-DevOps trigger integration rather than the CI pipeline implementation itself.

This should be treated as a follow-up configuration task.

---

## 20. Repository Structure

A simplified repository structure is:

```text
azure-transaction-risk-platform/
│
├── .gitignore
├── README.md
├── azure-pipelines-ci.yml
├── azure-pipelines-cd.yml
├── pytest.ini
├── requirements.txt
│
├── data/
│   └── fixtures/
│
├── docs/
│   ├── notes/
│   │   └── ...
│   ├── evidence/
│   │   └── ...
│   ├── rollback.md
│   ├── day11-production-readiness.md
│   └── project-completion.md
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
│
├── sql/
│   └── serving/
│       └── 01_create_serving_layer.sql
│
├── scripts/
│   ├── __init__.py
│   └── ...
│
├── tests/
│   ├── fixtures/
│   ├── test_data_quality.py
│   ├── test_feature_engineering.py
│   ├── test_ml_contract.py
│   └── test_model_smoke.py
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
Production Approval
      |
      v
CD
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

> I built an Azure transaction-risk data platform that takes transaction data through ingestion, Bronze and Silver data layers, data-quality validation, feature engineering, and ML preparation. I provisioned the Azure infrastructure with Terraform and implemented Azure DevOps CI/CD with automated Python tests, Terraform plan and apply, a production approval environment, plan artifact promotion, and post-deployment smoke validation. I also documented a controlled rollback process. The final CI and CD pipelines were successfully validated on the main branch.

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
* Azure DevOps CD
* Production approval
* Deployment smoke validation
* Rollback documentation
* Final Git state

### Remaining Configuration Item

* Automatic GitHub push trigger integration with Azure DevOps

The core CI/CD workflow has been successfully validated through manual pipeline execution, while the GitHub push trigger remains a separate integration configuration item.

---

## 24. Evidence

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
