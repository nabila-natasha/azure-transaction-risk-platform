# Day 11 — Production Readiness

## Objective

Day 11 converted the Azure Transaction Risk Platform from an implementation-focused project into a production-oriented engineering workflow.

The focus was:

* Automated testing
* CI validation
* Deployment validation
* Terraform plan artifact promotion
* Production approval
* Smoke testing
* Rollback documentation
* Final production validation

---

## 1. Automated Test Suite

A real Silver-derived Parquet fixture was added:

```text
tests/fixtures/silver_transactions_sample.parquet
```

The fixture contains 100 rows and is used by the automated tests.

The test suite covers four areas.

### Feature Engineering

Test file:

```text
tests/test_feature_engineering.py
```

Validates that the expected engineered features are produced.

### ML Contract

Test file:

```text
tests/test_ml_contract.py
```

Validates the exact expected ML feature contract:

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

### Data Quality

Test file:

```text
tests/test_data_quality.py
```

Validates expected data-quality behaviour.

### Model Smoke Testing

Test file:

```text
tests/test_model_smoke.py
```

Provides lightweight validation that the ML workflow can execute against the prepared data.

---

## 2. Pytest Configuration

The repository contains:

```text
pytest.ini
```

This provides consistent pytest configuration for local development and Azure DevOps CI.

The `scripts` directory also contains:

```text
scripts/__init__.py
```

This allows project scripts to be imported consistently during testing.

---

## 3. CI Pipeline

The CI pipeline is defined in:

```text
azure-pipelines-ci.yml
```

The pipeline performs:

1. Repository checkout
2. Environment validation
3. Python dependency installation
4. Python syntax compilation
5. pytest execution
6. Azure authentication
7. Terraform initialization
8. Terraform validation
9. Terraform plan

The Python test stage completed successfully:

```text
16 passed
```

---

## 4. Terraform Plan

The CI pipeline executes:

```bash
terraform init
terraform validate
terraform plan
```

The Synapse SQL administrator password is supplied through the Azure DevOps pipeline variable:

```text
SYNAPSE_SQL_ADMIN_PASSWORD
```

It is passed to Terraform through:

```text
TF_VAR_synapse_sql_admin_password
```

No password is committed to Git.

---

## 5. CD Pipeline

The CD pipeline is defined in:

```text
azure-pipelines-cd.yml
```

The CD pipeline is manually triggered rather than automatically applying infrastructure changes on every commit.

The deployment workflow is:

```text
Plan
  |
  v
Publish Terraform Plan
  |
  v
Apply Stage
  |
  v
Production Environment Approval
  |
  v
Terraform Apply
  |
  v
Smoke Validation
```

---

## 6. Terraform Plan Artifact

The Plan stage creates the Terraform plan:

```text
infra/terraform/tfplan
```

The plan is published as the Azure DevOps pipeline artifact:

```text
terraform-plan
```

The Apply stage downloads that artifact and applies the downloaded plan.

This avoids generating a different Terraform plan during the deployment stage and helps ensure that the reviewed plan is the plan that gets applied.

---

## 7. Production Environment

The Apply job uses the Azure DevOps environment:

```text
terraform-production
```

This provides an explicit production approval boundary.

The deployment therefore separates:

```text
Validation
```

from:

```text
Production Infrastructure Modification
```

This provides a controlled deployment workflow rather than automatically applying every infrastructure change.

---

## 8. Deployment Smoke Validation

After Terraform Apply, Azure DevOps performs deployment smoke validation.

The validation checks:

```text
Azure subscription
Resource group
Deployed Azure resources
Provisioning state
```

The expected production resource group is:

```text
rg-transaction-risk-platform
```

The smoke validation completed successfully during the final CD execution.

---

## 9. Rollback Procedure

Rollback documentation was added at:

```text
docs/rollback.md
```

The project does not claim automated rollback.

The documented rollback process is:

```text
Detect Issue
    |
    v
Identify Problematic Commit
    |
    v
Git Revert
    |
    v
CI Validation
    |
    v
Terraform Plan
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

This keeps rollback controlled and auditable.

---

## 10. Final Main Branch Merge

Day 11 production-readiness work was merged into `main`.

Final merge commit:

```text
654eff1
Merge branch 'feature/day11-production-readiness'
```

The production-readiness feature branch contained:

```text
93db707  ci: add deployment smoke validation and rollback procedure
f402a0f  ci: run automated Python test suite
8dc813f  Delete tests/.gitkeep
7efe814  test: add ML pipeline validation and smoke tests
```

---

## 11. Final CI Validation

CI was manually executed against:

```text
main
```

The pipeline completed successfully.

This validated:

* Python environment
* Python dependencies
* Python syntax
* Automated tests
* Azure authentication
* Terraform initialization
* Terraform validation
* Terraform plan

---

## 12. Final CD Validation

CD was manually executed against:

```text
main
```

The pipeline completed successfully.

The following stages were validated:

```text
Terraform Plan
       |
       v
Terraform Plan Artifact
       |
       v
Production Approval
       |
       v
Terraform Apply
       |
       v
Post-Deployment Smoke Validation
```

---

## 13. Final Git Validation

The final Git validation command was:

```bash
git status
```

Expected result:

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

Final HEAD:

```text
654eff1
```

Remote:

```text
origin/main
```

---

## 14. GitHub Trigger Follow-Up

The Azure DevOps CI pipeline itself is functional and has successfully run against `main`.

The remaining issue is the automatic GitHub push trigger.

Observed behaviour:

```text
Manual CI run
      |
      v
Successful

GitHub push
      |
      v
Automatic CI trigger does not start
```

This should be investigated separately as a GitHub-to-Azure DevOps integration configuration issue.

It does not change the successful validation of the CI pipeline through manual execution.

---

## 15. Day 11 Completion Criteria

| Requirement                     | Status                       |
| ------------------------------- | ---------------------------- |
| Automated Python tests          | Complete                     |
| ML smoke tests                  | Complete                     |
| Feature contract tests          | Complete                     |
| Data-quality tests              | Complete                     |
| Silver-derived test fixture     | Complete                     |
| CI test execution               | Complete                     |
| Terraform validation            | Complete                     |
| Terraform plan                  | Complete                     |
| Terraform plan artifact         | Complete                     |
| Production environment approval | Complete                     |
| Terraform Apply                 | Complete                     |
| Deployment smoke validation     | Complete                     |
| Rollback documentation          | Complete                     |
| Main branch merge               | Complete                     |
| Final CI validation             | Complete                     |
| Final CD validation             | Complete                     |
| Git working tree clean          | Complete                     |
| Automatic GitHub push trigger   | Follow-up configuration item |

---

## Day 11 Conclusion

Day 11 completed the production-readiness layer of the project.

The platform now demonstrates not only data ingestion and ML preparation, but also:

* Automated validation
* Infrastructure as Code deployment
* Terraform plan promotion
* Controlled production approval
* Deployment verification
* Documented rollback procedures
* Final Git and CI/CD validation

The result is an end-to-end engineering workflow that connects data processing, machine learning preparation, cloud infrastructure, testing, and DevOps deployment practices.
