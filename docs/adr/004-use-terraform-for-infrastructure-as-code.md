# ADR-004: Use Terraform for Infrastructure as Code

## Status

Accepted

## Context

The platform uses multiple Azure resources, including storage, Event Hubs, Data Factory, Synapse, managed identities, role assignments, and supporting resource-group infrastructure.

Manually creating these resources through the Azure Portal would make the environment harder to reproduce and audit.

## Decision

Use Terraform as the Infrastructure as Code (IaC) solution for Azure infrastructure.

Terraform defines and manages the infrastructure required by the project.

Terraform state is stored remotely in Azure Storage rather than being kept only on the local development machine.

## Alternatives Considered

### Azure Portal

Portal-based deployment is useful for exploration but is not ideal for repeatable infrastructure management.

### Azure CLI Scripts

CLI scripts can automate resource creation but require procedural logic and can become difficult to maintain as infrastructure grows.

### ARM/Bicep

Azure-native IaC technologies are viable alternatives. Terraform was selected for this project because it demonstrates a widely used declarative, multi-cloud-compatible IaC workflow and integrates directly with the project's CI/CD process.

## Rationale

Terraform allows infrastructure to be described declaratively and reviewed as version-controlled code.

It also provides a clear plan-before-apply workflow that fits the project's controlled deployment model.

## Consequences

### Positive

* Repeatable infrastructure deployment
* Version-controlled infrastructure definitions
* Terraform plan provides a reviewable change set
* Supports CI/CD integration
* Reduces dependence on manual Portal configuration

### Negative

* Requires Terraform state management
* Requires careful handling of infrastructure changes
* Terraform itself becomes another component that must be maintained

## Project Evidence

Terraform manages the core Azure infrastructure for the project, and the Azure DevOps pipelines execute Terraform initialization, validation, plan, and controlled apply operations.
