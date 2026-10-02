# ADR-006: Use Workload Identity Federation for Azure Authentication

## Status

Accepted

## Context

The Azure DevOps pipelines need to authenticate to Azure in order to execute Terraform operations.

Long-lived client secrets or passwords would introduce credential-management and rotation requirements and create a risk of storing persistent secrets in pipeline configuration.

## Decision

Use Azure DevOps workload identity federation with an Azure service connection.

The Azure DevOps pipeline authenticates through the configured service connection and receives federated credentials for Azure access.

No long-lived Azure client secret is required by the pipeline.

## Alternatives Considered

### Client Secret

A service principal client secret could be used, but it would require secure storage, rotation, and lifecycle management.

### Managed Identity

Managed identities are useful for Azure-hosted resources, but the CI/CD pipeline requires an identity mechanism that integrates with the Azure DevOps service connection.

## Rationale

Workload identity federation provides short-lived federated authentication between Azure DevOps and Microsoft Entra ID without requiring a persistent client secret in the repository.

This also demonstrates a modern passwordless authentication pattern for CI/CD.

## Consequences

### Positive

* No long-lived client secret in the repository
* Reduced credential-management overhead
* Suitable for automated pipelines
* Integrates with Azure DevOps service connections

### Negative

* Requires correct federation configuration
* Requires appropriate Azure RBAC permissions
* Authentication depends on the Azure DevOps service connection being correctly configured

## Project Evidence

The project uses the Azure DevOps service connection `sc-transaction-risk-platform` for Azure authentication during Terraform operations.
