# ADR-005: Use Azure DevOps for CI/CD

## Status

Accepted

## Context

The project requires automated validation of application code and Terraform configuration, together with a controlled mechanism for deploying infrastructure.

The CI/CD process should distinguish between:

1. Validating changes automatically
2. Making changes to Azure infrastructure through a controlled release

## Decision

Use Azure DevOps Pipelines for CI/CD.

The project uses separate CI and CD pipelines.

### CI

CI is automatically triggered when changes are pushed to the `main` branch.

CI performs:

* Environment validation
* Python dependency installation
* Python syntax validation
* Automated tests
* Azure authentication
* Terraform initialization
* Terraform validation
* Terraform planning

### CD

CD is a separate controlled workflow.

CD performs:

* Terraform planning
* Publishing the Terraform plan as an artifact
* Production approval
* Applying the approved plan
* Post-deployment smoke validation

## Alternatives Considered

### GitHub Actions

GitHub Actions could provide CI/CD because the source code is hosted on GitHub. Azure DevOps was selected to demonstrate Azure DevOps pipeline capabilities and controlled infrastructure deployment.

### Manual Deployment

Manual Terraform execution would reduce automation and make deployments less reproducible.

## Rationale

Separating CI from CD allows code and infrastructure changes to be validated automatically without making every source-code push automatically modify Azure infrastructure.

The resulting model is:

```text
GitHub Push
     |
     v
Azure DevOps CI
     |
     v
Tests + Terraform Plan
     |
     v
CI Success
     |
     | manual release
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

## Consequences

### Positive

* Automatic CI validation
* Controlled infrastructure deployment
* Clear separation of validation and release
* Approval before production infrastructure changes
* Deployment validation after Terraform Apply

### Negative

* Two pipeline definitions must be maintained
* CD requires an explicit release action
* Azure DevOps configuration becomes part of the platform

## Project Evidence

The project uses `azure-pipelines-ci.yml` and `azure-pipelines-cd.yml`. The CI pipeline is automatically triggered by pushes to `main`, while CD remains a separate controlled release workflow.
